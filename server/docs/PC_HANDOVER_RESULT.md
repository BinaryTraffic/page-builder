# PC側連携用: サーバー作業結果（2026-04-23）

LP Builder / PC 担当向け。クライアントの Cursor 用の短い導線は `CLIENT_CURSOR_HANDOVER.md`、フロー図は `CLIENT_SERVER_FLOWS.md`。

---

## 1) 結論（使うURL・認証）

- 公開（LP）: `https://jitan.app/<site_key>/`（`site_key` = アップロード先ディレクトリ名）
- 編集URL: `https://jitan.app/cms/admin/`
- API: `https://jitan.app/cms/api/`
- ログイン: ID `lp-admin`、一時パス: `Whatisthepassword?`（**サーバ `users.json` のハッシュ元と同じ平文**）→ 初回必ず本番用へ変更
- マルチ LP: ログイン・パス変更のあと **`POST select-site.php`** で編集する LP を選び、その後 `content` GET/PUT。`?site_key=` では切替えない

---

## 2) サーバー側で揃っていること

- Apache / PHP、データ保護（`/cms/data/*` は 403）
- API: `login` / `logout` / `me` / `change-password` / **`select-site`** / `content` / `upload-image` / `register-site`（任意）
- 台帳: `cms/data/sites.json`、本文: `cms/data/sites/<lp_token>/content.json`、ユーザ: `allowed_site_keys`
- 管理 UI: `cms/admin/`
- 受動台帳取込: `php cms/bin/sync-sites-from-lp-meta.php /home/lp-tool`（`custom/lp_meta.json` 走査・任意の運用で実行）

---

## 3) 動作確認（サーバで実施可能な範囲）

- 管理 `GET /cms/admin/` `200` / `GET /admin` → `/cms/admin/` リダイレクト
- `me` 未ログイン 401
- ログイン直後: `me` → `content`（未 `select-site` かつパス未変更のときは 400/403 系が仕様通り）→ パス変更 → `select-site` → `content` GET/PUT

---

## 4) 結合テストで見る手順

1. LP 生成 → SFTP で `.../<site_key>/` へ
2. 台帳に LP がまだなら `register-site` またはサーバの `sync-sites` / 手動 `sites.json` + ユーザ `allowed_site_keys`
3. CMS: ログイン → 初回パス変更 → **LP 選択** → 編集保存
4. 公開ページが `content` を参照する作りなら反映確認（**参照は各 LP の `script` 等の責務**）

---

## 5) 注意

- 本番パスを MD に平文で残さない
- `cms/data` 公開を開かない
- API パスは常に `/cms/api/*`

最終更新: 2026-04-23
