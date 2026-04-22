# LP Editing Server Setup (PHP Edition)

Last updated: 2026-04-23 05:53:08 +09:00

## Goal
- UploadしたLPをブラウザ上で編集できるようにする
- ローカルLP Builderは「生成 + アップロード + 編集情報発行」を担当
- サーバーは「認証 + 保存API + 公開反映」を担当

## Architecture
- **Windows LP Builder**
  - LP生成
  - SFTPアップロード
  - 編集URL / ログインID / 初期PWを表示
- **PHP Server**
  - `POST /cms/api/login.php`
  - `POST /cms/api/logout.php`
  - `GET /cms/api/me.php`
  - `POST /cms/api/change-password.php`（初回一時パスワード→本番用へ変更）
  - `GET /cms/api/content.php`
  - `PUT /cms/api/content.php`
  - `POST /cms/api/upload-image.php`（任意）
- **Browser Editor**
  - ログイン
  - 画像/文言編集
  - `content.json` 保存

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

## 4.1) 初期パスワード + 初回変更強制フロー（採用方針）

**認証の正はサーバー側**とする。ローカルLP Builderに入力しても、サーバーの `users.json` にハッシュ登録がない限りWebログインできない。

### 方針

- サーバーで **簡易な初期（一時）パスワード** を1つ生成し、`users.json` に **ハッシュのみ** 保存する。
- 各ユーザに `must_change_password: true` を付与する（初回のみ true）。
- ログイン成功時、**`must_change_password` が true なら CMS 編集UI（`/content` 等）へ入れない**。  
  代わりに **パスワード変更専用画面** のみ表示する（または専用API成功まで `403` + `error: "password_change_required"` を返す）。
- **`POST /cms/api/change-password.php`**（または同等）で新パスワードを受け取り、`password_hash` 更新 + `must_change_password: false` + 監査ログ。
- 初回パスワードは **案件・環境ごとに変えてよい**が、**ドキュメントに平文のまま永続化しない**（手渡し・パスワードマネージャ推奨）。

### なぜこのフローか

- ローカルアプリにだけPWを入れても、**同期API未実装のまま**ではWeb側 `invalid_credentials` になる。解決策は (A) サーバーで初期PWを正として配る、または (B) リモート登録APIを後から足す。本プロジェクトは **(A) を正**とし、**LP Builder は編集URL・ID・一時PWの表示・メモ用**（手動で同じ値を入れればよい）。

### ローカルLP Builder側（変更不要の範囲）

- ②画像・設定に **編集URL / ログインID / 一時PW** を表示・保存するUIは **そのまま利用可**。
- **実際のログインに使う一時パスワード**は、**サーバーで発行・反映した値と同じ**にする（手数はサーバー発行に合わせる）。

---

## 5) API Spec (MVP)

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
- return: `{ "ok": true, "user": { "id": "lp-admin", "must_change_password": false } }`  
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
アプリは **生成時に `lp_token` / `site_key` を `custom/lp_meta.json` に埋め、フォルダ名＝`site_key`、SFTP 先も同一セグメント**に揃える。多数量産時も **URL 上で LP を一意**に区別する。

仮想ホスト配下の例: `https://jitan.app/<site_key>/index.html`

ログイン用一時パスワードの **定義元は常にサーバー**（`users.json`）。`lp_meta` はサイト識別専用。

`④アップロード` ほか ② に表示:
- 公開URL
- 編集URL（例: `https://example.com/cms/admin/`）
- ログインID
- 初期/一時PW（伏せ字 + 表示/コピー）→ **サーバーで発行した値と同じ**に合わせる

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

