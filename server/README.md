# サーバ側リソース（`jitan.app` 等へデプロイする PHP CMS）

- `cms/admin/` — 管理 UI（静的）
- `cms/api/` — `login` / `me` / `select-site` / `content` 等
- `cms/bin/` — 例: `sync-sites-from-lp-meta.php`（台帳取込）
- `docs/` — 設計・引き渡し用 Markdown

`cms/data/` は本番の秘密を置くため、リポジトリでは `.gitkeep` のみ。手順は `docs/SERVER_SETUP.md`。
