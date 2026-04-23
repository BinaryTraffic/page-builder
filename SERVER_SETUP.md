# LP Editing Server Setup (PHP Edition)

Last updated: 2026-04-23（site-login・cms_credentials・クライアント主体に整合）

## Goal
- UploadしたLPをブラウザ上で編集できるようにする
- **ローカル LP Builder**は「生成（**`custom/lp_meta.json` + `custom/cms_credentials.json` 同梱**）+ アップロード + 編集情報発行」を**主体**として担当する
- サーバーは「認証 + 保存API + 公開反映」を担当する（**ドキュメントルート配下の `cms/` は既存前提**。本書は配置手順ではなく仕様・検証の参照用）

## Architecture
- **Windows LP Builder（正: 生成物）**
  - LP生成
  - SFTPアップロード
  - 編集URL / **site_key（フォルダ名）** / 初期PWを表示（**`cms_credentials.json` と一致**）
- **PHP Server（既存 `cms/`）**
  - **`POST /cms/api/site-login.php`** — LP 編集者: `site_key` + パスワード、`{DOCUMENT_ROOT}/{site_key}/custom/cms_credentials.json` を検証（**`users.json` に LP 専用ユーザを増やさない**）
  - `POST /cms/api/login.php` — 運用管理者（`users.json`）
  - `POST /cms/api/logout.php`
  - `GET /cms/api/me.php` — `auth: site | user`
  - `POST /cms/api/change-password.php` — セッションに応じて **`cms_credentials.json` または `users.json`**
  - `POST /cms/api/select-site.php` — **管理者ログイン経路**のマルチ LP 選択（サイト認証セッションでは拒否）
  - `GET /cms/api/content.php`
  - `PUT /cms/api/content.php`
  - `POST /cms/api/upload-image.php`（任意）
- **Browser Editor**
  - **site-login または login** → 画像/文言編集（管理 UI にヒーロー帯プレビュー）→ `content.json` 保存
  - 保存と同時に **`{site_key}/custom/cms_page_state.json`** を生成
- **公開 LP（任意）** — 各 `index.html` の `</body>` 直前に  
  `<script src="/cms/overlay-apply.js" defer></script>`  
  を追加し、`/cms/overlay-apply.js`（リポジトリ `server/cms/overlay-apply.js`）を配信すると **`.hero-bg` / 代表テキスト** に反映

---

## 1) Prerequisites
- Ubuntu 22.04+（または同等）
- Nginx or Apache
- PHP 8.1+（`json`, `mbstring`, `openssl`）
- TLS証明書（Let's Encrypt）

Example install:

```bash
sudo apt update
sudo apt install -y nginx php-fpm php-cli php-mbstring php-json php-curl
```

---

## 2) Directory Layout

```text
/var/www/lp_site/
  index.html
  style.css
  script.js
  pexels.js
  custom/
    config.json
    lp_meta.json                # クライアントが生成: LP 一意識別（下記 3.1）
  cms/
    admin/                # 編集UI (HTML/JS/CSS)
    api/
      bootstrap.php
      login.php
      logout.php
      me.php
      content.php
      upload-image.php    # optional
    data/
      content.json
      users.json
      audit.log
      login_attempts.json
```

Permission example:

```bash
sudo chown -R www-data:www-data /var/www/lp_site/cms/data /var/www/lp_site/custom
sudo chmod -R 750 /var/www/lp_site/cms/data
```

---

## 3) Data Model (MVP)

### 3.1) `custom/lp_meta.json`（各 LP サイト・クライアントが生成）

LP Builder は **1 LP 生成ごと**に、出力フォルダ名と同じ階層の `custom/lp_meta.json` を置く。SFTP で `.../public_html/<site_key>/` へ上げると **サーバーがファイルとして受け取れる**（追加 API 不要でも運用可）。

| キー | 例 | 意味 |
|------|-----|------|
| `lp_token` | 24 桁 hex | 暗号乱数で発行。別 LP と衝突しない一意 ID |
| `site_key` | `店名_20260423_123456_abc...` | ディレクトリ名＝**公開 URL のパス1セグメント**（`.../<site_key>/index.html`） |
| `generated_at` | ISO 8601 | 生成日時（監査用） |

### 3.2) `custom/cms_credentials.json`（各 LP・**クライアントが生成**・サイトログインの正）

