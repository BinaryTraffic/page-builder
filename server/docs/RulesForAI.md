# LP Builder サーバー — Cursor開発指示

## あなたの役割

クライアントアプリ（Windows EXEアプリ）が生成したランディングページを  
受け取り・ホスティングするサーバーを構築してください。  
クライアントの仕様に**合わせる側**です。独断でインターフェースを変えないこと。

---

## クライアントアプリの概要（参照元）

**リポジトリ**: https://github.com/BinaryTraffic/page-builder  
**動作環境**: Windows / Python + tkinter  
**処理内容**: Claude APIでHTMLランディングページを自動生成 → サーバーへ送信

---

## クライアントが送ってくるもの（固定仕様）

### ディレクトリ構造
{site_name}_{timestamp}/
├── index.html ← メインLP（Claude生成）
├── style.css ← テーマスタイル
├── script.js ← 共有スクリプト
├── pexels.js ← 画像取得スクリプト
├── INPUT_SHEET.md ← 生成パラメータ記録（管理用）
└── custom/
└── config.json ← 画像スロット設定


### site_name の形式
- 店舗名等から生成されるサニタイズ済み文字列
- 例: `yamada_dental_20250423_143022`

---

## サーバーが実装すべきAPI

### 1. ファイルアップロード
POST /api/upload
Content-Type: multipart/form-data

パラメータ:

site_dir: フォルダ名（例: yamada_dental_20250423_143022）
files[]: フォルダ内の全ファイル（パス情報付き）
api_key: 認証キー（ヘッダー or ボディ）
レスポンス（JSON）:
{
"success": true,
"url": "https://yourdomain.com/sites/yamada_dental_20250423_143022/",
"site_id": "xxxx"
}

### 2. アップロード済みサイト一覧
GET /api/sites
Authorization: Bearer {api_key}

レスポンス（JSON）:
{
"sites": [
{
"site_id": "xxxx",
"site_dir": "yamada_dental_20250423_143022",
"url": "https://yourdomain.com/sites/yamada_dental_20250423_143022/",
"created_at": "2025-04-23T14:30:22Z"
}
]
}


### 3. サイト削除（オプション）
DELETE /api/sites/{site_id}
Authorization: Bearer {api_key}

レスポンス（JSON）:
{ "success": true }


---

## サーバー技術スタック

| 項目 | 内容 |
|------|------|
| 環境 | GCP Linux |
| 言語 | PHP |
| フロント | HTML / CSS / JavaScript |
| データ管理 | JSON ファイル or MySQL（要選択） |
| 認証 | APIキー方式（Bearer Token） |

---

## ファイル配置ルール
/var/www/html/＜＝適宜実情に合わせること
├── api/
│ ├── upload.php
│ ├── sites.php
│ └── auth.php
├── sites/ ← アップロードされたLPを配置
│ └── {site_name}_{timestamp}/
│ ├── index.html
│ ├── style.css
│ └── ...
└── admin/ ← 管理画面（オプション）


---

## 実装上の制約（クライアント側との約束）

- レスポンスは必ず **JSON形式**
- `success: true/false` を必ず含める
- エラー時は `{ "success": false, "error": "メッセージ" }`
- アップロードされた `index.html` はそのまま配信（PHPで書き換えない）
- `INPUT_SHEET.md` は公開ディレクトリに置かない（管理用として別保存）
- CORS許可: クライアントアプリからのPOSTを受け入れる

---

## 未決事項（クライアント側と合意が必要）

- [ ] 認証APIキーの発行・管理方法
- [ ] アップロードサイズ上限（現状のLPは概ね1MB以内）
- [ ] 同名サイトの上書き可否
- [ ] HTTPSの証明書設定

---

## 開発優先順位

1. `POST /api/upload` の実装（最優先）
2. 静的ファイル配信の確認（index.htmlが正しくブラウザで開くか）
3. `GET /api/sites` の実装
4. 認証の実装
5. 管理画面（余裕があれば）