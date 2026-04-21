"""
LP生成プロンプトテンプレート
INPUT_SHEETの内容をClaude APIへ渡すプロンプトを組み立てる。

方針: ターゲット層・業種は UI で確定済みとして渡し、本文から業種を推定させない。
LPテンプレート選択（CSS）は「器」、ターゲット層＋業種は「中身」（文章）と責務分離する。
"""

from __future__ import annotations

import json
from typing import Any

# ── ターゲット層（GUI ラベル ↔ 内部キー） ─────────────────────────
TARGET_TIER_LABEL_TO_KEY = {
    "富裕層向け": "luxury",
    "庶民向け": "mass",
}
TARGET_TIER_KEY_TO_LABEL = {v: k for k, v in TARGET_TIER_LABEL_TO_KEY.items()}
TARGET_TIER_KEYS = frozenset(TARGET_TIER_LABEL_TO_KEY.values())

# 「その他」選択時は業種名を自由入力 → industry_type=custom
CUSTOM_CATEGORY_LABEL = "その他（自由入力）"


def normalize_target_tier(raw: object) -> str:
    k = str(raw or "").strip()
    if k in TARGET_TIER_KEYS:
        return k
    if k in TARGET_TIER_LABEL_TO_KEY:
        return TARGET_TIER_LABEL_TO_KEY[k]
    return "mass"


# ── 業種プリセット（業種推定はさせず、この定義を優先） ─────────────
# industry_group = 大分類（横断キー）
# preset の id = industry_type（中分類・個別業種コード）として渡す

_INDUSTRY_PRESET_ROWS: list[dict[str, Any]] = [
    # --- 富裕層向け ---
    {
        "id": "luxury_beauty",
        "tier": "luxury",
        "label": "美容",
        "industry_group": "beauty",
        "data_industry": "beauty_salon",
        "copy": """【見出し・セクションの呼び方の例】お悩み→「こんな方におすすめ」「美しさを磨きたい方へ」／Flow→「ご利用の流れ」
【訴求の軸】完全予約制・プライベート空間・上質な素材・熟練の技術・オーダーメイド・時間をかけた体験
【避けること】安売り・大幅割引の前面押し・チープな煽り文句""",
    },
    {
        "id": "luxury_real_estate",
        "tier": "luxury",
        "label": "高価格帯不動産",
        "industry_group": "premium_real_estate",
        "data_industry": "villa",
        "copy": """【見出し例】物件ラインナップ／独占・希少性／コンシェルジュ的案内
【訴求の軸】立地・資産性・プライバシー・設備・管理体制・限定公開
【避けること】安さ一番・即決煽りのみ""",
    },
    {
        "id": "luxury_self_pay_medical",
        "tier": "luxury",
        "label": "自費診療",
        "industry_group": "self_pay_clinic",
        "data_industry": "aesthetic_clinic",
        "copy": """【見出し例】診療の流れ／よくあるご不安／医師・設備の紹介
【訴求の軸】専門性・安心・慎重な説明・プライバシー・待ち時間を減らす設計
【避けること】誇大な効果保証・他院批判""",
    },
    {
        "id": "luxury_fine_dining",
        "tier": "luxury",
        "label": "高級飲食",
        "industry_group": "fine_dining",
        "data_industry": "restaurant",
        "copy": """【見出し例】コース／シェフ／ワイン／空間／ランチ・ディナーの雰囲気
【訴求の軸】食材・産地・季節・ペアリング・おもてなし・記念日
【避けること】ファストフード的訴求・過度な量訴求""",
    },
    {
        "id": "luxury_personal_service",
        "tier": "luxury",
        "label": "高単価パーソナルサービス",
        "industry_group": "premium_personal",
        "data_industry": "beauty_salon",
        "copy": """【見出し例】完全マンツーマン／秘密厳守／時間貸し・コンシェルジュ
【訴求の軸】特別感・信頼・経験豊富なスタッフ・カスタマイズ
【避けること】大衆向け・回転重視の表現""",
    },
    # --- 庶民向け ---
    {
        "id": "mass_food",
        "tier": "mass",
        "label": "飲食",
        "industry_group": "food_service",
        "data_industry": "restaurant",
        "copy": """【見出し例】メニュー／ランチ・ディナー／お子様連れ・アレルギー／アクセス
【訴求の軸】気軽さ・わかりやすい価格感・安心・駅近・駐車場・家族連れ
【避けること】過度なフォーマル・難しい用語の羅列""",
    },
    {
        "id": "mass_retail",
        "tier": "mass",
        "label": "小売",
        "industry_group": "retail",
        "data_industry": "default",
        "copy": """【見出し例】取扱商品／店舗の見どころ／よくある質問（返品・支払い）
【訴求の軸】見つけやすさ・営業時間・気軽に立ち寄れる・スタッフがすぐ対応
【避けること】過度な高級感演出のみに寄せること""",
    },
    {
        "id": "mass_life_service",
        "tier": "mass",
        "label": "生活サービス",
        "industry_group": "life_service",
        "data_industry": "default",
        "copy": """【見出し例】サービス一覧／ご利用シーン／料金の考え方／お問い合わせ
【訴求の軸】便利さ・安心・明朗会計・地域の皆様へ
【避けること】押し売り感の強い文言""",
    },
    {
        "id": "mass_chiropractic",
        "tier": "mass",
        "label": "整体・接骨",
        "industry_group": "chiropractic",
        "data_industry": "clinic",
        "copy": """【見出し例】こんな症状でお悩みの方／初めての方へ／施術の流れ
【訴求の軸】わかりやすい説明・安心・無理な勧誘なし・アクセス・保険・自費の線引きは法令順守
【避けること】効果の断定的表現・医療と誤認される誇大広告""",
    },
    {
        "id": "mass_local_shop",
        "tier": "mass",
        "label": "地域密着型店舗",
        "industry_group": "local_shop",
        "data_industry": "default",
        "copy": """【見出し例】地域の皆さまへ／当店のこだわり／スタッフ紹介
【訴求の軸】地元愛・信頼・リピート・話しかけやすさ・わかりやすい情報
【避けること】全国チェーンのような無個性なコピーのみ""",
    },
]

