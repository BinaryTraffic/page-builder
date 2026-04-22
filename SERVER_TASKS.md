# サーバー側作業指示（検証・追従）

最終更新: 2026-04-23（サイトログイン・クライアント主体に整合）

このドキュメントは**サーバー担当者向け**です。ドキュメントルートには **`cms/` が既にある**前提です。やることは「新規にツリーを置く」ではなく、**リポジトリの `server/cms/` と実機の差分をなくす・次の検証を通す**ことです。詳細仕様は `SERVER_SETUP.md` を参照してください。

---

## 0. 前提

- 対象ドメイン: `jitan.app`
- CMS ルート: `/cms/admin/`（既存）
- API ルート: `/cms/api/`（既存）
- データ保存: `/home/lp-tool/cms/data/`（実パスは環境に合わせる）

**役割分担:** LP ごとの編集パスワードの**生成元はクライアント**（`custom/cms_credentials.json` を SFTP で載せる）。サーバーは **`users.json` に LP 専用ユーザを増やさず**、`site-login.php` でファイル検証する実装と一致させる。

---

## 1. サーバー側 作業項目（必須）

### 1-1. Web/API 到達確認

- [ ] `https://jitan.app/cms/admin/` が `200` で表示される
- [ ] `https://jitan.app/admin` が `/cms/admin/` へリダイレクトされる（運用している場合）
- [ ] `https://jitan.app/cms/api/me.php` が未ログイン時に適切エラーを返す

### 1-2. データ保護

- [ ] `https://jitan.app/cms/data/` 配下が **403**（直リンク不可）
- [ ] Apache/Nginx で `/cms/data/*` が公開されない

### 1-3. 認証・セッション（2 系統）

**A. LP 編集者（`site-login.php`）**

- [ ] テスト用 LP ディレクトリに **`custom/cms_credentials.json`** と **`custom/lp_meta.json`** がある（クライアント生成物または同等）
- [ ] **`POST /cms/api/site-login.php`** — `{ "site_key", "password" }` で成功し、`GET me.php` が `auth: "site"` を返す
- [ ] `must_change_password: true` のとき、編集 API が `password_change_required` で拒否される
- [ ] **`POST change-password.php`** で **`cms_credentials.json`** のハッシュが更新される（平文がディスクに残らないこと）

**B. 運用管理者（`login.php`）**

- [ ] `cms/data/users.json` に **`lp-admin`**（または運用 ID）がハッシュで存在する
- [ ] **`POST /cms/api/login.php`** でログイン成功
- [ ] マルチ LP 時 **`POST select-site.php`** で `active_site_key` が設定され、その後 `GET/PUT content` が通る
- [ ] **サイト認証セッションで `select-site` が拒否される**（実装どおり）ことを把握する

**共通**

- [ ] ログアウト後に `me.php` が未認証になる
- [ ] Cookie（HttpOnly / Secure / SameSite）が意図どおり
- [ ] 管理者ログイン失敗ロック（例: 5 回 / 10 分）が仕様どおりなら確認

### 1-3b. `lp_meta.json` と台帳

- [ ] デプロイ済み LP に `custom/lp_meta.json` がある（`lp_token` / `site_key`）
- [ ] **管理者経路**で台帳と整合が必要な運用なら、`sites.json` と `register-site` / 同期スクリプトの状態を確認（**サイトログイン経路はファイルが正**）

### 1-4. コンテンツ保存 API

- [ ] **`GET` / `PUT /cms/api/content.php`** が、**A または B のいずれかの正当なセッション**で成功する
- [ ] 更新後に公開 LP 側の表示と整合する（運用どおり）
- [ ] `audit.log` に記録される

### 1-5. バックアップ

- [ ] 以下を定期バックアップ（パスは環境に合わせる）
  - `cms/data/users.json`、`sites.json`、`audit.log`、`login_attempts.json`
  - **`cms/data/sites/<lp_token>/content.json`**（LP ごとの編集データ）
- [ ] 復元テストを 1 回実施する

---

## 2. ローカルアプリとの結合テスト（必須）

- [ ] ローカルで LP 生成（**`cms_credentials.json` 同梱**）
- [ ] SFTP で **`…/<site_key>/` 一式**を反映
- [ ] 編集 URL（`?site_key=` 付き）から **`site-login`** でログイン → 編集・保存
- [ ] 公開ページに反映される

---

## 3. セキュリティ運用（必須）

- [ ] 本番パスワードをドキュメントに平文で残さない
- [ ] TLS 証明書の期限を確認
- [ ] PHP/ウェブサーバーログに異常がないことを確認

---

## 4. 作業完了時の報告フォーマット

```md
## サーバー作業報告（YYYY-MM-DD）

### 実施内容
- 

### 確認結果
- /cms/admin/: [OK/NG]
- /cms/data/* block(403): [OK/NG]
- site-login（cms_credentials）: [OK/NG]
- login（lp-admin）+ select-site（該当時）: [OK/NG]
- change-password（サイト / 管理者）: [OK/NG]
- content GET/PUT: [OK/NG]
- backup/restore test: [OK/NG]

### 変更ファイル（リポジトリ追従の場合）
- 

### 残課題
- 
```

---

## 5. 注意事項

- **クライアントが主体で変える契約**（生成ファイルの形式）と矛盾するサーバー独自改変をしないこと
- `cms/data` のアクセス禁止設定を解除しないこと
- API 仕様を変えた場合は **`SERVER_SETUP.md`** と **`CLIENT_CURSOR_HANDOVER.md`** に反映すること
- PC 側の短い要約は **`PC_HANDOVER_RESULT.md`**
