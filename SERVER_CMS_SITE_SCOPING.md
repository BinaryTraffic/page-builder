# CMS を LP 単位（site_key）に分離する — 参照仕様

最終更新: 2026-04-23  
前提: 静的は `…/<site_key>/` ＋ **`custom/lp_meta.json`**（およびクライアント生成の **`custom/cms_credentials.json`**）。詳細は `SERVER_SETUP.md`。

**読み替え:** LP 編集者は **`POST site-login.php`** で **`cms_credentials.json`** を検証する。**台帳 `sites.json` / `allowed_site_keys` / `select-site.php` は、主に `users.json` でログインした運用管理者向け**。

---

## やること（必須）

1. **`cms/data/sites.json`（名は任意）を新設**  
   各行: `lp_token`（主キー）, `site_key`, その LP 専用 `content.json` のパス（どちらか）  
   - 案A: `…/<site_key>/cms/data/content.json`  
   - 案B: `cms/data/sites/<lp_token>/content.json`

2. **ユーザに `allowed_site_keys` または `allowed_lp_tokens` を持たせる**（`users.json` 拡張可）。台帳にない・許可にない LP は**読み書き禁止**。

3. **`POST …/select-site.php`（仮名）**  
   body: `{ "site_key" }` → 台帳＋そのユーザの許可を検証 → OK ならセッションに `active_site_key`（＋ `active_lp_token`）保存。**GET の `?site_key=` だけで切替しない**。

4. **`content.php` / `upload-image.php`**  
   対象パスは**セッションの `active_site_key` のみ**。未設定なら `400` + `site_not_selected`。  
   クエリの `site_key` だけでは決めない。

5. **`me.php`**  
   応答に `allowed_site_keys` と `active_site_key` を入れる。

6. **台帳の入り方**（どちらか）  
   - デプロイ後に `public_html/* /custom/lp_meta.json` を走査して取り込み  
   - または `register-site` API（要ログイン・権限）で `lp_token` + `site_key` を登録

7. **監査ログ**  
   必ず `user` + `site_key`（＋ `lp_token` 任意）。

---

## セキュリティ

- **管理者経路:** `lp_meta.json` だけでは認めず、台帳と `allowed_site_keys` で許可する。  
- **`site-login` 経路:** `{DOCUMENT_ROOT}/{site_key}/custom/cms_credentials.json` とパスワード・`lp_token` 整合で許可する（別 LP のディレクトリには触れない）。  
- いずれの経路でも、**他サイトの `site_key` に越権保存しない**こと。

---

## 受け入れ

- [ ] LP が2つ以上あっても **content が混ざらない**  
- [ ] 許可のない `site_key` へ **API で触れない**  
- [ ] ログに **site_key** が残る

---

## LP Builder 側（主体）

- SFTP 先は従来どおり `…/<site_key>/`。生成時に **`custom/cms_credentials.json`** を同梱すること（**仕様の正はクライアント実装**）。