INDUSTRY_PRESETS: dict[str, dict[str, Any]] = {row["id"]: row for row in _INDUSTRY_PRESET_ROWS}

_PRESET_ID_BY_TIER_LABEL: dict[tuple[str, str], str] = {}
for row in _INDUSTRY_PRESET_ROWS:
    _PRESET_ID_BY_TIER_LABEL[(row["tier"], row["label"])] = row["id"]


def category_labels_for_tier(tier_key: str) -> list[str]:
    """ターゲット層に応じた業種カテゴリ（日本語ラベル）一覧。末尾に「その他」。"""
    labels = [row["label"] for row in _INDUSTRY_PRESET_ROWS if row["tier"] == tier_key]
    return labels + [CUSTOM_CATEGORY_LABEL]


def resolve_preset_id(tier_key: str, category_label: str) -> str | None:
    """プリセット選択時は preset id、それ以外は None。"""
    if category_label == CUSTOM_CATEGORY_LABEL:
        return None
    return _PRESET_ID_BY_TIER_LABEL.get((tier_key, category_label))


def preset_copy(preset_id: str | None) -> str:
    if not preset_id or preset_id not in INDUSTRY_PRESETS:
        return ""
    return str(INDUSTRY_PRESETS[preset_id].get("copy") or "")


def _template_tier_category(
    table: dict[str, dict[str, str]], tier_key: str, category_label: str
) -> str | None:
    """プリセット業種ラベルに対応するテンプレを返す。カスタム業種・未定義は None。"""
    if category_label == CUSTOM_CATEGORY_LABEL:
        return None
    tk = normalize_target_tier(tier_key)
    return (table.get(tk) or {}).get(category_label)


