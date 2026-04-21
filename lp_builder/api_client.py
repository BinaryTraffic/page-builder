"""
Claude API クライアント
INPUT_SHEETをAPIに送信してLP HTMLを受け取る
"""

import re

import anthropic

from prompt_template import (
    build_system_prompt,
    build_user_prompt,
    normalize_lp_template_key,
    normalize_target_tier,
)

# 1リクエストあたりの「生成の最大長」上限。
# 課金はこの数値ではなく実際の入出力トークン（max_tokens を満額使っても丸ごと請求されるわけではない）
_OUTPUT_CAPS = (128_000, 64_000, 32_768)

# LP 生成で用いるモデル（利用明細 JSON と揃える）
CLAUDE_LP_MODEL = "claude-opus-4-5"


def generate_lp(sheet: dict, api_key: str, on_progress=None) -> dict:
    """
    LPを生成してHTMLを返す

    Args:
        sheet: 入力シート辞書
        api_key: Anthropic APIキー
        on_progress: 進捗コールバック(text) → GUIのログ更新用

    Returns:
        {"html": str, "tokens_used": int, "input_tokens": int, "output_tokens": int,
         "error": str|None}
    """
    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = build_system_prompt(
        normalize_lp_template_key(sheet.get("lp_template")),
        normalize_target_tier(sheet.get("target_tier")),
    )
    user_prompt = build_user_prompt(sheet)

    if on_progress:
        on_progress("Claude APIに接続中（ストリーミング）...")

    # 長い生成は同期 create が拒否される場合がある（10分超想定時はストリーミング必須）
    # モデルごとの max_tokens 上限は異なる。大きい順に試し、BadRequest なら次へ。
    try:
        message = None
        last_cap_err: Exception | None = None
        for cap in _OUTPUT_CAPS:
            try:
                with client.messages.stream(
                    model=CLAUDE_LP_MODEL,
                    max_tokens=cap,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                ) as stream:
                    message = stream.get_final_message()
                if on_progress and cap != _OUTPUT_CAPS[0]:
                    on_progress(f"利用した出力上限: {cap:,} トークン（モデル制限に合わせ調整）")
                break
            except anthropic.BadRequestError as e:
                last_cap_err = e
                continue
        if message is None:
            raise last_cap_err if last_cap_err else RuntimeError("Messages API が利用できませんでした")

        if on_progress:
            on_progress("レスポンス受信完了。HTMLを抽出中...")

        raw_parts: list[str] = []
        for block in message.content:
            if getattr(block, "type", None) == "text":
                raw_parts.append(block.text)
        raw = "".join(raw_parts) if raw_parts else ""
        usage = message.usage
        in_tok = getattr(usage, "input_tokens", 0) or 0
        out_tok = getattr(usage, "output_tokens", 0) or 0
        tokens = in_tok + out_tok
        stop_reason = getattr(message, "stop_reason", None)

        # ```html ... ``` を抽出（非貪欲＝最初の閉じフェンスまで）。打ち切りで閉じがない場合はフォールバック
        match = re.search(r"```html\s*([\s\S]+?)\s*```", raw)
        if not match:
            match = re.search(r"```html\s*([\s\S]+)", raw)
        if match:
            html = match.group(1).strip()
        else:
            # フォールバック: <!DOCTYPE から始まる部分を抽出
            match2 = re.search(r"(<!DOCTYPE[\s\S]+)", raw, re.IGNORECASE)
            html = match2.group(1).strip() if match2 else raw.strip()

        if stop_reason == "max_tokens":
            err = (
                "生成がAPIの出力長上限で途中で切れました。保存された index.html は不完全です。"
                "もう一度「LP を生成する」を実行するか、プロンプトで外部CSS（style.css）利用に統一してください。"
            )
            if on_progress:
                on_progress(err)
            return {
                "html": html,
                "tokens_used": tokens,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "error": err,
            }

        if on_progress:
            on_progress(f"HTML生成完了（入力 {in_tok:,} / 出力 {out_tok:,} トークン）")

        return {
            "html": html,
            "tokens_used": tokens,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "error": None,
        }

    except anthropic.AuthenticationError:
        return {
            "html": "",
            "tokens_used": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "error": "APIキーが無効です。設定を確認してください。",
        }
    except anthropic.RateLimitError:
        return {
            "html": "",
            "tokens_used": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "error": "レート制限に達しました。しばらく待ってから再試行してください。",
        }
    except Exception as e:
        return {
            "html": "",
            "tokens_used": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "error": f"エラーが発生しました: {str(e)}",
        }
