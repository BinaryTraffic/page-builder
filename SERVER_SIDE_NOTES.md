# サーバー側への伝達メモ（クライアント側から）

このファイルに、サーバー担当／サーバー側 Cursor に伝えたいことを**時系列で追記**していく。  
仕様の正は引き続き `CLIENT_CURSOR_HANDOVER.md` / `SERVER_SETUP.md` / `SERVER_CMS_SITE_SCOPING.md`。

---

## 書き方の例

```
### YYYY-MM-DD
- （依頼・質問・決定・デプロイ後の確認結果など）
```

---

## 記入欄

### 2026-04-23
- LP ごとに CMS ユーザー `lp_<24hex lp_token>` を台帳同期時に自動作成。初期パスは環境変数 `LP_SITE_INITIAL_PASSWORD`（未設定時 `Whatisthepassword?`）。**既存ディレクトリはデプロイ後に `sync-sites-from-lp-meta.php` を再実行してユーザーを埋める。**


---

## 固定リンク（貼り戻し用）

- リポ: `https://github.com/BinaryTraffic/page-builder`
- 手引き: 同梱 `CLIENT_CURSOR_HANDOVER.md` / `server/docs/` 内のコピーあり