# 店舗情報欄の初期テンプレ（GUI の業種ラベルと完全一致させる）。100〜200字程度・誇張控えめ。
DEFAULT_SHOP_INFO_BY_TIER: dict[str, dict[str, str]] = {
    "luxury": {
        "美容": (
            "当サロンは、お一人おひとりの髪質やライフスタイルに寄り添い、丁寧なカウンセリングのもとで施術をご提案いたします。"
            "落ち着いた空間と熟練の技術により、ご来店その日から実感していただける仕上がりを大切にしています。"
        ),
        "高価格帯不動産": (
            "希少性の高い立地と資産としての耐久性を重視し、ご希望に沿ったご紹介から契約まで一貫してサポートいたします。"
            "プライバシーにも配慮したご案内で、ご納得いただける選択をお手伝いします。"
        ),
        "自費診療": (
            "ご不安やご質問にお答えしながら、美容医療に関する選択をご自身のペースで進めていただける環境を整えております。"
            "医師・スタッフが協力し、結果と安全性の両面に配慮したご提案をいたします。"
        ),
        "高級飲食": (
            "素材の産地と季節を大切にし、シェフが一皿ひと皿丁寧に仕上げる料理をご提供いたします。"
            "記念日や大切な会合にふさわしい空間とおもてなしで、余韻の残るひとときをお届けします。"
        ),
        "高単価パーソナルサービス": (
            "ご予約いただいたお時間は完全にご自身のためだけの時間として、経験豊かなスタッフが個別に対応いたします。"
            "細やかなヒアリングにもとづき、無駄のないサービス設計と安心の運用を何より重視しています。"
        ),
    },
    "mass": {
        "飲食": (
            "当店では、素材にこだわった料理を気軽な雰囲気でご提供しています。"
            "お子様連れや少人数のお集まりにもご利用いただけるよう、アクセスや席のご案内にも気を配っています。"
        ),
        "小売": (
            "地域のみなさまに長く親しまれる店づくりを心がけ、品揃えとスタッフのご案内に力を入れています。"
            "お探しの商品についてもお気軽にお声がけください。"
        ),
        "生活サービス": (
            "暮らしのちょっとしたお困りごとから、定期的なご依頼まで幅広くお受けしています。"
            "料金や所要時間についてもわかりやすくご説明し、安心してご利用いただけるよう努めています。"
        ),
        "整体・接骨": (
            "身体のだるさや痛みでお困りの方へ、現在の状態を伺いながら無理のない施術計画をご提案しています。"
            "初めての方にも流れを丁寧にご説明し、続けやすいケアを大切にしています。"
        ),
        "地域密着型店舗": (
            "地元で長年営んでまいりました。「丁寧な対応」と「通いやすさ」を両立することを目指しています。"
            "ご来店やお問い合わせを心よりお待ちしています。"
        ),
    },
}

# サービス内容欄（やや具体的で短め。LP の Services に展開しやすいメモ）
DEFAULT_SERVICE_SUMMARY_BY_TIER: dict[str, dict[str, str]] = {
    "luxury": {
        "美容": (
            "カット・カラー・トリートメント等をご用意しています。ご来店時にカウンセリングのうえ、髪質やライフスタイルに合わせた施術をご提案いたします。"
        ),
        "高価格帯不動産": (
            "ご希望条件の整理から物件のご紹介、内覧同行、契約手続きに至るまで、専任にて一貫してサポートいたします。"
        ),
        "自費診療": (
            "ご相談・診察に基づき、ご希望と安全性のバランスを伺いながらメニューをご提案いたします。お悩みに応じた説明を大切にしています。"
        ),
        "高級飲食": (
            "季節のコース料理のほか、シーンに合わせたお席のご案内が可能です。アレルギーや苦手食材はご予約時にお申し付けください。"
        ),
        "高単価パーソナルサービス": (
            "事前のヒアリングを踏まえ、ご予約時間内で最適なメニューを組み立てます。ご相談のみ・お試しのご利用もお問い合わせください。"
        ),
    },
    "mass": {
        "飲食": (
            "ランチ・ディナーともにご利用いただけます。お子様メニューや宴会のご相談も承ります。"
        ),
        "小売": (
            "店頭販売のほか、在庫確認や取り寄せのご依頼も承っています。目的に合わせてスタッフがご案内します。"
        ),
        "生活サービス": (
            "お電話またはご来店にてお申し込みいただけます。内容・日程に応じてお見積りし、進め方をわかりやすくご説明します。"
        ),
        "整体・接骨": (
            "初回は問診と簡単なチェックのうえ、施術内容と目安をご説明します。保険適用・自費の別も事前にご案内いたします。"
        ),
        "地域密着型店舗": (
            "修理・お取り寄せ・簡単なお見積りなど、お困りごとに幅広く対応しています。まずはお気軽にお問い合わせください。"
        ),
    },
}

