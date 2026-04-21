"""
LP生成プロンプトテンプレート
INPUT_SHEETの内容をClaude APIへ渡すプロンプトを組み立てる
"""

# 業種キーマッピング（GUI選択肢 → data-industry属性値）
INDUSTRY_KEYS = {
    "ペットサロン":         "pet_salon",
    "美容院・ヘアサロン":   "beauty_salon",
    "レストラン・飲食店":   "restaurant",
    "クリニック・医院":     "clinic",
    "美容整形クリニック":   "aesthetic_clinic",
    "フィットネス・ジム":   "fitness",
    "別荘・リゾート":       "villa",
    "バイク・モータースポーツ誌": "motorcycle_mag",
    "その他":               "default",
}

# アクセントカラープリセット
COLOR_PRESETS = {
    "ゴールド（高級・サロン系）":   {"gold": "#c9a96e", "gold_light": "#e8d5b0", "gold_dark": "#a07840"},
    "オレンジ（バイク・スポーツ系）": {"gold": "#d4681a", "gold_light": "#f0a96a", "gold_dark": "#a04e10"},
    "ラベンダー（美容・クリニック系）": {"gold": "#b8a0c8", "gold_light": "#d8c8e8", "gold_dark": "#8870a8"},
    "ボルドー（レストラン・ワイン系）": {"gold": "#9b2335", "gold_light": "#d4a0a8", "gold_dark": "#7a1828"},
    "ブルー（フィットネス・医療系）":  {"gold": "#2471a3", "gold_light": "#90c0e0", "gold_dark": "#1a5278"},
    "グリーン（ナチュラル・ハーブ系）": {"gold": "#5d8a5e", "gold_light": "#a8c8a8", "gold_dark": "#3d6a3e"},
}

# LP 全体のテイスト（GUI ラベル → 内部キー）。template_styles/*.css と対応。
LP_TEMPLATE_OPTIONS = [
    ("クラシック（標準・暖色）", "classic"),
    ("モダン（シャープ・クール）", "modern"),
    ("ミニマル（余白・フラット）", "minimal"),
    ("ラグジュアリー（濃色・重厚）", "luxury"),
]
LP_TEMPLATE_LABEL_TO_KEY = dict(LP_TEMPLATE_OPTIONS)
LP_TEMPLATE_STYLE_FILES = {
    "classic": "classic.css",
    "modern": "modern.css",
    "minimal": "minimal.css",
    "luxury": "luxury.css",
}
_LP_TEMPLATE_KEYS = frozenset(LP_TEMPLATE_STYLE_FILES.keys())

LP_TEMPLATE_DESIGN_HINTS = {
    "classic": "バランスの取れたセクション密度・ガラスモーフィズムのヒーロー。落ち着いた高級感。",
    "modern": "ややタイトな縦リズム・シャープなカードと細い境界線。クリニックやテック寄りの締まった印象。",
    "minimal": "セクション間をやや広めに取り、影を抑えたフラット寄り。余白とタイポグラフィを活かす。",
    "luxury": "ダークトーンとのコントラストを強め、ヒーローやフッターの重厚感。別荘・高級サロン向き。",
}


def normalize_lp_template_key(raw: object) -> str:
    k = str(raw or "").strip()
    if k in _LP_TEMPLATE_KEYS:
        return k
    return "classic"


