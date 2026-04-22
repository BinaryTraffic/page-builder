# PC側連携用: サーバー作業結果（2026-04-23）

このファイルは、PC側（LP Builder側）への連携情報です。  
サーバー側の実装・設定変更は完了しており、以下の前提でPC側の接続先を使用してください。

---

## 1) 結論（PC側が使う値）

- 公開URL: `https://jitan.app/`
- 編集URL: `https://jitan.app/cms/admin/`
- APIベース: `https://jitan.app/cms/api/`
- ログインID: `lp-admin`
- 一時（初回）パスワード: `Whatisthepassword?`（**サーバーの `users.json` ハッシュの元**と同じ平文にすること）
  - 初回ログイン後、必須のパスワード変更で本番用に更新する

---

## 2) サーバー側で完了した内容

- Apache vhost統一（`jitan.app`）
- `/admin` を `/cms/admin/` へリダイレクト
- PHP版CMS APIを実装
  - `login.php` / `logout.php` / `me.php` / `content.php` / `upload-image.php`
- 編集UIを実装
  - `cms/admin/index.html` + `main.js` + `style.css`
- データ保護を有効化
  - `/cms/data/*` 直アクセスは `403`
- 旧FastAPIサービスは停止・削除済み

---

## 3) 動作確認結果（サーバー側実施済み）

- `GET https://jitan.app/cms/admin/` -> `200 OK`
- `GET https://jitan.app/admin` -> `/cms/admin/` へ `302`
- `GET https://jitan.app/cms/data/content.json` -> `403 Forbidden`
- APIフロー:
  - `POST /cms/api/login.php` -> OK
  - `GET /cms/api/me.php` -> OK
  - `GET /cms/api/content.php` -> OK
  - `PUT /cms/api/content.php` -> OK

---

## 4) PC側で実施してほしい確認

- LP Builderの表示URLを以下へ統一
  - 編集URL: `https://jitan.app/cms/admin/`
- 初期ログイン情報の表示/コピー動線を確認
- SFTPアップロード後、以下を結合テスト
  1. CMSへログイン
  2. 画像/文言を編集
  3. 保存
  4. 公開LPへの反映確認

---

## 5) 注意事項

- 上記一時パスは初回ログイン専用。**変更後の本番パス**を平文でドキュメントに残さないこと
- `cms/data` の公開禁止設定を解除しないこと
- APIパスは必ず `/cms/api/*` を使用すること
