# LP Builder — ランディングページ自動生成ツール

4項目を入力するだけでランディングページを自動生成するWindowsデスクトップアプリです。

## 必要なもの

- **Windows 10/11**
- **Python 3.9 以上**（https://www.python.org/downloads/）
- **Anthropic APIキー**（https://console.anthropic.com/）

## インストール・起動手順

```powershell
# 1. このフォルダをWindowsにコピー（例: C:\Users\hshim\LP_Builder\）

# 2. ライブラリをインストール
pip install -r requirements.txt

# 3. アプリを起動
python lp_builder.py
```

## 使い方

### ① 基本情報タブ
| 項目 | 内容 |
|------|------|
| 業種 | ドロップダウンから選択 |
| カラー | アクセントカラーを選択 |
| 店舗名・住所・電話など | 入力（空欄は自動補完） |

### ② サービスタブ
- 提供するサービスを3〜6項目入力
- 空欄は業種に合わせてAIが自動補完

### ③ 推しポイントタブ
- 選ばれる理由を最大3つ入力
- タイトル・説明・特徴3つを入力

### ⚙ 設定タブ
- **APIキー**: Anthropic Console で取得したキーを入力
- **出力先フォルダ**: 生成されたLPの保存先
- **共有ファイル元**: style.css / script.js / pexels.js のコピー元

### 生成ボタン
「▶ LP を生成する」をクリックすると：
1. INPUT_SHEET.md を生成・保存
2. Claude API に送信
3. index.html を生成・保存
4. style.css / script.js / pexels.js をコピー
5. ブラウザで自動プレビュー

## 出力ファイル構成

```
出力先フォルダ/
└── サイト名_20260414_123456_<lp_token>/
    ├── INPUT_SHEET.md   ← 入力内容の記録
    ├── index.html       ← 生成されたLP
    ├── style.css        ← デザイン（共有）
    ├── script.js        ← インタラクション（共有）
    ├── pexels.js        ← 画像自動取得（共有）
    └── custom/
        ├── lp_meta.json ← lp_token / site_key（サーバー側でサイト識別用）
        └── config.json  ← 任意（顧客画像差し替え時）
```

`<lp_token>` は 24 桁の十六進（一意 ID）。フォルダ名全体が `site_key` で、公開 URL のパスおよび SFTP のリモートディレクトリ名と一致します。

## ファイル構成

```
lp_builder/
├── lp_builder.py       ← メインGUIアプリ（これを起動）
├── api_client.py       ← Claude API連携
├── prompt_template.py  ← プロンプト・業種定義
├── requirements.txt    ← 依存ライブラリ
└── README.md           ← このファイル
```

## 設定の保存場所

APIキーと出力先フォルダは `%USERPROFILE%\.lp_builder_config.json` に保存されます。
