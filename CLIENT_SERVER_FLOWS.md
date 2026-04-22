# クライアントアプリ ↔ サーバー — フロー可視化

LP Builder（Windows）と PHP サーバ（`jitan.app` 想定）の役割と接点。  
**仕様の正はクライアントが生成するファイル**（`lp_meta.json`・`cms_credentials.json`）と **`lp_builder/`** 実装。**実装詳細**は `SERVER_SETUP.md` / `SERVER_CMS_SITE_SCOPING.md` / `lp_builder/README.md`。  
ドキュメントルートには **`cms/` が既にある**前提（新規作成手順の話ではない）。

---

## 全体像（片道）

```mermaid
flowchart LR
  subgraph C["クライアント: LP Builder"]
    A1[①入力〜③文章]
    A2[生成: site_key + lp_token]
    A3["custom/lp_meta.json\n+cms_credentials.json"]
    A4[④SFTP または手動]
    A5[編集URL・site_key・初期PW]
  end
  subgraph S["サーバー（既存 cms/）"]
    B1[静的配信 /site_key/]
    B2[lp_meta / 台帳（管理者経路）]
    B3["CMS: site-login または login"]
    B4[編集 session → content 保存]
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
  T3 --> T5["custom/lp_meta.json\n+cms_credentials.json"]
  T3 --> T6[index.html / 共有 CSS・JS]
  T4 --> T7[ローカルプレビュー]
  T7 --> T8[④ SFTP 設定]
  T8 --> T9[アップロード]
  T9 --> T10[公開URL・CMS情報表示]
  T5 -.->|同梱| T9
```

**サーバー非依存:** ①〜⑦設定・コストはローカル完結。生成と SFTP 以外に HTTP 必須なし。

---

## サーバー側フロー（認証の分岐）

**経路 A（LP 編集者）:** ブラウザで **`POST site-login.php`**（`site_key` + パスワード）→ `cms_credentials.json` 検証 → `must_change_password` なら変更 → `content` 編集。

**経路 B（管理者）:** **`users.json`** + **`login.php`** →（マルチ LP なら）**`select-site`** → `content` 編集。

```mermaid
flowchart TB
  SA[cms_credentials.json\nクライアント生成] --> A1[POST site-login]
  SB[users.json\nサーバー台帳] --> B1[POST login]
  A1 --> E[編集可セッション]
  B1 --> B2{マルチ LP?}
  B2 -->|yes| B3[select-site]
  B2 -->|no| E
  B3 --> E
  E --> C1[GET/PUT content 等]
```

---

## 両者の「接点」（データの行き方）

| 接点 | 方向 | 中身 |
|------|------|------|
| **SFTP** | Client → Server | ディレクトリ全体。`…/<site_key>/` 以下に `index.html`, `custom/lp_meta.json`, **`custom/cms_credentials.json`** 等 |
| **HTTPS 静的** | Server → 閲覧者 | `https://<host>/<site_key>/index.html` |
| **HTTPS CMS** | ブラウザ ↔ Server | **A:** `site-login` → content。**B:** `login` → `select-site` → content。EXE は CMS に直接 HTTP しない |
| **識別子** | 生成時にクライアントが決定 | `site_key` = フォルダ名。`lp_token` = `lp_meta.json` |
| **認証の正（A）** | **LP ディレクトリ内** | `cms_credentials.json`（ハッシュ）と `site_key`／`lp_token` の整合 |
| **認証の正（B）** | サーバー | `users.json` + 台帳・`allowed_site_keys` |

```mermaid
sequenceDiagram
  participant App as LP Builder
  participant SFTP as サーバ SFTP
  participant Web as サーバ HTTP
  participant Br as ブラウザ

  App->>App: 生成 + lp_meta + cms_credentials
  App->>SFTP: ツリーアップロード
  SFTP-->>Web: ファイル置場に反映
  Br->>Web: /site_key/ 閲覧
  Br->>Web: site-login または login
  Br->>Web: PUT content
  Note over App,Web: EXE は CMS に直接 HTTP しない
```

---

## 一言まとめ

- **クライアント**は「作る・資格情報を同梱する・上げる・手取り情報を出す」。
- **サーバー**は「既存の `cms/` で配信する・認証して save する」。**LP 編集者の ID は `users.json` に増やさず**、ディレクトリ内ファイルで検証する。
- ファイルの**同一性**は `site_key` / `lp_meta` / **`cms_credentials`**、**人の操作**はブラウザ CMS 経由。
