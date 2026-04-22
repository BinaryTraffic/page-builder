# クライアント側 Cursor 向け: サーバー連携の「正」

**読み方**

- **仕様の主体はクライアント側**です。LP Builder が生成する **`custom/lp_meta.json`**・**`custom/cms_credentials.json`** と、リポジトリ内の **`lp_builder/`** 実装が**納品・認証情報の正**です。
- 本番ドキュメントルートには **`cms/` が既にある**前提で書きます（「これから `cms/` を新規に作って置く」という意味ではありません）。サーバー側 PHP の実装はリポジトリの **`server/cms/`** と一致させる（サーバー環境では別 Cursor が追従する場合があります）。

---

## 固定で使う URL

| 用途 | URL |
|------|-----|
| 公開 | `https://jitan.app/`（直下は `index.html` が無いと 403/一覧なし。LP は `https://jitan.app/<site_key>/`） |
| 管理画面 | `https://jitan.app/cms/admin/`（LP Builder からは `?site_key=<フォルダ名>` 付きで開く） |
| API | `https://jitan.app/cms/api/` 配下（後述） |

---

## 認証（2 系統 — 混同しないこと）

### A. LP 編集者（通常の納品先）— **ファイルの正はクライアント生成物**

1. 同一 LP ディレクトリに **`custom/lp_meta.json`**（`lp_token` / `site_key`）と **`custom/cms_credentials.json`**（`password_hash`・`lp_token`・`must_change_password` 等）が同梱される（**LP ごとに `users.json` にアカウントを増やさない**方式）。
2. **`POST /cms/api/site-login.php`** — body: `{ "site_key": "<出力フォルダ名>", "password": "<平文>" }`  
   - サーバーは **`{DOCUMENT_ROOT}/{site_key}/custom/cms_credentials.json`** を読み **`password_verify`**。可能なら **`lp_meta.json` の `lp_token`** と整合確認。
3. 応答で `must_change_password: true` のとき、先に **`POST /cms/api/change-password.php`**（要 CSRF、新パス 12 文字以上）。**サイト認証時はディスク上の `cms_credentials.json` が更新される**。
4. 以降 **`GET` / `PUT /cms/api/content.php`** 等。**この経路では `select-site` は使わない**（画面の `?site_key=` は入力補助。セッションに active が入るのは `site-login` の結果）。

**CSRF:** `me.php` または `site-login` / `login` 応答の `csrf` を、書き込み系の `X-CSRF-Token` に付ける。

### B. 運用スーパーユーザ（`users.json`）— 任意

1. **`POST /cms/api/login.php`** — body: `{ "id": "lp-admin", "password": "..." }`（**台帳: `cms/data/users.json`**）。
2. マルチ LP では **`POST /cms/api/select-site.php`**（body: `{ "site_key": "..." }`、ヘッダ `X-CSRF-Token`）。**GET の `?site_key=` だけでは切り替わらない**。
3. 未選択のとき編集 API は `400` + `site_not_selected`。

---

## LP 単位（site_key）の前提

- 静的の置き場は従来どおり SFTP: **`…/<site_key>/`**（フォルダ名＝`site_key`）。
- **台帳 `cms/data/sites.json` と `allowed_site_keys`** は、主に **B（管理者ログイン）** で「誰がどの LP を触れるか」を区切るために使う。**A（サイトログイン）では LP 直下の資格情報ファイルが認証の正**。
- 各 LP の編集用 JSON 本文はサーバー内 **`cms/data/sites/<lp_token>/content.json`**（ブラウザから直リンクしない。**`/cms/data/*` は 403**）。
- 詳細: `SERVER_CMS_SITE_SCOPING.md` / `SERVER_SETUP.md`

---

## API 一覧（接続先が必要ならこの表）

| 経路 | 主なエンドポイント |
|------|-------------------|
| **A（LP 編集者）** | `POST site-login.php`、`GET me.php`、`POST change-password.php`、`GET`/`PUT content.php`、`POST upload-image.php` |
| **B（管理者）** | `POST login.php`、`POST logout.php`、`GET me.php`、`POST select-site.php`、`POST change-password.php`、`GET`/`PUT content.php`、`POST register-site.php`（台帳取り込み・任意） |

---

## クライアント側（Cursor / LP Builder）で優先すること

- 生成・SFTP 対象に **`custom/cms_credentials.json`** を含めること（初期 PW は ② の表示と一致）。
- ②に **編集 URL**（`https://jitan.app/cms/admin/?site_key=...`）、**site_key（フォルダ名）**、**初期パス**を表示する。
- 結合テスト: **site-login**（→ 必要ならパス変更）→ 文言保存 → 公開側反映。

---

## Git での連携（やり取りを短く）

依頼や変更の「正」は **このリポジトリのコミットと Markdown** にまとめる。共通ルールは **`server/docs/GIT_WORKFLOW.md`**（パスが無い場合はリポジトリ内を確認）。

---

## 参照 MD（リポ同梱）

- `PC_HANDOVER_RESULT.md` — PC 担当向けの短い要約
- `CLIENT_SERVER_FLOWS.md` — クライアント ↔ サーバーのフロー
- `SERVER_SETUP.md` — 全体設計（サーバー側詳細）
- `SERVER_CMS_SITE_SCOPING.md` — LP 分離（site_key）
- `SERVER_TASKS.md` — サーバー担当向けチェックリスト（検証観点）

---

最終更新: 2026-04-23（認証二系統・クライアント主体に整合）