LP Builder が **`password_hash`（bcrypt）**・`lp_token`・`must_change_password` 等を書き出す。サーバーは **`POST site-login.php`** でこのファイルを読み **`password_verify`** する。**LP ごとに `users.json` にアカウントを増やす方式ではない**。

### 3.3) サイト台帳（`sites.json`）— 主に**管理者経路**向け

以下は **従来の** `lp_meta` 受け取り方。`site-login` 経路では **LP ディレクトリ内の `cms_credentials.json` が認証の正**。

サーバー実装案（いずれか）:

- **受動**: 各サイトの `custom/lp_meta.json` を集約バッチ or デプロイフックで読み、CMS/DBの「サイト台帳」に `lp_token` → パス or `site_key` を登録。
- **能動**（任意）: `POST /cms/api/register-site.php` に `{ "lp_token", "site_key" }` を出す（**認証必須**）。上書き・なりすまし防止のレート制限付き。

---

### `cms/data/content.json`

```json
{
  "images": {
    "hero": "hero.jpg",
    "about": "about.jpg",
    "reason1": "reason1.jpg"
  },
  "texts": {
    "hero_title": "タイトル",
    "hero_desc": "説明文"
  },
  "updated_at": "2026-04-22T10:00:00+09:00",
  "updated_by": "lp-admin"
}
```

### `cms/data/users.json`

```json
{
  "users": [
    {
      "id": "lp-admin",
      "password_hash": "$2y$10$...",
      "must_change_password": true,
      "active": true
    }
  ]
}
```

---

## 4) Auth + Session Rules
- PHP session利用（`$_SESSION`）
- Cookie:
  - `HttpOnly=true`
  - `Secure=true`（HTTPS）
  - `SameSite=Lax`
- パスワードは `password_hash` / `password_verify`
- ログイン失敗制限:
  - 例: 5回失敗で10分ロック

---

## 4.1) 初期パスワード + 初回変更強制フロー（2 経路）

### 経路 A: LP 編集者（`site-login`）— **ハッシュの正はクライアント生成ファイル**

- LP Builder が **`custom/cms_credentials.json`** に **`password_hash`** と **`must_change_password`** を書く（初期平文は ② の表示と一致）。
- サーバーは **`POST site-login.php`** で検証。**変更時は `change-password.php` が同一ファイルを更新**。
- **`must_change_password: true` の間は編集 API を拒否**（`password_change_required`）。

### 経路 B: 運用管理者（`login.php`）— **`users.json` の正はサーバー**

- サーバーで初期（一時）パスワードを決め、`users.json` に **ハッシュのみ** 保存する（例: `lp-admin`）。
- **`must_change_password` が true の間は編集 API を拒否**し、変更後に解除。
- マルチ LP は **`select-site.php`** と台帳・`allowed_site_keys` を利用。

### LP Builder 側（クライアント）

- ②に **編集 URL・site_key（フォルダ名）・初期 PW** を表示。**経路 A** では **`cms_credentials.json`** と同一の初期値がログインに使える。

---

## 5) API Spec (MVP)

### `POST /cms/api/site-login.php`
- input: `{ "site_key": "<フォルダ名>", "password": "<平文>" }`
- 処理: `{DOCUMENT_ROOT}/{site_key}/custom/cms_credentials.json` を読み `password_verify`。可能なら `lp_meta.json` の `lp_token` と整合。
- success: session（`site_auth_*`, `active_site_key`, `active_lp_token`, `csrf`）+ `{ "ok": true, "must_change_password": bool }`
- fail: `credentials_not_found` / `invalid_credentials` / `lp_token_mismatch` 等

### `POST /cms/api/login.php`
- input: `{ "id": "...", "password": "..." }`
- success:  
  - 通常: `{ "ok": true, "must_change_password": false }` + session  
  - 初回: `{ "ok": true, "must_change_password": true }` + session（編集系APIは change 完了まで拒否 or 専用UIのみ）
- fail: `{ "ok": false, "error": "invalid_credentials" }`

### `POST /cms/api/logout.php`
- session破棄
- return `{ "ok": true }`

### `GET /cms/api/me.php`
- ログイン状態確認
- **サイト認証時:** `{ "ok": true, "auth": "site", "user": { "id": "site", "must_change_password": bool }, "active_site_key": "...", ... }`
- **ユーザ認証時:** `{ "ok": true, "auth": "user", "user": { "id": "lp-admin", ... }, ... }`  
  未認証: `{ "ok": false, "error": "unauthorized" }`

