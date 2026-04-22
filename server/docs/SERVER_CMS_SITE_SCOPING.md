# サーバー作業指示: CMS を LP 単位（site_key）に分離する

最終更新: 2026-04-23 05:53:08 +09:00
前提: 静的は `…/<site_key>/` ＋ `custom/lp_meta.json`。詳細は `SERVER_SETUP.md`。

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

6. **台帳の入り方**（いずれか）  
   - **実装済（CLI）**: `sudo -u www-data php /home/lp-tool/cms/bin/sync-sites-from-lp-meta.php /home/lp-tool`（`<docroot>/<site_key>/custom/lp_meta.json` 走査 → `sites.json` マージ）  
   - または `POST /cms/api/register-site.php`（要ログイン・`can_register_sites`）で `lp_token` + `site_key` を登録

7. **監査ログ**  
   必ず `user` + `site_key`（＋ `lp_token` 任意）。

---

## セキュリティ

- クライアントの `lp_meta.json` だけ**では認可しない**（台帳はサーバー管理が正）。  
- 他ユーザの `site_key` へ**保存・読取できない**こと。

---

## 受け入れ（実装基準。本番手動で最終確認）

- [x] LP が2つ以上あっても **content が混ざらない**（本文は `sites/<lp_token>/content.json`）  
- [x] 許可のない `site_key` へ **select / content で触れない**  
- [x] ログ（`audit`）に **site_key**（＋ `lp_token` 任意）が付く

---

## LP Builder 側

- **変更不要**（SFTP 先は従来どおり `…/<site_key>/`）