def build_system_prompt(lp_template_key: str = "classic") -> str:
    tpl = normalize_lp_template_key(lp_template_key)
    tpl_hint = LP_TEMPLATE_DESIGN_HINTS.get(tpl, LP_TEMPLATE_DESIGN_HINTS["classic"])
    base = """あなたはプロのWebデザイナー兼フロントエンドエンジニアです。
与えられた店舗情報からランディングページ（LP）のHTMLを生成します。

## 最重要（トークン削減・出力が途中で切れないように）
- **生成物のフォルダに `style.css` が同梱される前提**です。**レイアウト用のCSSをHTML内に巨大に書かないでください（無駄な出力・コストになります）。**
- `<head>` に必ず次を入れる: `<link rel="stylesheet" href="style.css?v=1">`（フォントは従来どおり Google Fonts の link）
- **禁止**: セクション全体のレイアウト用として、`<style>` 内に数百行のCSSを書くこと。
- **許可**: `<style>` は次のどちらかだけに限定する（合計 **40行以内** を目安）
  (A) `:root { --gold: ...; --gold-light: ...; （必要なら --accent 等） }` のみ — 入力シートのテーマ色を CSS 変数で上書きするため
  (B) どうしても必要な **1〜3行のユーティリティ** だけ（乱用しない）
- 見た目の大部分は **既存クラス** に任せる（下記）。HTMLは **本文とマークアップ** に集中する。

## 出力ルール
- 必ずHTMLファイル1つを完全な形で出力する
- ```html と ``` で囲んで出力する
- 外部依存は Google Fonts・Lucide CDN（と同梱の script.js / pexels.js）のみ
- レスポンシブ: style.css 内のメディアクエリ前提。独自に重ねない
- 日本語コンテンツ

## 参照するクラス（style.css 定義済み・これを使う）
- ナビ: `nav` に id="navbar"、メニューに id="navMenu" class="nav-menu"、ハンバーガーに id="navToggle" class="nav-toggle"
- ヒーロー: .hero, .hero-bg, .hero-overlay, .hero-content, .glass-card, .hero-title, .btn, .btn-primary …
- セクション: .section, .section-header, .section-en, .section-title, .container
- About: .about, .about-grid, .about-img-wrap, .about-text …
- お悩み: .troubles-section, .lp-grid, .lp-card, .section-icon（アイコン枠）
- 理由: .reasons-section, .reason-block, .reason-block--reverse, .reason-img …
- サービス: .services-section, .lp-grid, .lp-card …
- Flow: .flow-section, .flow-list, .flow-item, .flow-num, .flow-body
- レビュー: .reviews-section, .reviews-grid, .review-card …。**星評価は** `.review-stars` **1つの要素の中に** Lucide の `star` を **横に並べる**（星ごとに別セクションや `<br>` で区切らない）
- FAQ: .faq-section, .faq-list, .faq-item, button.faq-q（aria-expanded）, .faq-a
- CTA: .cta-section, .cta-bg, .cta-overlay … / Access: .access … / Footer: .footer …

## デザイン仕様（必ず守ること）
- フォント: Cormorant Garamond（見出し）+ Noto Sans JP（本文）— link で読み込み
- アイコン: Lucide（`data-lucide`、stroke は CSS 済み）。読み込み後 `lucide.createIcons()` を実行する `<script>` を1つ
- data-industry 属性: `<html lang="ja" data-industry="（入力のキー）" data-lp-template="（テンプレID）">` — **業種でフォールバック写真、テンプレIDで同梱CSSのテーマが決まる**
- 画像: `pexels.js` を `</body>` 直前で読み込む。必ず **`.hero` 内に `.hero-bg`**、About に **`.about-img-wrap` > img**、理由に **`.reason-img` > img**、CTA に **`.cta-bg`** を用意する（ヒーロー背景は HTML の inline style で書かない）
- **禁止**: `images.pexels.com` の長い URL や、業種と無関係な固定 Unsplash ID を HTML にベタ書きすること（リンク切れ・他業種の写真のままになる）。`<img>` は **1×1 の透明 GIF** `data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7` を `src` にしてよい（`pexels.js` が業種別に差し替える）
- インタラクション: `<script src="script.js"></script>` を `</body>` 直前で読み込む

## 必須セクション構成
1. Navbar（ロゴ・ナビリンク・CTAボタン）
2. Hero（全面背景・キャッチコピー・バッジ3つ）
3. About（店舗紹介・特徴リスト）
4. Troubles（こんな方に/こんなお悩み 8項目）
5. Reasons（選ばれる理由 3ブロック・左右交互）
6. Services（サービスメニュー 3〜6枚カード）
7. Flow（ご利用の流れ 4〜5ステップ）
8. Reviews（お客様の声 6件）
9. FAQ（よくある質問 8問）
10. CTA（予約・購入ボタンセクション）
11. Access/Info（店舗情報・地図またはリンク）
12. Footer

## 業種別読み替えルール
- 雑誌・メディア系: Troubles→「こんな方に」、Branches→「バックナンバー」、Price→「購入方法」
- 別荘・不動産系: Services→「物件ラインナップ」、Flow→「購入の流れ」
- クリニック系: Troubles→「こんなお悩みに」、Flow→「診療の流れ」
- その他: セクション名を業種に合わせて自然に読み替える"""

    suffix = f"""

## 選択中のLPテンプレート（生成トーン）
- **テーマID `{tpl}`** — {tpl_hint}
- `<html>` には必ず **`data-lp-template="{tpl}"`** を付与する（省略・別名禁止）"""
    return base + suffix


