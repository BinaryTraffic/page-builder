# `content.json`（LP 編集データ）の形

サーバーは `cms/data/sites/<lp_token>/content.json` に保存する。  
**GET `/cms/api/content.php`** は欠損フィールドを既定で補う（**PUT 成功時にディスクへ正規化**）。

## トップレベル

| キー | 型 | 説明 |
|------|-----|------|
| `images` | object | 画像スロット（例: `hero` にファイル名文字列など） |
| `texts` | object | 文言（例: `hero_sub`, `hero_title`, `hero_desc`） |
| `created_at` | string | 初回作成日時（ISO 8601）。既存ファイルに無ければ初回 PUT で入る |
| `updated_at` | string | 最終更新日時（ISO 8601） |
| `updated_by` | string | 最後に保存した主体（監査用・例: `site:...` またはユーザ ID） |
| `meta` | object | 下記 |

## `meta`

| キー | 型 | 説明 |
|------|-----|------|
| `dirty` | bool | **未保存の編集がある**等の意味で使う想定。ディスクに **PUT 保存した直後は常に `false`** |
| `status` | string | 次のいずれか: `editing`（編集中） / `preview`（プレビュー扱い） / `deployed`（本番に反映済） |
| `section_dirty` | object | セクション ID → 真偽。例: `{ "hero": true }`。**成功した PUT 後は空オブジェクト**（全クリーン）に正規化 |

## ステータス遷移の例

- 編集・保存: `PUT` → `meta.dirty` は `false`、`meta.status` はリクエストの `meta.status` か維持（省略時は `editing`）
- プレビューにしたい: `PUT` の body に `meta: { "status": "preview" }`
- 本番デプロイ（`_lp_publish` 生成）成功時: サーバが `content.json` の `meta.status` を `deployed`、dirty / section_dirty をクリア

## クライアント（将来のオンページ編集）

- 指を離す前の **ローカル汚染**はブラウザ内で `dirty: true` / `section_dirty` を立て、**PUT 成功後**は JSON 上は再びクリーン。  
- `created_at` / `updated_at` は **保険・差分表示**用。

---

最終更新: 2026-04-23