# 推しポイント欄（箇条書きメモ。Reasons セクションのたたき台）
DEFAULT_SELLING_POINTS_BY_TIER: dict[str, dict[str, str]] = {
    "luxury": {
        "美容": (
            "・完全予約制・落ち着いたプライベート空間\n"
            "・カウンセリング重視のオーダーメイド施術\n"
            "・熟練スタッフによる丁寧な仕上げとアフターケアのご提案"
        ),
        "高価格帯不動産": (
            "・希少性の高い物件情報と慎重なご紹介\n"
            "・内覧から契約まで一貫したサポート\n"
            "・プライバシーと資産性の両面に配慮したご提案"
        ),
        "自費診療": (
            "・十分な説明とご納得の上での施術設計\n"
            "・医師・スタッフが連携した安心の体制\n"
            "・お悩みに応じたオーダーメイドの選択肢"
        ),
        "高級飲食": (
            "・季節と産地を活かしたコース構成\n"
            "・記念日や接待に配慮したお席とおもてなし\n"
            "・ワイン・ペアリング等のご相談にも対応"
        ),
        "高単価パーソナルサービス": (
            "・マンツーマンでの時間と空間の確保\n"
            "・ヒアリングに基づく無駄のないサービス設計\n"
            "・経験と実績に裏打ちされた信頼の対応"
        ),
    },
    "mass": {
        "飲食": (
            "・気軽に立ち寄れる雰囲気とわかりやすいメニュー\n"
            "・素材と味付けへのこだわり\n"
            "・家族連れ・アレルギー等のご相談に対応"
        ),
        "小売": (
            "・地域の暮らしに合わせた品揃え\n"
            "・スタッフによる丁寧な商品説明\n"
            "・在庫・取り寄せのお問い合わせに迅速対応"
        ),
        "生活サービス": (
            "・明朗な料金と所要時間の説明\n"
            "・定期的なご依頼からスポットまで柔軟に対応\n"
            "・安心して続けられるサポート体制"
        ),
        "整体・接骨": (
            "・現在の状態に合わせた無理のない施術計画\n"
            "・初めての方にもわかりやすいご説明\n"
            "・無理な勧誘をせず、続けやすいペースを重視"
        ),
        "地域密着型店舗": (
            "・地元で培った信頼と実績\n"
            "・相談しやすい雰囲気と丁寧な対応\n"
            "・通いやすい立地とわかりやすい案内"
        ),
    },
}


def default_shop_info_for(tier_key: str, category_label: str) -> str | None:
    """プリセット業種とターゲットに対応する店舗紹介テンプレ。"""
    return _template_tier_category(DEFAULT_SHOP_INFO_BY_TIER, tier_key, category_label)


def default_service_summary_for(tier_key: str, category_label: str) -> str | None:
    """サービス内容欄用テンプレ。"""
    return _template_tier_category(DEFAULT_SERVICE_SUMMARY_BY_TIER, tier_key, category_label)


def default_selling_points_for(tier_key: str, category_label: str) -> str | None:
    """推しポイント欄用テンプレ。"""
    return _template_tier_category(DEFAULT_SELLING_POINTS_BY_TIER, tier_key, category_label)


def target_tier_detailed_guide(tier_key: str) -> str:
    """文体・訴求・CTA・見出しの指針（ターゲット最優先）。"""
    if tier_key == "luxury":
        return """【富裕層向け・文章トーン（最優先で全体に反映）】
- 上品で大人向け。誇張しすぎず、静かな自信と品格。
- 安売り・値引き連発・チープな煽りは禁止。価格は「明朗さ」が必要なとき以外前面に出さない。
- 品質・体験・信頼・特別感・時間の価値・プライバシーを軸に。
- 説明は簡潔だが雑にしない。見出しは洗練された語彙（過度なカタカナ連発は避ける）。
- CTAは「無理な締め切り煽り」より、相談・ご予約・お問い合わせへの自然な誘い。落ち着いた温度感。
- よくある悩み・選ばれる理由・安心感は「根拠・プロセス・実績の示し方」で語る。"""
    return """【庶民向け・文章トーン（最優先で全体に反映）】
- 難しい言い回し・過度な敬語の壁を避け、親しみやすく自然に。
- はじめてでも利用しやすいこと、気軽さ、わかりやすさを重視。
- 地域密着・安心感・手軽さ・価格感には配慮するが、過度にチープにはしない。
- CTAは押し売りではなく「お気軽にご相談」「まずはお問い合わせ」など安心寄りの温度感。
- よくある悩み・選ばれる理由・安心感は「具体的シーン・スタッフ対応・アクセス・明朗さ」で語る。"""


TARGET_TIER_VOICE = {
    "luxury": target_tier_detailed_guide("luxury"),
    "mass": target_tier_detailed_guide("mass"),
}

