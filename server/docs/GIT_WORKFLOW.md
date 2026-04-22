# Git でクライアント ⇄ サーバーのやり取りを短くする

**目的:** メールや口頭だけに頼らず、**この GitHub リポジトリひとつ**で「何が正しいか」を共有する。

---

## 1. フォルダの意味（ここだけ覚える）

| フォルダ | だれのものか |
|----------|----------------|
| `lp_builder/` | クライアント（Windows LP Builder） |
| `server/` | サーバー（PHP の CMS と、その説明用 Markdown） |

---

## 2. みんなで守る約束（4 つ）

1. **決まりごとは Git に書く**  
   リポジトリに無い変更は「まだ無い」と同じ扱いにする。

2. **コミットの一行目**に、向き先が分かる語を付ける（おすすめ）  
   - `client:` … クライアント側だけ  
   - `server:` … サーバー側だけ  
   - `docs:` … 説明文だけ  

3. **URL・API・画面の動きを変えたら**、下の「触るファイル」の表を見て、**説明書も同じコミットで直す**。

4. **依頼・不具合**は、**まずクライアント側が** **GitHub の Issue** を立てる（タイトルは短く。本文に再現手順があれば尚よい）。  
   テンプレート: **「New issue」→「クライアント⇄サーバー連絡」**（`.github/ISSUE_TEMPLATE/`）。  
   サーバー担当は、対応内容を **同じリポジトリのコミット**で示し、必要なら Issue を閉じる。  
   Issue がどうしても使えないときだけ、`server/docs/SERVER_TASKS.md` の末尾に **日付＋一行** を足してコミットする（補助ルート）。

---

## 3. 仕様を変えたときに触るファイル（目安）

| 変えた内容 | クライアント側 | サーバー側 |
|------------|------------------|------------|
| 編集 URL・`?site_key=` など | `lp_builder/` のコード、`CLIENT_CURSOR_HANDOVER.md` | `server/cms/admin/`、`docs/SERVER_SETUP.md` |
| API のパス・POST の中身 | クライアントが API を叩くならそのコード | `server/cms/api/*.php`、`SERVER_SETUP.md`、`SERVER_CMS_SITE_SCOPING.md` |
| 台帳・LP の切り分け | `custom/lp_meta.json` の前提を変えるなら README 等 | `SERVER_CMS_SITE_SCOPING.md`、`cms/bin/` |

---

## 4. 「これ読んで」と送るときの最短パス

| 相手 | まず開いてもらうファイル |
|------|---------------------------|
| サーバー担当 | `server/docs/SERVER_SETUP.md` |
| クライアント担当 | `CLIENT_CURSOR_HANDOVER.md`（リポジトリ直下または `server/docs/` の同内容） |
| 全体の流れだけ | `server/docs/CLIENT_SERVER_FLOWS.md` |

---

## 5. このドキュメント自体

変更したらコミット例: `docs: clarify Git workflow for client/server`

最終更新: 2026-04-23（起票はクライアント側主導で Issue 優先、と明文化）