def build_user_prompt(sheet: dict) -> str:
    industry_key = INDUSTRY_KEYS.get(sheet.get("industry", "その他"), "default")
    tpl = normalize_lp_template_key(sheet.get("lp_template"))
    tpl_label = next((lab for lab, k in LP_TEMPLATE_OPTIONS if k == tpl), LP_TEMPLATE_OPTIONS[0][0])
    color = sheet.get("color", {})

    reasons_text = ""
    for i, r in enumerate(sheet.get("reasons", []), 1):
        if r.get("title"):
            reasons_text += f"""
REASON {i:02d}:
  タイトル: {r['title']}
  説明: {r.get('desc', '')}
  特徴: {' / '.join(r.get('features', []))}"""

    services_text = ""
    for i, s in enumerate(sheet.get("services", []), 1):
        if s.get("title"):
            services_text += f"\n  {i}. {s['title']}: {s.get('desc', '')}"

    return f"""以下の入力シートに基づいてLPのHTMLを生成してください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INPUT SHEET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

【業種】
  業種名: {sheet.get('industry', '')}
  data-industry: {industry_key}

【LPテンプレート】
  選択名: {tpl_label}
  data-lp-template: {tpl}

【店舗情報】
  店舗名（日本語）: {sheet.get('name_ja', '')}
  店舗名（英語）:   {sheet.get('name_en', '')}
  キャッチコピー:   {sheet.get('catch', '')}
  サブコピー:       {sheet.get('sub_copy', '')}
  住所:             {sheet.get('address', '')}
  電話:             {sheet.get('tel', '')}
  営業時間:         {sheet.get('hours', '')}
  定休日:           {sheet.get('holiday', '')}
  最寄り駅:         {sheet.get('station', '')}
  WebサイトURL:     {sheet.get('url', '')}

【サービス内容】{services_text}

【推しポイント（選ばれる理由）】{reasons_text}

【デザイン設定】
  アクセントカラー: {color.get('gold', '#c9a96e')}
  ホバーカラー:     {color.get('gold_light', '#e8d5b0')}
  押下カラー:       {color.get('gold_dark', '#a07840')}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 追加指示
- 上記情報が空欄の場合は業種に合った自然なダミーテキストを補完する
- アイコンはすべて Lucide（data-lucide）。`.section-icon` 内に配置
- FAQ は button.faq-q + .faq-a（script.js のアコーディオン前提）
- **スタイルは style.css を link した上で、テーマ色だけ :root を <style> で上書き**（長大な<style>禁止）
- `<html lang="ja" data-industry="{industry_key}" data-lp-template="{tpl}">` を必ず付与（**業種・テンプレIDと一致させる・省略しない**）
- サービス・カード内の `<img>` は上記透明 GIF の `src` でよい（外部写真 URL を安易に埋め込まない）
"""


def build_input_sheet_md(sheet: dict) -> str:
    """入力内容をマークダウン形式で保存用に整形"""
    industry_key = INDUSTRY_KEYS.get(sheet.get("industry", "その他"), "default")
    tpl = normalize_lp_template_key(sheet.get("lp_template"))
    tpl_label = next((lab for lab, k in LP_TEMPLATE_OPTIONS if k == tpl), LP_TEMPLATE_OPTIONS[0][0])
    lines = [
        "# LP INPUT SHEET",
        "",
        f"生成日時: {sheet.get('created_at', '')}",
        "",
        "---",
        "",
        "## 業種",
        f"- 業種名: {sheet.get('industry', '')}",
        f"- data-industry: `{industry_key}`",
        "",
        "## LPテンプレート",
        f"- 選択名: {tpl_label}",
        f"- data-lp-template: `{tpl}`",
        "",
        "## 店舗情報",
        f"- 店舗名（日本語）: {sheet.get('name_ja', '')}",
        f"- 店舗名（英語）: {sheet.get('name_en', '')}",
        f"- キャッチコピー: {sheet.get('catch', '')}",
        f"- サブコピー: {sheet.get('sub_copy', '')}",
        f"- 住所: {sheet.get('address', '')}",
        f"- 電話: {sheet.get('tel', '')}",
        f"- 営業時間: {sheet.get('hours', '')}",
        f"- 定休日: {sheet.get('holiday', '')}",
        f"- 最寄り駅: {sheet.get('station', '')}",
        f"- WebサイトURL: {sheet.get('url', '')}",
        "",
        "## サービス内容",
    ]
    for i, s in enumerate(sheet.get("services", []), 1):
        if s.get("title"):
            lines.append(f"{i}. **{s['title']}**: {s.get('desc', '')}")
    lines += ["", "## 推しポイント（選ばれる理由）"]
    for i, r in enumerate(sheet.get("reasons", []), 1):
        if r.get("title"):
            lines += [
                f"### REASON {i:02d}: {r['title']}",
                f"- 説明: {r.get('desc', '')}",
                f"- 特徴: {' / '.join(r.get('features', []))}",
                "",
            ]
    lines += [
        "## デザイン設定",
        f"- アクセントカラー: `{sheet.get('color', {}).get('gold', '#c9a96e')}`",
        f"- カラープリセット: {sheet.get('color_name', 'ゴールド')}",
    ]
    return "\n".join(lines)
