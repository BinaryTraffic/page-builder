# クライアント側 Cursor 向け: サーバー準備完了の連絡

**結論: サーバー側の準備は完了しています。**  LP Builder / クライアント作業用に Cursor に読ませる前提のメモです。

---

## 固定で使うURL

| 用途 | URL |
|------|-----|
| 公開 | `https://jitan.app/`（直下は `index.html` が無いと 403/一覧なし。LP は `https://jitan.app/<site_key>/`） |
| 管理画面 | `https://jitan.app/cms/admin/` |
| API | `https://jitan.app/cms/api/` 配下（後述） |

---

## 認証（必ずこの順）

1. `POST /cms/api/login.php` — body: `{ "id", "password" }`  
   - 初期: ID `lp-admin`、サーバー固定の一時パス `Whatisthepassword?`（初回は変更必須の運用）
2. 応答 `must_change_password: true` のとき、先に `POST /cms/api/change-password.php`（要 CSRF、12 文字以上の新パス）
3. **LP 単位の切替**は `GET ?site_key=...` では**しない**  
   - `POST /cms/api/select-site.php` — body: `{ "site_key": "連番ディレクトリ名" }`、ヘッダ `X-CSRF-Token: <me の csrf>`
4. 以降 `GET/PUT /cms/api/content.php` など。未選択のときは `400` + `site_not_selected`

**CSRF:** `me.php` または login の応答の `csrf` を、書き込み系の `X-CSRF-Token` に付ける。

---

## LP 単位（site_key）の前提

- 静的の置き場は従来どおり SFTP: `…/<site_key>/`（Builder 変更不要、という前提）
- サーバー台帳 `cms/data/sites.json` + 各ユーザ `allowed_site_keys` で、**触っていい site_key だけ**が分かれる
- 各 LP の編集用 JSON 本文はサーバー内 `cms/data/sites/<lp_token>/content.json`（**ブラウザから直リンクしない**。`/cms/data/*` は 403）
- 詳細仕様: リポ内 `SERVER_CMS_SITE_SCOPING.md` / 運用の全体: `SERVER_SETUP.md`

---

## API 一覧（接続先が必要ならこの表）

- `POST login.php` / `POST logout.php`
- `GET me.php` — `allowed_site_keys`, `active_site_key`, `sites`（接続可 LP の一覧）
- `POST change-password.php`
- `POST select-site.php` — アクティブ LP をセッションに保存
- `GET` / `PUT content.php` — 編集用 JSON
- `POST upload-image.php`（任意）— 保存先は `…/<site_key>/custom/`
- `POST register-site.php`（管理用・必要なら）— 新 LP を台帳＋ allowed に取り込み

---

## クライアント側（Cursor / アプリ）でやるとよいこと

- ②アップロード等に **編集URL** `https://jitan.app/cms/admin/`、**ID/初期パス**の表示を既存方針どおり維持
- 初回以降、**実際のログイン**は「サーバーの一時パス or 変更後の本番パス」に揃えているか確認
- 結合テスト: ログイン（→必要ならパス変更）→ **LP 選択** → 文言保存 → 公開側反映

---

## 参照 MD（リポ同梱）

- `PC_HANDOVER_RESULT.md` — PC 担当向けの短い要約
- `SERVER_SETUP.md` — 全体設計とサーバ作業ログ
- `SERVER_CMS_SITE_SCOPING.md` — LP 分離（site_key）の仕様
- `SERVER_TASKS.md` — サーバ担当向けチェックリスト

---

最終更新: 2026-04-23 05:53:08 +09:00