SELLING_POINTS_EMPTY_GUIDE = """【推しポイント（selling_points が空のとき）】
入力が空でも LP は完成させること。**業種・ターゲット層に整合する推しポイントを 2〜4 個**、Reasons（.reason-block）などに反映する。
※ 定型句のそのままコピペは避け、業種に即して言い換えること。
参考キーワードの方向性: 丁寧な対応／通いやすさ／落ち着いた空間／地域密着／柔軟な対応／初めてでも安心／上質な体験／専門性の高い提案 — から業種に合うものを選び、独自の短文にすること。"""

# 互換用: 旧 INDUSTRY_KEYS（もし外部参照が残る場合）
LEGACY_INDUSTRY_KEYS = {
    "ペットサロン": "pet_salon",
    "美容院・ヘアサロン": "beauty_salon",
    "レストラン・飲食店": "restaurant",
    "クリニック・医院": "clinic",
    "美容整形クリニック": "aesthetic_clinic",
    "フィットネス・ジム": "fitness",
    "別荘・リゾート": "villa",
    "バイク・モータースポーツ誌": "motorcycle_mag",
    "その他": "default",
}

# アクセントカラープリセット
COLOR_PRESETS = {
    "ゴールド（高級・サロン系）": {"gold": "#c9a96e", "gold_light": "#e8d5b0", "gold_dark": "#a07840"},
    "オレンジ（バイク・スポーツ系）": {"gold": "#d4681a", "gold_light": "#f0a96a", "gold_dark": "#a04e10"},
    "ラベンダー（美容・クリニック系）": {"gold": "#b8a0c8", "gold_light": "#d8c8e8", "gold_dark": "#8870a8"},
    "ボルドー（レストラン・ワイン系）": {"gold": "#9b2335", "gold_light": "#d4a0a8", "gold_dark": "#7a1828"},
    "ブルー（フィットネス・医療系）": {"gold": "#2471a3", "gold_light": "#90c0e0", "gold_dark": "#1a5278"},
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


def resolve_data_industry(sheet: dict) -> str:
    """HTML data-industry 用。プリセットは定義済みキー、カスタムは default。"""
    pid = sheet.get("preset_id")
    if pid and pid in INDUSTRY_PRESETS:
        return str(INDUSTRY_PRESETS[pid]["data_industry"])
    return "default"


def normalized_input_block(sheet: dict) -> dict[str, Any]:
    """ユーザー指定の正規化ブロック（プロンプト・保存用）。
    industry_group = 大分類、industry_type = 中分類／個別業種コード（プリセット id または custom）
    """
    return {
        "target_tier": sheet.get("target_tier"),
        "industry_group": sheet.get("industry_group"),
        "industry_type": sheet.get("industry_type"),
        "industry_label": sheet.get("industry_label"),
        "shop_info": sheet.get("shop_info") or "",
        "service_summary": sheet.get("service_summary") or "",
        "selling_points": sheet.get("selling_points") or "",
    }


def build_system_prompt(
    lp_template_key: str = "classic",
    target_tier_key: str | None = None,
) -> str:
    tpl = normalize_lp_template_key(lp_template_key)
    tpl_hint = LP_TEMPLATE_DESIGN_HINTS.get(tpl, LP_TEMPLATE_DESIGN_HINTS["classic"])
    tt = normalize_target_tier(target_tier_key) if target_tier_key is not None else None

    base = """あなたはプロのWebデザイナー兼フロントエンドエンジニアです。
与えられた店舗情報からランディングページ（LP）のHTMLを生成します。

## 最重要（業種・ターゲット）
- **ユーザー入力で指定されたターゲット層・業種のみを正とする。** 店舗説明文から別の業種や別ターゲットへ「推定して」書き換えないこと。
- **業種の推定・変更は禁止。** 補完は `industry_label`・`industry_group`・`industry_type`・店舗メモの範囲に留める。
- **前段で業種を判断する処理は不要。** 入力 JSON の値をそのまま用いる。

## 責務分離（テンプレート = 器／文章 = 中身）
- **`data-lp-template`（選択中の CSS テーマ）** はレイアウト・余白・色調の「器」である。
- **文章のトーン・訴求・見出し・CTA の温度感** は **`data-target-tier`（luxury | mass）と業種フィールド** で決める。テーマ名に文章トーンを寄せない（例: テンプレが luxury でもターゲットが庶民向けなら庶民向けの文にする）。

## 最重要（トークン削減・出力が途中で切れないように）
- **生成物のフォルダに `style.css` が同梱される前提**です。**レイアウト用のCSSをHTML内に巨大に書かないでください（無駄な出力・コストになります）。**
- **`<head>` 内の順序（崩れ防止）**: Google Fonts の `<link>` →（任意）テーマ色の短い `<style>`（:root のみ）→ **最後に** `<link rel="stylesheet" href="style.css">`（**保存時に LP Builder が自動で `?v=日時` を付与**しキャッシュを避けるので、本文では `style.css` のみでよい）。**`style.css` より後に `<style>` を置かない**（後から書いた CSS がナビやヒーローを上書きして白背景・白文字・巨大ボタンになる）。
- **禁止**: `<nav id="navbar"` / `<header id="navbar"` の**開始タグ**に `style=`（インラインCSS）を書かない。白背景などが効くとナビの白文字が背景と同化して見えなくなる。LP Builder が保存時に除去するが、出力に含めないこと。
- **禁止**: `<style>` で `#navbar` / `.navbar` / `.nav-menu` / `.nav-cta` / `.hero-content` / `.glass-card` の**レイアウト・背景・文字色**を書かない（`style.css` と競合する）。テーマ色は **`:root` 変数だけ**。
- **禁止**: セクション全体のレイアウト用として、`<style>` 内に数百行のCSSを書くこと。
- **許可**: `<style>` は次のどちらかだけに限定する（合計 **40行以内** を目安）
  (A) `:root { --gold: ...; --gold-light: ...; （必要なら --accent 等） }` のみ — 入力シートのテーマ色を CSS 変数で上書きするため
  (B) どうしても必要な **1〜3行のユーティリティ** だけ（乱用しない）
- 見た目の大部分は **既存クラス** に任せる（下記）。HTMLは **本文とマークアップ** に集中する。

## 必須コピー要素（本文生成・クラス対応）
次の文言はすべて LP 内に **自然な日本語で** 含めること（店舗メモが薄い場合は業種・ターゲットに整合するよう補完してよいが、業種のすり替えはしない）。
| 要素 | 配置の目安 |
|------|------------|
| Hero キャッチコピー | `.hero-title` |
| Hero サブコピー | `.hero-desc` または `.glass-card` 内のリード |
| リード文（店の紹介の冒頭） | About `.about-text` の冒頭段落 |
| サービス説明文 | Services `.services-section` のカード本文 |
| 推しポイント文（2〜4個） | Reasons `.reason-block`（入力 selling_points が空なら業種・ターゲットに沿って生成） |
| CTA 見出し | `.cta-glass h2` |
| CTA 補助文 | `.cta-glass p` |

## 生成時の観点（文章）
- その業種で一般的な顧客像（※ただしターゲット層は入力の target_tier を優先）
- よくある悩み → Troubles セクション
- 選ばれる理由 → Reasons / Reviews のストーリーに反映
- 安心感（根拠・プロセス・対応）
- 問い合わせ・予約につながる自然な導線（CTA・Access）

## 出力ルール
- 必ずHTMLファイル1つを完全な形で出力する
- ```html と ``` で囲んで出力する
- 外部依存は Google Fonts・Lucide CDN（と同梱の script.js / pexels.js）のみ
- レスポンシブ: style.css 内のメディアクエリ前提。独自に重ねない
- 日本語コンテンツ

## 参照するクラス（style.css 定義済み・これを使う）
- ナビ: `nav` に id="navbar"（任意で `data-nav-max-visible="4"`：バーに並べる最大リンク数。省略時は 4）、メニューに id="navMenu" class="nav-menu"（**同一階層に並ぶ** `a` がナビ項目。CTA は最後に `class="nav-cta"`）、ハンバーガーに id="navToggle" class="nav-toggle"。**script.js** が左からスライドするメニューを追加する：デスクトップは先頭 N 件だけバー表示・それ以降は「メニュー」から、モバイルはハンバーガーで全リンクを同じドロワーに表示。**右上の予約・問い合わせ導線は** `class="nav-cta"` **のみ**（`btn` / `btn-lg` を併用しない。1行表示が前提）
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
- **ルート要素**: `<html lang="ja" data-industry="（後述の値のみ）" data-target-tier="luxury|mass" data-lp-template="（テンプレID）">`
  - **data-industry** はユーザー入力で確定した値のみ（本文から変更しない）
  - **data-target-tier** は luxury または mass（ユーザー選択と一致）
- 画像: `pexels.js` を `</body>` 直前で読み込む。必ず **`.hero` 内に `.hero-bg`**、About に **`.about-img-wrap` > img**、理由に **`.reason-img` > img**、CTA に **`.cta-bg`** を用意する（ヒーロー背景は HTML の inline style で書かない）
- **禁止**: `images.pexels.com` の長い URL や、業種と無関係な固定 Unsplash ID を HTML にベタ書きすること（リンク切れ・他業種の写真のままになる）。`<img>` は **1×1 の透明 GIF** `data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7` を `src` にしてよい（`pexels.js` が業種別に差し替える）
- インタラクション: `<script src="script.js"></script>` を `</body>` 直前で読み込むのが確実（`<head>` に置いても DOM 構築後に初期化するよう実装済み）。ページ内リンクは下記の「**必須（ページ内アンカー）**」を遵守すること。右下の「↑ トップへ戻る」は script.js が自動付与（`style.css` の `.back-to-top` 前提）
- **必須（ページ内アンカー）**: ナビ・フッター・本文で使う **`href="#xxx"` の `xxx` と、飛び先の `id="xxx"` を必ず同一文字列にする**（例: `<a href="#about">` → `<section id="about">` または `<div id="about">`）。**`#` だけ・空の href は不可**。`href` と `id` が1文字でも違うと script.js はスクロールできない。LP Builder は保存時に不整合があればログに警告する。

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

## 業種別読み替え（プリセットまたは industry_label に整合させる）
- 不動産・別荘系: Services→「物件ラインナップ」、Flow→「ご案内の流れ」など自然な語に
- クリニック・整体系: Troubles→「こんなお悩みに」、Flow→「初診〜の流れ」
- 飲食: メニュー・シーン・家族連れなどわかりやすく
- **カスタム業種**（industry_type が custom）: `industry_label` と店舗メモに沿い、無理に別業種の語彙へ寄せない"""

    suffix = f"""

## 選択中のLPテンプレート（レイアウト・器のみ）
- **テーマID `{tpl}`** — {tpl_hint}
- `<html>` には必ず **`data-lp-template="{tpl}"`** を付与する（省略・別名禁止）
- 文章トーンはテーマではなく **ユーザーのターゲット層・業種** に従うこと。"""

    tier_extra = ""
    if tt is not None:
        tier_extra = f"""

## 今回のターゲット層（文章の最優先条件）
- **data-target-tier = `{tt}`** の指針に従い、文体・訴求・CTA・見出しを統一すること。
- **ターゲット層と矛盾する表現**（例: 庶民向けなのに過度な富裕層限定の煽り）は避ける。
"""
    return base + tier_extra + suffix


def build_user_prompt(sheet: dict) -> str:
    tpl = normalize_lp_template_key(sheet.get("lp_template"))
    tpl_label = next((lab for lab, k in LP_TEMPLATE_OPTIONS if k == tpl), LP_TEMPLATE_OPTIONS[0][0])
    color = sheet.get("color", {})

    tier_key = normalize_target_tier(sheet.get("target_tier"))
    tier_label = TARGET_TIER_KEY_TO_LABEL.get(tier_key, "庶民向け")
    tier_voice = TARGET_TIER_VOICE.get(tier_key, TARGET_TIER_VOICE["mass"])

    preset_id = sheet.get("preset_id")
    pcopy = preset_copy(preset_id) if preset_id else ""
    industry_type_field = sheet.get("industry_type")
    data_ind = resolve_data_industry(sheet)

    norm = normalized_input_block(sheet)
    norm_json = json.dumps(norm, ensure_ascii=False, indent=2)

    sp = (sheet.get("selling_points") or "").strip()
    selling_block = (
        SELLING_POINTS_EMPTY_GUIDE
        if not sp
        else "【推しポイント入力あり】以下のメモを Reasons 等に反映し、不足分のみ補完してよい。\n" + sp
    )

    custom_note = ""
    if industry_type_field == "custom":
        custom_note = """
【カスタム業種モード】
- `industry_label` を公式の業種名として扱い、別業種へ書き換えないこと。
- 写真用 data-industry は default。必要なら顧客が custom 画像を置ける旨は想起してよいが、HTML に外部写真 URL をベタ書きしない。
"""

    preset_section = ""
    if preset_id and pcopy:
        preset_section = f"""
【業種プリセット（大分類・個別コードに整合・業種推定の代替ではない）】
- industry_group（大分類）・industry_type（個別コード）= `{sheet.get("industry_type")}` と一致する前提で読む。
preset_id: {preset_id}
{pcopy}
"""
    else:
        preset_section = """
【業種プリセット】
なし（カスタム）。industry_group / industry_type = custom。industry_label と店舗メモのみを業種の根拠とする。
"""

    return f"""以下の入力に基づいてLPのHTMLを生成してください。

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
禁止: 本文から業種・ターゲット層を「推定し直して」見出しやコピーを別業種に変更しないこと。
必ず JSON の target_tier / industry_group / industry_type / industry_label と data-industry の組み合わせに整合させること。
優先順位: **① target_tier（文体・訴求・CTA） → ② 業種フィールド → ③ 店舗メモ → ④ LPテンプレ（器のみ）**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 正規化済み入力（唯一の参照・業種推定は不要）
```json
{norm_json}
```

## ターゲット層（最優先・全文面に反映）
{tier_voice}

選択: **{tier_label}**（`target_tier={tier_key}`）
- 見出しの言い回し、FAQの切り口、CTAの温度感は **必ずこのターゲットに合わせる**。
- `data-lp-template`（{tpl}）は **レイアウト用**。**文章のトーンをテーマ名に寄せない**。

{preset_section}
{custom_note}

【LPテンプレート（見た目の器のみ）】
  選択名: {tpl_label}
  data-lp-template: {tpl}
  ※ CSS のテーマは配色・余白・密度。コピーの品格／親しみは target_tier で決める。

【デザイン（CSS変数上書き用）】
  アクセントカラー: {color.get('gold', '#c9a96e')}
  ホバーカラー:     {color.get('gold_light', '#e8d5b0')}
  押下カラー:       {color.get('gold_dark', '#a07840')}

{selling_block}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## 追加指示
- アイコンはすべて Lucide（data-lucide）。`.section-icon` 内に配置
- FAQ は button.faq-q + .faq-a（script.js のアコーディオン前提）
- **スタイルは style.css を link した上で、テーマ色だけ :root を <style> で上書き**（長大な<style>禁止）
- `<html lang="ja" data-industry="{data_ind}" data-target-tier="{tier_key}" data-lp-template="{tpl}">` を必ず付与（値は上記と一致）
- サービス・カード内の `<img>` は上記透明 GIF の `src` でよい（外部写真 URL を安易に埋め込まない）
"""


def build_input_sheet_md(sheet: dict) -> str:
    """入力内容をマークダウン形式で保存用に整形"""
    tpl = normalize_lp_template_key(sheet.get("lp_template"))
    tpl_label = next((lab for lab, k in LP_TEMPLATE_OPTIONS if k == tpl), LP_TEMPLATE_OPTIONS[0][0])
    tier_key = normalize_target_tier(sheet.get("target_tier"))
    tier_label = TARGET_TIER_KEY_TO_LABEL.get(tier_key, "")
    norm = normalized_input_block(sheet)
    data_ind = resolve_data_industry(sheet)

    lines = [
        "# LP INPUT SHEET",
        "",
        f"生成日時: {sheet.get('created_at', '')}",
        "",
        "---",
        "",
        "## 正規化入力（JSON）",
        "```json",
        json.dumps(norm, ensure_ascii=False, indent=2),
        "```",
        "",
        "## メタデータ",
        f"- target_tier: `{tier_key}`（{tier_label}）",
        f"- industry_group（大分類）: `{sheet.get('industry_group', '')}`",
        f"- industry_type（中分類・個別コード）: `{sheet.get('industry_type', '')}`",
        f"- preset_id（内部）: `{sheet.get('preset_id')}`",
        f"- data-industry（HTML）: `{data_ind}`",
        "",
        "## LPテンプレート（器）",
        f"- 選択名: {tpl_label}",
        f"- data-lp-template: `{tpl}`",
        "",
        "## デザイン設定",
        f"- アクセントカラー: `{sheet.get('color', {}).get('gold', '#c9a96e')}`",
        f"- カラープリセット: {sheet.get('color_name', '')}",
        "",
        "## 店舗情報（本文）",
        sheet.get("shop_info") or "",
        "",
        "## サービス内容メモ",
        sheet.get("service_summary") or "",
        "",
        "## 推しポイントメモ（任意・空可）",
        sheet.get("selling_points") or "",
        "",
    ]
    return "\n".join(lines)
