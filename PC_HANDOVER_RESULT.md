# PC側連携用: サーバーとの接続前提（2026-04-23 更新）

このファイルは **LP Builder（PC）側**への連携用です。**仕様の主体はクライアント**（生成する `custom/` 以下）です。

---

## 1) PC側が使う値（URL）

- 公開 URL: `https://jitan.app/`
- 編集 URL: `https://jitan.app/cms/admin/`（可能なら **`?site_key=<出力フォルダ名>`** を付与）
- API ベース: `https://jitan.app/cms/api/`

---

## 2) ログインの考え方（2 系統）

### LP を編集する（納品先・通常）

- **サイトキー** = 出力フォルダ名（URL の `/<site_key>/` と一致）
- **パスワード** = LP 生成時に **`custom/cms_credentials.json`** に書き込んだ初期値と同じ（Builder ②「初期 PW」と一致させる）
- ブラウザでは管理画面から **`POST /cms/api/site-login.php`**（実装は `server/cms/`）。**ログイン ID は `lp_<token>` ではない**。

### サーバー運用管理者のみ（任意）

- **`POST /cms/api/login.php`** — ID 例: **`lp-admin`**
- 初期（一時）パスワードは **`cms/data/users.json`** のハッシュとペア。**LP ごとにユーザを増やす方式ではない**。

---

## 3) PC側で実施してほしいこと（優先）

- 生成に **`custom/cms_credentials.json`** を含める（リポジトリの `lp_builder` 実装に従う）
- ②に **編集 URL・site_key（フォルダ名）・初期 PW** を表示
- SFTP 後の結合テスト: **site-login** →（必要ならパス変更）→ 保存 → 公開反映

---

## 4) 注意

- 一時パスを平文で長期保管しない
- API は **`/cms/api/*`**
- サーバー側の実装の正はリポジトリ **`server/cms/`**（本番は別環境で追従）

---

最終更新: 2026-04-23（認証二系統・クライアント生成 credentials に整合）