### `POST /cms/api/change-password.php`
- 認証必須（初回: セッションはあるが `must_change_password: true` のみ許可、など実装方針を揃える）
- input: `{ "current_password": "...", "new_password": "..." }`（初回は `current_password` を一時PWと比較）
- success: `password_hash` 更新 + `must_change_password: false` + `{ "ok": true }`
- fail: 例 `{ "ok": false, "error": "weak_password" }` / `invalid_current`

### `GET /cms/api/content.php`
- `content.json` 返却（認証必須 + **`must_change_password` が false のときのみ**）
- `must_change_password: true` のセッション: `403` + `{ "ok": false, "error": "password_change_required" }`（推奨。フロントは change UI へ誘導）

### `PUT /cms/api/content.php`
- `content.json` 更新（認証 + CSRFチェック + **同上: パスワード未変更の初回は拒否**）
- return `{ "ok": true, "updated_at": "..." }`

### `POST /cms/api/upload-image.php` (optional)
- multipart upload
- `custom/` に保存
- return `{ "ok": true, "file": "reason1_20260422.jpg" }`

---

## 6) Bootstrap Script (Initial Admin User)
1. サーバーで一時平文を決める（**この文字列をサーバー上でハッシュ化し、** `users.json` には入れない）。`jitan.app` 採用の初回一時平文: `Whatisthepassword?`。
2. ハッシュ生成（例: 上記文字列の場合、ダブルクオート内をその平文に置き換え）:

```bash
php -r 'echo password_hash("Whatisthepassword?", PASSWORD_DEFAULT), PHP_EOL;'
```

3. `cms/data/users.json` の例（**必ず** `must_change_password: true`）:

```json
{
  "users": [
    {
      "id": "lp-admin",
      "password_hash": "（上記コマンドの出力）",
      "must_change_password": true,
      "active": true
    }
  ]
}
```

4. **運用**: 一時平文を担当者に安全に渡す（口頭・1Password 等）。LP Builder ②に手入力しておけば、手元表示と揃う。

---

## 7) Nginx Example (High Level)
- `/` -> static LP
- `/cms/admin/` -> editor UI files
- `/cms/api/` -> PHP-FPM
- deny direct access to `cms/data/*`

Important rules:
- `location ^~ /cms/data/ { deny all; }`
- HTTPS redirect enabled

---

## 8) Local App Integration (LP Builder)
アプリは **生成時に `lp_token` / `site_key` を `custom/lp_meta.json` に埋め、あわせて `custom/cms_credentials.json` を出力し、フォルダ名＝`site_key`、SFTP 先も同一セグメント**に揃える。多数量産時も **URL 上で LP を一意**に区別する。

仮想ホスト配下の例: `https://jitan.app/<site_key>/index.html`

**LP 編集者向けログイン:** 初期パスワードの定義は **クライアントが `cms_credentials.json` に書いた内容**と一致させ、ブラウザは **`site-login.php`** を使う。**運用管理者**向けの **`lp-admin` 等は `users.json`**（経路が異なる）。

`④アップロード` ほか ② に表示:
- 公開URL
- 編集URL（例: `https://example.com/cms/admin/?site_key=...`）
- **site_key（フォルダ名）**
- 初期/一時PW（伏せ字 + 表示/コピー）→ **`cms_credentials.json` と同じ値**

Upload target:
- LP static files
- `custom/config.json`
- (optional) 初期 `content.json`

---

## 9) Security Minimum
- HTTPS mandatory
- Plain password never stored
- CSRF token on write API
- Login rate limit / lock
- Audit log (`cms/data/audit.log`)
  - time, user, action, ip
- Backup:
  - `content.json`
  - `users.json`

---

## 10) Optional: Encrypted Payload from Windows App
If needed:
- Windows app uploads encrypted bootstrap payload
- PHP server decrypts (server key only)
- server updates `users.json` / editor config

Rule:
- decrypt key never distributed to Windows client

---

## 11) Deployment Checklist
- [ ] PHP-FPM running
- [ ] Nginx/Apache routing OK
- [ ] `/cms/admin` login works（一時パスワード＝サーバー反映値）
- [ ] 初回ログイン後、パスワード変更フローで `must_change_password` が false になる
- [ ] 変更前は `content` / 画像UP が拒否（または専用UIのみ）で、変更後に編集可能
- [ ] `/cms/api/content.php` GET/PUT works
- [ ] LP reflects `content.json`
- [ ] `cms/data/` is not web-accessible
- [ ] lock/rate limit works
- [ ] backup/restore tested

