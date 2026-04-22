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
  - `POST /api/login.php`
  - `POST /api/logout.php`
  - `GET /api/content.php`
  - `PUT /api/content.php`
  - `POST /api/upload-image.php`（任意）
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

## 5) API Spec (MVP)

### `POST /cms/api/login.php`
- input: `{ "id": "...", "password": "..." }`
- success: `{ "ok": true }` + session発行
- fail: `{ "ok": false, "error": "invalid_credentials" }`

### `POST /cms/api/logout.php`
- session破棄
- return `{ "ok": true }`

### `GET /cms/api/me.php`
- ログイン状態確認
- return `{ "ok": true, "user": { "id": "lp-admin" } }`

### `GET /cms/api/content.php`
- `content.json` 返却（認証必須）

### `PUT /cms/api/content.php`
- `content.json` 更新（認証 + CSRFチェック）
- return `{ "ok": true, "updated_at": "..." }`

### `POST /cms/api/upload-image.php` (optional)
- multipart upload
- `custom/` に保存
- return `{ "ok": true, "file": "reason1_20260422.jpg" }`

---

## 6) Bootstrap Script (Initial Admin User)
Run once to create hash:

```bash
php -r 'echo password_hash("CHANGE_ME_TEMP_PASSWORD", PASSWORD_DEFAULT), PHP_EOL;'
```

Write hash to `cms/data/users.json`.

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
`④アップロード` に表示:
- 公開URL
- 編集URL（例: `https://example.com/cms/admin/`）
- ログインID
- 初期PW（伏せ字 + 表示/コピー）

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
- [ ] `/cms/admin` login works
- [ ] `/cms/api/content.php` GET/PUT works
- [ ] LP reflects `content.json`
- [ ] `cms/data/` is not web-accessible
- [ ] lock/rate limit works
- [ ] backup/restore tested

---

## 12) Operation Flow
1. LP Builder generates LP locally.
2. LP Builder uploads files via SFTP.
3. Editor opens `/cms/admin`, logs in.
4. Editor edits image/text and saves.
5. Server writes `content.json`.
6. Public LP renders updated content.

---

## Notes for Separate Cursor Session
- First build MVP only:
  - login/logout
  - content GET/PUT
- Keep schema simple (`images`, `texts`, `updated_at`)
- Add upload API and audit hardening after MVP verification.
