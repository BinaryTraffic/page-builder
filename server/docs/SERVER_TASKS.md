# サーバー側作業指示（実施依頼）

最終更新: 2026-04-23 05:53:08 +09:00

このドキュメントは、サーバー担当者向けの実施指示です。  
詳細仕様は `SERVER_SETUP.md`（特に **4.1 初期パスワード＋初回変更強制**、API 仕様）を参照し、本書は「何を・どこまで・どう報告するか」を明確化します。

クライアントとの連絡ルール（コミットの付け方・Issue の使い方）は **`GIT_WORKFLOW.md`** を参照。

---

## 0. 前提

- 対象ドメイン: `jitan.app`
- CMSルート: `/cms/admin/`
- APIルート: `/cms/api/`
- データ保存: `/home/lp-tool/cms/data/`

---

## 1. サーバー側 作業項目（必須）

### 1-1. Web/API到達確認

- [ ] `https://jitan.app/cms/admin/` が `200` で表示される
- [ ] `https://jitan.app/admin` が `/cms/admin/` へリダイレクトされる
- [ ] `https://jitan.app/cms/api/me.php` が未ログイン時に適切エラーを返す

### 1-2. データ保護

- [ ] `https://jitan.app/cms/data/content.json` が `403` になる
- [ ] `https://jitan.app/cms/data/users.json` が `403` になる
- [ ] Apache/Nginx 設定で `/cms/data/*` の公開が禁止されている

### 1-3. 認証・セッション

- [ ] サーバーで一時初期パスワードを `users.json`（ハッシュ + `must_change_password: true`）に登録し、その平文をテスト用に控える
- [ ] `lp-admin` ＋上記一時パスでログイン成功（`login` 応答に `must_change_password: true`）
- [ ] 初回は編集前に `change-password`（または管理画面）で本番用へ変更し、`me` で `must_change_password: false` になる
- [ ] 変更前は `GET/PUT content` 等が `password_change_required` 等で拒否される
- [ ] ログアウト後に `me.php` が未認証になる
- [ ] Cookie設定が有効（HttpOnly / Secure / SameSite）
- [ ] ログイン失敗ロック（5回失敗→10分ロック）を確認

### 1-3b. サイト一意 ID（`lp_meta.json` / 台帳）

- [ ] 各デプロイされた LP ディレクトリに `custom/lp_meta.json` が含まれる（`lp_token` / `site_key`）
- [ ] `cms/data/sites.json` と `users.allowed_site_keys` が揃う（手動 or `register-site` or `php cms/bin/sync-sites-from-lp-meta.php`）

### 1-3c. LP 単位スコープ（`SERVER_CMS_SITE_SCOPING.md`）

- [ ] `POST /cms/api/select-site.php` で `active_site_key` が付く
- [ ] 未 `select` の `GET/PUT content` は `site_not_selected` 等
- [ ] 許可のない `site_key` を選べない / `site_forbidden`
- [ ] 監査 `audit.log` に `site_key` が残る
- [ ] クライアント: `CLIENT_CURSOR_HANDOVER.md` / `PC_HANDOVER_RESULT.md` を配布

### 1-4. コンテンツ保存API

- [ ] パス変更済み かつ `select-site` 済みで `GET /cms/api/content.php` が成功する
- [ ] 同条件で `PUT /cms/api/content.php` で更新できる
- [ ] 更新後に公開LPへ反映される
- [ ] `audit.log` に記録される

### 1-5. バックアップ

- [ ] 以下のバックアップを定期実行する
  - `cms/data/sites.json`
  - `cms/data/sites/`
  - `cms/data/users.json`
  - `cms/data/audit.log`
  - `cms/data/login_attempts.json`
- [ ] 復元テストを1回実施する

---

## 2. ローカルアプリとの結合テスト（必須）

サーバー単体確認後、ローカルアプリ担当と結合テストを実施する。

- [ ] ローカルアプリでLP生成
- [ ] SFTPアップロード完了（連番ディレクトリ）
- [ ] アプリ表示の編集URLからCMSへログイン（**一時パスはサーバー登録と同じ値**）
- [ ] 初回パスワード変更（サーバー方針どおり）のあと、CMSで画像/文言を編集して保存
- [ ] 公開ページに反映される

---

## 3. セキュリティ運用（必須）

- [ ] 一時パスワードの発行元は**サーバー**（平文をドキュメントに残さない）
- [ ] 初回ログイン後、必須のパスワード変更フローで本番用へ更新（`must_change_password` 解除を確認）
- [ ] TLS証明書の更新期限を確認
- [ ] Apache/PHPエラーログに重大エラーがないことを確認

---

## 4. 作業完了時の報告フォーマット

以下のテンプレートで報告してください。

```md
## サーバー作業報告（YYYY-MM-DD）

### 実施内容
- 

### 確認結果
- /cms/admin/: [OK/NG]
- /cms/data/content.json block(403): [OK/NG]
- initial temp PW + `must_change_password` flow: [OK/NG]
- select-site + content GET/PUT: [OK/NG]
- lock(5 failures/10min): [OK/NG]
- backup/restore test: [OK/NG]

### 変更ファイル
- 

### 残課題
- 
```

---

## 5. 注意事項

- 本番パスワードをドキュメントに平文で残さないこと
- `cms/data` のアクセス禁止設定を解除しないこと
- API仕様を変更した場合は、必ず `SERVER_SETUP.md` に反映すること
- PC側引き継ぎ: `PC_HANDOVER_RESULT.md`、クライアント Cursor: `CLIENT_CURSOR_HANDOVER.md`
