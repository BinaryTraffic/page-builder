# クライアントアプリ ↔ サーバー — フロー可視化

LP Builder（Windows）と PHP サーバ（`jitan.app` 想定）の役割と接点。  
**実装詳細**は `SERVER_SETUP.md` / `SERVER_CMS_SITE_SCOPING.md` / `lp_builder/README.md`。

---

## 全体像（片道）

```mermaid
flowchart LR
  subgraph C["クライアント: LP Builder"]
    A1[①入力〜③文章]
    A2[生成: site_key + lp_token]
    A3[custom/lp_meta.json]
    A4[④SFTP または手動]
    A5[編集URL・ID・一時PW 表示]
  end
  subgraph S["サーバー"]
    B1[静的配信 /site_key/]
    B2[lp_meta 取込 or 台帳]
    B3[CMS ログイン]
    B4[LP 選択 → content 保存]
  end
  A1 --> A2 --> A3
  A3 --> A4
  A4 -->|ファイル配置| B1
  A4 -->|同梱| B2
  A5 -->|ブラウザで開く| B3
  B3 --> B4
  B1 -->|閲覧| B3
```

---

## クライアント（LP Builder）内フロー

```mermaid
flowchart TB
  T1[① 基本・業種 等] --> T2[② 画像 ③ 文章]
  T2 --> T3[▶ 生成]
  T3 --> T4["出力フォルダ: site_name_日時_lp_token"]
  T3 --> T5["custom/lp_meta.json\nlp_token, site_key, generated_at"]
  T3 --> T6[index.html / 共有 CSS・JS]
  T4 --> T7[ローカルプレビュー]
  T7 --> T8[④ SFTP 設定]
  T8 --> T9[アップロード]
  T9 --> T10[公開URL・CMS情報表示]
  T5 -.->|同梱| T9
```

**サーバー非依存:** ①〜⑦設定・コストはローカル完結。生成と SFTP 以外に HTTP 必須なし。

---

## サーバー側フロー（初回オペ＋日常編集）

```mermaid
flowchart TB
  S0[users.json: 一時PW ハッシュ\nmust_change_password] --> S1[ブラウザ /cms/admin/]
  S1 --> S2[login]
  S2 --> S3{must_change_password?}
  S3 -->|yes| S4[パスワード変更]
  S4 --> S5[編集可]
  S3 -->|no| S5
  S5 --> S6[select-site: active_site_key]
  S6 --> S7[GET/PUT content 等\nその LP 専用 content.json]
  S7 --> S8[静的 /site_key/ が反映]
```

**前提:** マルチ LP 時は `SERVER_CMS_SITE_SCOPING.md` どおり、台帳＋ `allowed_site_keys` ＋セッションの `active_site_key`。

---

## 両者の「接点」（データの行き方）

| 接点 | 方向 | 中身 |
|------|------|------|
| **SFTP** | Client → Server | ディレクトリ全体。`…/<site_key>/` 以下に `index.html`, `custom/lp_meta.json` 等 |
| **HTTPS 静的** | Server → 閲覧者 | `https://<host>/<site_key>/index.html` |
| **HTTPS CMS** | ブラウザ ↔ Server | ログイン・`select-site`・`content.php`。クライアント EXE とは別経路（人がブラウザ） |
| **識別子** | 生成時にクライアントが決定 | `site_key` = フォルダ名。`lp_token` = `lp_meta.json`（サーバー台帳と突合可） |
| **認証** | サーバーの正 | ログイン ID/PW は `users.json`（LP Builder 表示欄は手元メモ。同期は人間 or 将来 API） |

```mermaid
sequenceDiagram
  participant App as LP Builder
  participant SFTP as サーバ SFTP
  participant Web as サーバ HTTP
  participant Br as ブラウザ

  App->>App: 生成 + lp_meta
  App->>SFTP: ツリーアップロード
  SFTP-->>Web: ファイル置場に反映
  Br->>Web: /site_key/ 閲覧
  Br->>Web: /cms/admin ログイン
  Br->>Web: select-site → PUT content
  Note over App,Web: EXE は CMS に直接 HTTP しない
```

---

## 一言まとめ

- **クライアント**は「作る・上げる・手取り情報を出す」。
- **サーバー**は「配信する・誰がどの LP を編集するか決めて save する」。
- ファイルの**同一性**は `site_key` / `lp_meta`、**人の操作**はブラウザ CMS 経由。