---

## 12) Operation Flow
1. **サーバー**で初期ユーザ＋一時パスワードを `users.json` に登録。一時平文を運用者へ手渡し。
2. LP Builder generates LP locally.
3. LP Builder uploads files via SFTP.（必要なら②に一時平文をメモ＝**サーバーと同じ**）
4. Editor opens `/cms/admin`, logs in with **一時** credentials.
5. 初回はパスワード変更画面（または専用API）で本番用へ変更。`must_change_password` 解除。
6. Editor edits image/text and saves.
7. Server writes `content.json`.
8. Public LP renders updated content.

---

## Notes for Separate Cursor Session
- First build MVP only:
  - login/logout
  - content GET/PUT
- Keep schema simple (`images`, `texts`, `updated_at`)
- Add upload API and audit hardening after MVP verification.

---

## Server-side Work Log (2026-04-23)
This section records what was actually done on the server for this environment.

### A) Apache vhost cleanup and unification
- Unified `jitan.app` vhost settings into:
  - `/etc/apache2/sites-available/jitan.app-le-ssl.conf`
- Removed duplicate HTTP definition:
  - disabled `jitan.app.conf` (`a2dissite jitan.app.conf`)
- Kept HTTPS redirect on `:80` and main site on `:443`.

### B) Migrated to PHP CMS implementation
- Implemented PHP API endpoints:
  - `cms/api/bootstrap.php`
  - `cms/api/login.php`
  - `cms/api/logout.php`
  - `cms/api/me.php`
  - `cms/api/content.php`
  - `cms/api/upload-image.php` (optional)
- Implemented simple admin UI:
  - `cms/admin/index.html`
  - `cms/admin/main.js`
  - `cms/admin/style.css`
- Created/updated data files:
  - `cms/data/users.json`
  - `cms/data/content.json`
  - `cms/data/login_attempts.json`
  - `cms/data/audit.log`

### C) Apache routing changes for PHP edition
- Removed FastAPI reverse proxy rules (`/admin`, `/api`) from `jitan.app-le-ssl.conf`.
- Added redirect:
  - `/admin` -> `/cms/admin/`
- Added data protection:
  - `<LocationMatch "^/cms/data/"> Require all denied </LocationMatch>`
- Added `open_basedir` for this site to allow PHP access to:
  - `/home/lp-tool` and `/tmp` (plus existing paths).

### D) Permissions set on server
- Created/ensured directories:
  - `/home/lp-tool/cms/admin`
  - `/home/lp-tool/cms/api`
  - `/home/lp-tool/cms/data`
  - `/home/lp-tool/custom`
- Applied runtime write permissions:
  - `chown -R www-data:www-data /home/lp-tool/cms/data /home/lp-tool/custom`
  - `chmod -R 750 /home/lp-tool/cms/data`

### E) Service cleanup (from previous FastAPI phase)
- Stopped and disabled old service:
  - `lp-cms.service`
- Removed old unit file:
  - `/etc/systemd/system/lp-cms.service`

### F) Validation results
- `https://jitan.app/cms/admin/` returns `200`.
- `https://jitan.app/admin` redirects to `/cms/admin/`.
- `https://jitan.app/cms/data/content.json` is blocked (`403`).
- API flow checked:
  - login -> me -> content GET -> content PUT all OK.

### G) Initial admin account (temporary)
- id: `lp-admin`
- temporary password: `Whatisthepassword?`（サーバーでこの平文の `password_hash` を `users.json` に登録。平文はファイルに含めない）
- action required: 初回ログイン後、必須のパスワード変更（`must_change_password` 解除）で本番用へ差し替え

---

## Handover Checklist (Operations)
- [ ] Change temporary admin password immediately (`lp-admin`).
- [ ] Rotate session and secret-related values as needed.
- [ ] Verify TLS certificate validity and renewal schedule.
- [ ] Confirm Apache vhost is loaded as intended (`jitan.app-le-ssl.conf`).
- [ ] Confirm `/cms/data/*` remains blocked from web access.
- [ ] Verify login lock behavior (5 failures -> 10 minute lock).
- [ ] Set up periodic backup for:
  - `cms/data/content.json`
  - `cms/data/users.json`
  - `cms/data/audit.log`
  - `cms/data/login_attempts.json`
- [ ] Test restore procedure from backup on staging or safe environment.
- [ ] Review Apache/PHP error logs after first production edits.

