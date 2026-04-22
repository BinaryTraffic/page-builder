"""
LP Builder — ランディングページ自動生成ツール
Python 3.x + tkinter（追加インストール不要）
"""

import csv
import base64
import ctypes
import functools
import http.server
import json
import os
import re
import secrets
import shutil
import uuid
import socketserver
import subprocess
import sys
import threading
import urllib.parse
import webbrowser
import posixpath
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime
from pathlib import Path

# パスを通す（同ディレクトリのモジュールを読む）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prompt_template import (
    COLOR_PRESETS,
    CUSTOM_CATEGORY_LABEL,
    INDUSTRY_PRESETS,
    TARGET_TIER_KEY_TO_LABEL,
    TARGET_TIER_LABEL_TO_KEY,
    build_input_sheet_md,
    category_labels_for_tier,
    default_selling_points_for,
    default_service_summary_for,
    default_shop_info_for,
    LP_TEMPLATE_OPTIONS,
    LP_TEMPLATE_LABEL_TO_KEY,
    LP_TEMPLATE_STYLE_FILES,
    normalize_lp_template_key,
    normalize_target_tier,
    resolve_preset_id,
)
from api_client import CLAUDE_LP_MODEL, generate_lp

# ─────────────────────────────────────────────
# 定数
# ─────────────────────────────────────────────
APP_TITLE   = "LP Builder  —  ランディングページ自動生成"
APP_VERSION = "1.0.0"
CONFIG_FILE = Path.home() / ".lp_builder_config.json"
# API 利用明細（追記型）。ホーム直下に保存し、別名エクスポートも可能。
USAGE_LEDGER_JSON = Path.home() / ".lp_builder_api_usage.json"
# サイト専用 CMS ユーザー（サーバ環境変数 LP_SITE_INITIAL_PASSWORD と揃える）
CMS_SITE_INITIAL_PASSWORD = "Whatisthepassword?"

BG_DARK   = "#1a1a1a"
BG_PANEL  = "#242424"
BG_INPUT  = "#2e2e2e"
FG_MAIN   = "#f0f0f0"
FG_SUB    = "#aaaaaa"
GOLD      = "#c9a96e"
GOLD_DARK = "#a07840"
RED_ERR   = "#e05555"
GREEN_OK  = "#55c055"
WARN_MSG  = "#e8b86d"

FONT_H1   = ("Segoe UI", 16, "bold")
FONT_H2   = ("Segoe UI", 12, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_MONO = ("Consolas", 9)

# 共有ファイル（アプリと同じフォルダに同梱）
SHARED_FILES = ["script.js", "pexels.js"]
APP_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
ENV_FILE = APP_DIR / ".env"
WIN_TOKEN_FILE = Path(os.getenv("APPDATA") or str(Path.home())) / "LPBuilder" / "env_token.bin"

# 概算コスト用デフォルト（USD / 100万トークン）。公式 Pricing と api_client の model 名に合わせて設定で調整してください。
# https://platform.claude.com/docs/en/about-claude/pricing
DEFAULT_PRICE_INPUT_PER_MTOK = "5"
DEFAULT_PRICE_OUTPUT_PER_MTOK = "25"


def _strip_example_prefix(text: str) -> str:
    """入力に誤って含まれた「例:」系の接頭辞を除く（説明文のコピペ対策）"""
    t = (text or "").strip()
    for p in ("例:", "例：", "e.g.", "E.g.", "eg:", "eg："):
        if t.startswith(p):
            return t[len(p) :].strip()
    return t


def normalize_output_dir(raw: str) -> Path:
    """設定タブの出力先パスを正規化。空や無効なら ~/LP_Projects。"""
    s = _strip_example_prefix(raw or "")
    if not s:
        return (Path.home() / "LP_Projects").resolve()
    p = Path(s).expanduser()
    try:
        return p.resolve()
    except OSError:
        return p


def _inject_asset_cache_bust(html: str, version: str) -> str:
    """index.html 内の style.css / script.js / pexels.js 参照にキャッシュバスト用 ?v= を付与する。"""
    if not html:
        return html
    v = re.sub(r"[^\w.-]+", "", (version or "").strip())[:80] or "1"
    out = html
    out = re.sub(
        r'href=(["\'])style\.css(?:\?[^"\']*)?\1',
        rf"href=\1style.css?v={v}\1",
        out,
        flags=re.IGNORECASE,
    )
    for name in ("script.js", "pexels.js"):
        out = re.sub(
            rf'src=(["\']){re.escape(name)}(?:\?[^"\']*)?\1',
            rf"src=\1{name}?v={v}\1",
            out,
            flags=re.IGNORECASE,
        )
    return out


def _strip_navbar_inline_styles(html: str) -> str:
    """
    id="navbar" の <nav> / <header> 開始タグに付いた style はブラウザで強く効き、
    白背景のまま白文字のナビになることがある。外部 CSS を効かせるため style 属性を除去する。
    """
    if not html:
        return html

    def _clean_tag(m: re.Match) -> str:
        tag = m.group(0)
        if not re.search(r'\bid\s*=\s*["\']navbar["\']', tag, re.I):
            return tag
        t2 = tag
        for _ in range(8):
            nxt = re.sub(
                r'\sstyle\s*=\s*("[^"]*"|\'[^\']*\')',
                "",
                t2,
                count=1,
                flags=re.I,
            )
            if nxt == t2:
                break
            t2 = nxt
        return t2

    return re.sub(r"<(?:nav|header)\b[^>]*>", _clean_tag, html, flags=re.I)


def _ensure_navbar_class(html: str) -> str:
    """
    id="navbar" を持つ <nav> / <header> 開始タグに class="navbar" を保証する。
    モデル出力で class が欠けると .navbar 系の基本スタイル/挙動が効かないため、保存時に補正する。
    """
    if not html:
        return html

    def _fix_tag(m: re.Match) -> str:
        tag = m.group(0)
        if not re.search(r'\bid\s*=\s*["\']navbar["\']', tag, re.I):
            return tag
        cm = re.search(r'\bclass\s*=\s*(["\'])(.*?)\1', tag, re.I | re.S)
        if cm:
            cls = cm.group(2)
            if re.search(r'(^|\s)navbar(\s|$)', cls):
                return tag
            new_cls = (cls + " navbar").strip()
            return tag[: cm.start(2)] + new_cls + tag[cm.end(2) :]
        return re.sub(r"<(?:nav|header)\b", r'\g<0> class="navbar"', tag, count=1, flags=re.I)

    return re.sub(r"<(?:nav|header)\b[^>]*>", _fix_tag, html, flags=re.I)


def _normalize_common_anchor_aliases(html: str) -> str:
    """
    よくあるアンカー別名を実在セクションへ寄せる。
    例: #contact / #contact-form があり、#cta が存在する場合は #cta に統一。
    """
    if not html:
        return html
    if not re.search(r'\bid\s*=\s*["\']cta["\']', html, re.I):
        return html
    out = html
    for alias in ("contact", "contact-form", "inquiry", "reserve"):
        out = re.sub(
            rf'href\s*=\s*(["\'])#{re.escape(alias)}\1',
            r'href="#cta"',
            out,
            flags=re.I,
        )
    return out


def _ensure_custom_images_enabled(html: str) -> str:
    """
    pexels.js の custom/config.json 読み込みを有効化するため、
    <html> 開始タグへ data-custom-images="1" を付与する。
    """
    if not html:
        return html

    def _fix(m: re.Match) -> str:
        tag = m.group(0)
        if re.search(r'\bdata-custom-images\s*=', tag, re.I):
            return re.sub(
                r'(\bdata-custom-images\s*=\s*)(["\']).*?\2',
                r'\1"1"',
                tag,
                flags=re.I | re.S,
            )
        return tag[:-1] + ' data-custom-images="1">'

    return re.sub(r"<html\b[^>]*>", _fix, html, count=1, flags=re.I)


def _hash_anchor_mismatches(html: str) -> list[str]:
    """
    href=\"#...\" のページ内リンクに対し、対応する id または name が HTML 内にあるか検査する。
    モデルが id を付け忘れたとき、スクロールが効かない原因の手がかりになる。
    """
    if not html:
        return []
    ids = set(re.findall(r'\bid\s*=\s*["\']([^"\']+)["\']', html, re.I))
    names = set(re.findall(r'\bname\s*=\s*["\']([^"\']+)["\']', html, re.I))
    frags: set[str] = set()
    for m in re.finditer(r'\bhref\s*=\s*["\']#([^"\'#?]*)["\']', html, re.I):
        frag = (m.group(1) or "").strip()
        if not frag:
            continue
        try:
            frag = urllib.parse.unquote(frag)
        except Exception:
            pass
        frags.add(frag)
    out: list[str] = []
    for frag in sorted(frags):
        if frag not in ids and frag not in names:
            out.append(
                f'ページ内リンク #{frag} に対応する id="{frag}"（または name）がありません'
            )
    return out


def _usage_meta_from_sheet(sheet: dict, out_dir: Path) -> dict:
    """API 利用明細に載せるラベル・出力パス。"""
    shop = (sheet.get("shop_info") or "").strip()
    first = ""
    for line in shop.splitlines():
        s = line.strip()
        if s:
            first = s[:120]
            break
    lab = first or str(sheet.get("industry_label") or "").strip()
    lab = lab[:120] if lab else ""
    try:
        out_s = str(out_dir.resolve())
    except OSError:
        out_s = str(out_dir)
    return {"label": lab, "output_dir": out_s}


def _truncate_utf8_bytes(s: str, max_bytes: int) -> str:
    """UTF-8 バイト数が max_bytes を超えないよう末尾から切り詰け（1 ファイル名の長さ対策）。"""
    if not s or max_bytes <= 0:
        return s
    if len(s.encode("utf-8")) <= max_bytes:
        return s
    out = s
    while out and len(out.encode("utf-8")) > max_bytes:
        out = out[:-1]
    return out or "lp"


def safe_site_dir_segment(sheet: dict) -> str:
    """出力サブフォルダ名用。店舗情報の先頭行などから派生。

    最終ディレクトリ名は ``{base}_{%Y%m%d_%H%M%S}_{lp_token}``。Linux ext4 等の
    「1 コンポーネント 255 バイト」制限のため、base は先に短くする。
    """
    shop = (sheet.get("shop_info") or "").strip()
    first_line = ""
    for line in shop.splitlines():
        s = line.strip()
        if s:
            first_line = s
            break
    raw = first_line or (sheet.get("industry_label") or "lp_site").strip()
    raw = _strip_example_prefix(raw)
    if not raw:
        raw = "lp_site"
    for c in '<>:"/\\|?*':
        raw = raw.replace(c, "_")
    raw = raw.replace(" ", "_").lower()
    # 先頭1行が長文でも、公開URLの1セグメントが読めない長さにならないよう字数目で上限
    _max_slug_chars = 32
    if len(raw) > _max_slug_chars:
        raw = raw[:_max_slug_chars].rstrip("._-")
    # _ + 日時(15) + _ + lp_token(24hex) = 41 バイト（ASCII）
    _reserved = 1 + 15 + 1 + 24
    raw = _truncate_utf8_bytes(raw, 255 - _reserved)
    if not (raw and raw.replace("_", "").strip()):
        raw = "lp_site"
    return raw


class _PreviewHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    """LP 出力フォルダをルートにしたローカルプレビュー用（デーモンスレッドで応答）"""

    daemon_threads = True
    allow_reuse_address = True


# ─────────────────────────────────────────────
# メインアプリ
# ─────────────────────────────────────────────
class LPBuilderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("920x900")
        self.minsize(800, 760)
        self.configure(bg=BG_DARK)

        # 設定読み込み
        self.config_data = self._load_config()
        self.env_data = self._load_env()

        # ウィジェット変数
        self.api_key_var = tk.StringVar(value=self.config_data.get("api_key", ""))
        _cfg_out = self.config_data.get("output_dir", "")
        _init_out = (
            str(normalize_output_dir(str(_cfg_out)))
            if str(_cfg_out).strip()
            else str((Path.home() / "LP_Projects").resolve())
        )
        self.output_dir = tk.StringVar(value=_init_out)
        cd0 = self.config_data
        _tt = normalize_target_tier(cd0.get("target_tier", "mass"))
        self.target_tier_var = tk.StringVar(
            value=TARGET_TIER_KEY_TO_LABEL.get(_tt, "庶民向け")
        )
        _cats = category_labels_for_tier(_tt)
        _cfg_cat = str(cd0.get("category_label") or "").strip()
        if _cfg_cat not in _cats:
            _cfg_cat = _cats[0]
        self.category_var = tk.StringVar(value=_cfg_cat)
        self.custom_industry_var = tk.StringVar(value=str(cd0.get("custom_industry", "")))
        self.color_var = tk.StringVar(value=list(COLOR_PRESETS.keys())[0])
        _cfg_tpl = normalize_lp_template_key(self.config_data.get("lp_template", "classic"))
        _tpl_label = next(
            (lab for lab, k in LP_TEMPLATE_OPTIONS if k == _cfg_tpl),
            LP_TEMPLATE_OPTIONS[0][0],
        )
        self.lp_template_var = tk.StringVar(value=_tpl_label)
        self.is_generating = False
        self._generate_modal: tk.Toplevel | None = None
        self._modal_progress_label: tk.Label | None = None
        self._modal_progress_pb: ttk.Progressbar | None = None
        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._last_in = 0
        self._last_out = 0
        self._last_auto_shop_text: str | None = None
        self._last_auto_service_text: str | None = None
        self._last_auto_selling_text: str | None = None

        cd = self.config_data
        env = self.env_data

        def _cfg_str(key: str, default: str) -> str:
            v = cd.get(key)
            if v is None or not str(v).strip():
                return default
            return str(v).strip()

        self.price_in_var = tk.StringVar(
            value=_cfg_str("price_input_per_mtok", DEFAULT_PRICE_INPUT_PER_MTOK)
        )
        self.price_out_var = tk.StringVar(
            value=_cfg_str("price_output_per_mtok", DEFAULT_PRICE_OUTPUT_PER_MTOK)
        )
        _jpy = cd.get("jpy_per_usd")
        self.jpy_per_usd_var = tk.StringVar(
            value="" if _jpy is None else str(_jpy).strip()
        )
        self.cost_est_in_var = tk.StringVar(value="")
        self.cost_est_out_var = tk.StringVar(value="")
        self.sftp_host_var = tk.StringVar(value=str(env.get("SFTP_HOST") or cd.get("sftp_host", "")).strip())
        self.sftp_port_var = tk.StringVar(value=str(env.get("SFTP_PORT") or cd.get("sftp_port", "22")).strip() or "22")
        self.sftp_user_var = tk.StringVar(value=str(env.get("SFTP_USER") or cd.get("sftp_user", "")).strip())
        self.sftp_pass_var = tk.StringVar(value=str(env.get("SFTP_PASS") or cd.get("sftp_pass", "")).strip())
        self.sftp_remote_dir_var = tk.StringVar(value=str(env.get("SFTP_REMOTE_DIR") or cd.get("sftp_remote_dir", "")).strip())
        self.sftp_route_url_var = tk.StringVar(
            value=str(env.get("SFTP_ROUTE_URL") or cd.get("sftp_route_url", "https://www.jitan.app/")).strip() or "https://www.jitan.app/"
        )
        self.sftp_link_var = tk.StringVar(value="")
        self._sftp_editing = False
        self._sftp_edit_entries: list[tk.Entry] = []
        self._sftp_pass_toggle_btn: tk.Button | None = None
        self.sftp_edit_btn: tk.Button | None = None
        self._last_generated_out_dir: str = ""
        self._last_generated_sheet: dict | None = None
        self._last_site_key: str = str(cd0.get("last_site_key", "") or "").strip()
        _route = self.sftp_route_url_var.get().strip().rstrip("/")
        self.cms_editor_url_var = tk.StringVar(value="")
        self.cms_admin_user_var = tk.StringVar(value=str(env.get("CMS_ADMIN_USER") or cd.get("cms_admin_user", "lp-admin")).strip())
        self.cms_admin_pass_var = tk.StringVar(
            value=str(env.get("CMS_ADMIN_TEMP_PASS") or cd.get("cms_admin_temp_pass") or CMS_SITE_INITIAL_PASSWORD).strip()
        )
        self.sftp_route_url_var.trace_add("write", lambda *_: self._refresh_cms_editor_url())

        self._build_ui()
        self._apply_style()
        self._bind_pricing_refresh()
        self._refresh_usage_display()

        self._preview_httpd: http.server.HTTPServer | None = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._refresh_cms_editor_url()

    # ─── UI構築 ───────────────────────────────
    def _build_ui(self):
        # ヘッダー
        hdr = tk.Frame(self, bg=BG_DARK, pady=12)
        hdr.pack(fill="x", padx=20)
        tk.Label(hdr, text="LP Builder", font=("Segoe UI", 20, "bold"),
                 bg=BG_DARK, fg=GOLD).pack(side="left")
        tk.Label(hdr, text=f"v{APP_VERSION}  ランディングページ自動生成",
                 font=FONT_BODY, bg=BG_DARK, fg=FG_SUB).pack(side="left", padx=12, pady=6)

        # ノートブック（タブ）
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook",        background=BG_DARK,  borderwidth=0)
        style.configure("TNotebook.Tab",    background=BG_PANEL, foreground=FG_SUB,
                        padding=[14, 6],    font=FONT_BODY)
        style.map("TNotebook.Tab",
                  background=[("selected", BG_INPUT)],
                  foreground=[("selected", GOLD)])

        self.nb = ttk.Notebook(self)

        self.tab_basic = self._make_tab("① 入力")
        self.tab_image = self._make_tab("② 画像")
        self.tab_text = self._make_tab("③ 文章")
        self.tab_sftp = self._make_tab("④ アップロード")
        self.tab_cost = self._make_tab("⑤ コスト")
        self.tab_log = self._make_tab("⑥ ログ")
        self.tab_settings = self._make_tab("⑦ 設定")

        self._build_tab_basic()
        self._build_tab_image()
        self._build_tab_text()
        self._build_tab_sftp()
        self._build_tab_cost()
        self._build_tab_log()
        self._build_tab_settings()

        # 下部：生成ボタン＋トークン概要（後で先に bottom を pack して常にウィンドウ下端に確保）
        self._build_bottom()

        # pack 順: ヘッダー ↑ / ノートブック が伸びる / 下端に生成・使用量を固定表示
        # （ノートブックのみ先に expand すると、タブが高いと生成ボタンが画面外に押し出される）
        self.bottom_bar.pack(side="bottom", fill="x", padx=16, pady=(0, 12))
        self.nb.pack(fill="both", expand=True, padx=16, pady=(0, 8))

    def _make_tab(self, label):
        frame = tk.Frame(self.nb, bg=BG_INPUT)
        self.nb.add(frame, text=label)
        return frame

    # ─── タブ①：入力 ─────────────────────────
    def _build_tab_basic(self):
        f = self.tab_basic
        canvas = tk.Canvas(f, bg=BG_INPUT, highlightthickness=0)
        sb = ttk.Scrollbar(f, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG_INPUT)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        inner_window = canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(inner_window, width=e.width),
        )
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        def _wheel(evt):
            canvas.yview_scroll(int(-1 * (evt.delta / 120)), "units")

        canvas.bind("<MouseWheel>", _wheel)
        inner.bind("<MouseWheel>", _wheel)

        p = 16
        self._section_label(inner, "ターゲット・業種（AIに推定させません）")
        row_tc = tk.Frame(inner, bg=BG_INPUT)
        row_tc.pack(fill="x", padx=p, pady=4)
        row_tc.grid_columnconfigure(0, weight=1, uniform="tc")
        row_tc.grid_columnconfigure(1, weight=1, uniform="tc")

        box_t = tk.Frame(row_tc, bg=BG_INPUT)
        box_t.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        tk.Label(box_t, text="ターゲット層", width=14, anchor="w", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        cb_tier = ttk.Combobox(
            box_t,
            textvariable=self.target_tier_var,
            values=list(TARGET_TIER_LABEL_TO_KEY.keys()),
            state="readonly",
            width=20,
        )
        cb_tier.pack(side="left", padx=4)
        cb_tier.bind("<<ComboboxSelected>>", self._on_target_tier_changed)

        box_c = tk.Frame(row_tc, bg=BG_INPUT)
        box_c.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        tk.Label(box_c, text="業種カテゴリ", width=14, anchor="w", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        tk_key = normalize_target_tier(self.target_tier_var.get())
        self.cb_category = ttk.Combobox(
            box_c,
            textvariable=self.category_var,
            values=category_labels_for_tier(tk_key),
            state="readonly",
            width=24,
        )
        self.cb_category.pack(side="left", padx=4)
        self.cb_category.bind("<<ComboboxSelected>>", self._on_category_selected)

        self.custom_row = tk.Frame(inner, bg=BG_INPUT)
        tk.Label(self.custom_row, text="業種（自由入力）", width=14, anchor="w", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        tk.Entry(
            self.custom_row,
            textvariable=self.custom_industry_var,
            bg=BG_PANEL,
            fg=FG_MAIN,
            insertbackground=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            width=42,
        ).pack(side="left", padx=4, fill="x", expand=True)

        self._toggle_custom_industry_row()

        self._section_label(inner, "店舗情報・本文メモ")
        tk.Label(
            inner,
            text="店名・住所・電話・営業時間など、LPに載せたいことをまとめて入力してください。",
            bg=BG_INPUT,
            fg=FG_SUB,
            font=("Segoe UI", 9),
            wraplength=820,
            justify="left",
        ).pack(anchor="w", padx=p)
        self.shop_text = scrolledtext.ScrolledText(
            inner,
            height=8,
            bg=BG_PANEL,
            fg=FG_MAIN,
            insertbackground=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            wrap="word",
        )
        self.shop_text.pack(fill="x", padx=p, pady=(4, 12))

        tk.Label(inner, text="サービス内容（ちょっとでOK）", bg=BG_INPUT, fg=GOLD, font=FONT_BODY).pack(anchor="w", padx=p)
        self.service_text = scrolledtext.ScrolledText(
            inner,
            height=5,
            bg=BG_PANEL,
            fg=FG_MAIN,
            insertbackground=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            wrap="word",
        )
        self.service_text.pack(fill="x", padx=p, pady=(4, 12))

        tk.Label(
            inner,
            text="推しポイント（任意・空でも可。空のときはAIが業種・ターゲットに合わせて補完）",
            bg=BG_INPUT,
            fg=GOLD,
            font=FONT_BODY,
        ).pack(anchor="w", padx=p)
        self.selling_text = scrolledtext.ScrolledText(
            inner,
            height=5,
            bg=BG_PANEL,
            fg=FG_MAIN,
            insertbackground=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            wrap="word",
        )
        self.selling_text.pack(fill="x", padx=p, pady=(4, 12))

        self._section_label(inner, "見た目（CSS）")
        row_vis = tk.Frame(inner, bg=BG_INPUT)
        row_vis.pack(fill="x", padx=p, pady=4)
        row_vis.grid_columnconfigure(0, weight=1, uniform="vis")
        row_vis.grid_columnconfigure(1, weight=1, uniform="vis")

        box_color = tk.Frame(row_vis, bg=BG_INPUT)
        box_color.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        tk.Label(box_color, text="カラー", width=14, anchor="w", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        ttk.Combobox(
            box_color,
            textvariable=self.color_var,
            values=list(COLOR_PRESETS.keys()),
            state="readonly",
            width=24,
        ).pack(side="left", padx=4)

        box_tpl = tk.Frame(row_vis, bg=BG_INPUT)
        box_tpl.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        tk.Label(box_tpl, text="LPテンプレート", width=14, anchor="w", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        ttk.Combobox(
            box_tpl,
            textvariable=self.lp_template_var,
            values=[lab for lab, _ in LP_TEMPLATE_OPTIONS],
            state="readonly",
            width=24,
        ).pack(side="left", padx=4)

        self._apply_default_input_templates_if_applicable()

    def _apply_default_input_templates_if_applicable(self) -> None:
        """プリセット業種確定時、店舗／サービス／推しの各欄へテンプレを入れる（空または直前の自動文のときのみ上書き）。"""
        cat = self.category_var.get()
        if cat == CUSTOM_CATEGORY_LABEL:
            return
        tk = normalize_target_tier(self.target_tier_var.get())

        def _fill(widget, sample: str | None, last_attr: str) -> None:
            if not sample:
                return
            cur = widget.get("1.0", "end").strip()
            last = getattr(self, last_attr)
            if cur and cur != (last or ""):
                return
            widget.delete("1.0", "end")
            widget.insert("1.0", sample)
            setattr(self, last_attr, sample)

        _fill(self.shop_text, default_shop_info_for(tk, cat), "_last_auto_shop_text")
        _fill(self.service_text, default_service_summary_for(tk, cat), "_last_auto_service_text")
        _fill(self.selling_text, default_selling_points_for(tk, cat), "_last_auto_selling_text")

    def _on_category_selected(self, _evt=None):
        self._toggle_custom_industry_row()
        self._apply_default_input_templates_if_applicable()

    def _on_target_tier_changed(self, _evt=None):
        tk = normalize_target_tier(self.target_tier_var.get())
        labs = category_labels_for_tier(tk)
        self.cb_category["values"] = labs
        cur = self.category_var.get()
        if cur not in labs:
            self.category_var.set(labs[0])
        self._toggle_custom_industry_row()
        self._apply_default_input_templates_if_applicable()

    def _toggle_custom_industry_row(self):
        if self.category_var.get() == CUSTOM_CATEGORY_LABEL:
            self.custom_row.pack(fill="x", padx=16, pady=4, before=self.shop_text)
        else:
            self.custom_row.pack_forget()

    def _build_tab_image(self):
        f = self.tab_image
        self._section_label(f, "画像編集（サーバーCMSへ移行）")
        tk.Label(
            f,
            text=(
                "ローカルアプリ内での画像編集機能は停止しました。\n"
                "画像差し替え・文言編集は、アップロード先のCMS（ブラウザ）で実施してください。"
            ),
            bg=BG_INPUT,
            fg=FG_SUB,
            font=("Segoe UI", 10),
            justify="left",
        ).pack(anchor="w", padx=16, pady=(8, 10))

        box = tk.Frame(f, bg=BG_INPUT)
        box.pack(fill="x", padx=16, pady=4)
        tk.Label(box, text="編集URL", width=14, anchor="w", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        tk.Entry(
            box,
            textvariable=self.cms_editor_url_var,
            bg=BG_PANEL,
            fg=GOLD,
            readonlybackground=BG_PANEL,
            disabledforeground=GOLD,
            insertbackground=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            state="readonly",
            width=68,
        ).pack(side="left", padx=4, fill="x", expand=True)

        row = tk.Frame(f, bg=BG_INPUT)
        row.pack(fill="x", padx=16, pady=4)
        tk.Label(row, text="site_key（フォルダ名）", width=14, anchor="w", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        tk.Entry(
            row,
            textvariable=self.cms_admin_user_var,
            bg=BG_PANEL,
            fg=FG_MAIN,
            readonlybackground=BG_PANEL,
            disabledforeground=FG_MAIN,
            insertbackground=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            state="normal",
            width=24,
        ).pack(side="left", padx=4)
        tk.Label(row, text="初期PW", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left", padx=(16, 0))
        tk.Entry(
            row,
            textvariable=self.cms_admin_pass_var,
            bg=BG_PANEL,
            fg=FG_MAIN,
            readonlybackground=BG_PANEL,
            disabledforeground=FG_MAIN,
            insertbackground=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            state="normal",
            width=30,
        ).pack(side="left", padx=4)

        row_btn = tk.Frame(f, bg=BG_INPUT)
        row_btn.pack(fill="x", padx=16, pady=(12, 4))
        tk.Button(
            row_btn,
            text="CMS情報を保存",
            command=self._save_config,
            bg=GOLD_DARK,
            fg=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            cursor="hand2",
            padx=12,
            pady=6,
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            row_btn,
            text="CMS編集画面を開く",
            command=self._open_cms_editor_url,
            bg=BG_PANEL,
            fg=GOLD,
            relief="flat",
            font=FONT_BODY,
            cursor="hand2",
            padx=12,
            pady=6,
        ).pack(side="left")

    def _open_cms_editor_url(self) -> None:
        url = (self.cms_editor_url_var.get() or "").strip()
        if not url:
            messagebox.showerror("未設定", "編集URLが未設定です。④ アップロードで ROUTEURL を設定してください。")
            return
        webbrowser.open(url)

    def _build_tab_text(self):
        f = self.tab_text
        self._section_label(f, "文章")
        tk.Label(
            f,
            text="文章テンプレート・口調・禁止語の設定機能はこのタブに追加予定です。",
            bg=BG_INPUT,
            fg=FG_SUB,
            font=("Segoe UI", 10),
            justify="left",
        ).pack(anchor="w", padx=16, pady=(8, 6))
        tk.Label(
            f,
            text="現状は「① 入力」タブの本文メモ欄を利用してください。",
            bg=BG_INPUT,
            fg=FG_SUB,
            font=("Segoe UI", 9),
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 12))

    # ─── タブ②：設定 ─────────────────────────
    def _build_tab_settings(self):
        f = self.tab_settings
        self._section_label(f, "Claude API 設定")

        row = tk.Frame(f, bg=BG_INPUT)
        row.pack(fill="x", padx=16, pady=6)
        tk.Label(row, text="APIキー", width=14, anchor="w",
                 bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        e = tk.Entry(row, textvariable=self.api_key_var, show="•",
                     bg=BG_PANEL, fg=FG_MAIN, insertbackground=FG_MAIN,
                     relief="flat", font=FONT_BODY, width=48)
        e.pack(side="left", padx=4)
        tk.Button(row, text="表示/非表示", command=lambda: e.config(show="" if e.cget("show") else "•"),
                  bg=BG_PANEL, fg=FG_SUB, relief="flat", font=FONT_BODY,
                  cursor="hand2").pack(side="left", padx=4)

        tk.Label(f, text="  ※ Anthropic Console (console.anthropic.com) で取得できます",
                 bg=BG_INPUT, fg=FG_SUB, font=("Segoe UI", 9)).pack(anchor="w", padx=16)

        self._section_label(f, "概算コスト（API 単価）")
        tk.Label(
            f,
            text="  ご利用モデルの「入力・出力量＝$」は料金ページの数値と揃えてください（キャッシュ等は含みません）。",
            bg=BG_INPUT,
            fg=FG_SUB,
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=16)
        row_p = tk.Frame(f, bg=BG_INPUT)
        row_p.pack(fill="x", padx=16, pady=6)
        tk.Label(row_p, text="入力 $/100万tok", width=14, anchor="w",
                 bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        tk.Entry(row_p, textvariable=self.price_in_var, bg=BG_PANEL, fg=FG_MAIN,
                 insertbackground=FG_MAIN, relief="flat", font=FONT_BODY, width=10).pack(side="left", padx=4)
        tk.Label(row_p, text="出力 $/100万tok",
                 bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left", padx=(16, 0))
        tk.Entry(row_p, textvariable=self.price_out_var, bg=BG_PANEL, fg=FG_MAIN,
                 insertbackground=FG_MAIN, relief="flat", font=FONT_BODY, width=10).pack(side="left", padx=4)

        row_j = tk.Frame(f, bg=BG_INPUT)
        row_j.pack(fill="x", padx=16, pady=4)
        tk.Label(row_j, text="円換算（任意）", width=14, anchor="w",
                 bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        tk.Label(row_j, text="1 USD =", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        tk.Entry(row_j, textvariable=self.jpy_per_usd_var, bg=BG_PANEL, fg=FG_MAIN,
                 insertbackground=FG_MAIN, relief="flat", font=FONT_BODY, width=8).pack(side="left", padx=4)
        tk.Label(row_j, text="円（空欄ならドル表示のみ）", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")

        self._section_label(f, "出力先フォルダ")
        row2 = tk.Frame(f, bg=BG_INPUT)
        row2.pack(fill="x", padx=16, pady=6)
        tk.Entry(row2, textvariable=self.output_dir, bg=BG_PANEL, fg=FG_MAIN,
                 insertbackground=FG_MAIN, relief="flat", font=FONT_BODY,
                 width=44).pack(side="left", padx=(0, 4))
        tk.Button(row2, text="参照...", command=self._browse_output,
                  bg=BG_PANEL, fg=GOLD, relief="flat", font=FONT_BODY,
                  cursor="hand2").pack(side="left")

        tk.Button(f, text="  設定を保存  ", command=self._save_config,
                  bg=GOLD, fg=BG_DARK, relief="flat", font=FONT_H2,
                  cursor="hand2", padx=12, pady=6).pack(pady=20)

    # ─── タブ：SFTP ───────────────────────────
    def _build_tab_sftp(self):
        f = self.tab_sftp
        self._section_label(f, "アップロード設定")
        tk.Label(
            f,
            text="公開用サーバーへの接続情報とアップロード先を設定します。",
            bg=BG_INPUT,
            fg=FG_SUB,
            font=("Segoe UI", 9),
            wraplength=820,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(4, 8))

        row1 = tk.Frame(f, bg=BG_INPUT)
        row1.pack(fill="x", padx=16, pady=4)
        tk.Label(row1, text="ホスト", width=14, anchor="w", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        ent_host = tk.Entry(
            row1,
            textvariable=self.sftp_host_var,
            bg=BG_PANEL,
            fg=FG_MAIN,
            readonlybackground=BG_PANEL,
            disabledforeground=FG_MAIN,
            insertbackground=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            width=34,
        )
        ent_host.pack(side="left", padx=4)
        tk.Label(row1, text="ポート", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left", padx=(16, 0))
        ent_port = tk.Entry(
            row1,
            textvariable=self.sftp_port_var,
            bg=BG_PANEL,
            fg=FG_MAIN,
            readonlybackground=BG_PANEL,
            disabledforeground=FG_MAIN,
            insertbackground=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            width=8,
        )
        ent_port.pack(side="left", padx=4)
        self.sftp_edit_btn = tk.Button(
            row1,
            text="接続編集",
            command=self._toggle_sftp_edit_mode,
            bg=GOLD_DARK,
            fg=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            cursor="hand2",
            padx=12,
            pady=6,
        )
        self.sftp_edit_btn.pack(side="right", padx=(8, 0))
        tk.Button(
            row1,
            text="SFTP接続テスト",
            command=self._test_sftp_connection,
            bg=BG_PANEL,
            fg=GOLD,
            relief="flat",
            font=FONT_BODY,
            cursor="hand2",
            padx=12,
            pady=6,
        ).pack(side="right", padx=(0, 8))

        row2 = tk.Frame(f, bg=BG_INPUT)
        row2.pack(fill="x", padx=16, pady=4)
        tk.Label(row2, text="ユーザー名", width=14, anchor="w", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        ent_user = tk.Entry(
            row2,
            textvariable=self.sftp_user_var,
            bg=BG_PANEL,
            fg=FG_MAIN,
            readonlybackground=BG_PANEL,
            disabledforeground=FG_MAIN,
            insertbackground=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            width=24,
        )
        ent_user.pack(side="left", padx=4)
        tk.Label(row2, text="パスワード", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left", padx=(16, 0))
        ent_pass = tk.Entry(
            row2,
            textvariable=self.sftp_pass_var,
            show="•",
            bg=BG_PANEL,
            fg=FG_MAIN,
            readonlybackground=BG_PANEL,
            disabledforeground=FG_MAIN,
            insertbackground=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            width=24,
        )
        ent_pass.pack(side="left", padx=4)
        self._sftp_pass_toggle_btn = tk.Button(
            row2,
            text="表示/非表示",
            command=lambda: ent_pass.config(show="" if ent_pass.cget("show") else "•"),
            bg=BG_PANEL,
            fg=FG_SUB,
            relief="flat",
            font=FONT_BODY,
            cursor="hand2",
        )
        self._sftp_pass_toggle_btn.pack(side="left", padx=4)

        row3 = tk.Frame(f, bg=BG_INPUT)
        row3.pack(fill="x", padx=16, pady=4)
        tk.Label(row3, text="リモートパス", width=14, anchor="w", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        ent_remote = tk.Entry(
            row3,
            textvariable=self.sftp_remote_dir_var,
            bg=BG_PANEL,
            fg=FG_MAIN,
            readonlybackground=BG_PANEL,
            disabledforeground=FG_MAIN,
            insertbackground=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            width=58,
        )
        ent_remote.pack(side="left", padx=4, fill="x", expand=True)

        row4 = tk.Frame(f, bg=BG_INPUT)
        row4.pack(fill="x", padx=16, pady=4)
        tk.Label(row4, text="ドメインROUTEURL", width=14, anchor="w", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        ent_route = tk.Entry(
            row4,
            textvariable=self.sftp_route_url_var,
            bg=BG_PANEL,
            fg=FG_MAIN,
            readonlybackground=BG_PANEL,
            disabledforeground=FG_MAIN,
            insertbackground=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            width=58,
        )
        ent_route.pack(side="left", padx=4, fill="x", expand=True)

        tk.Label(
            f,
            text="例: /var/www/html/lp_site",
            bg=BG_INPUT,
            fg=FG_SUB,
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=16, pady=(4, 16))

        row_btn = tk.Frame(f, bg=BG_INPUT)
        row_btn.pack(fill="x", padx=16, pady=(0, 8))

        row_link = tk.Frame(f, bg=BG_INPUT)
        row_link.pack(fill="x", padx=16, pady=(0, 16))
        tk.Label(row_link, text="公開URL", width=14, anchor="w", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        tk.Entry(
            row_link,
            textvariable=self.sftp_link_var,
            bg=BG_PANEL,
            fg=GOLD,
            readonlybackground=BG_PANEL,
            disabledforeground=GOLD,
            insertbackground=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            width=58,
            state="readonly",
        ).pack(side="left", padx=4, fill="x", expand=True)

        row_upload = tk.Frame(f, bg=BG_INPUT)
        row_upload.pack(fill="x", padx=16, pady=(4, 8))
        tk.Button(
            row_upload,
            text="アップロード",
            command=self._upload_latest_via_sftp,
            bg=GOLD_DARK,
            fg=FG_MAIN,
            relief="flat",
            font=FONT_BODY,
            cursor="hand2",
            padx=16,
            pady=8,
        ).pack(side="right")

        self._sftp_edit_entries = [ent_host, ent_port, ent_user, ent_pass, ent_remote, ent_route]
        self._set_sftp_editable(False)

    # ─── タブ：コスト・積算 ────────────────────
    def _build_tab_cost(self):
        f = self.tab_cost
        tk.Label(
            f,
            text="LP生成で API を呼ぶたび、トークン数・記録時点の単価・出力先などの明細を JSON に追記します。"
            "下でファイルの集計・履歴・CSV 出力ができます。試算・直近表示は ⚙ 設定の単価・為替に基づきます（実請求はコンソール参照）。",
            bg=BG_INPUT,
            fg=FG_SUB,
            font=("Segoe UI", 9),
            wraplength=840,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(16, 8))

        self._section_label(f, "API利用明細（JSON）")
        self.cost_ledger_path_label = tk.Label(
            f,
            text="",
            bg=BG_INPUT,
            fg=FG_SUB,
            font=FONT_MONO,
            wraplength=840,
            justify="left",
            anchor="w",
        )
        self.cost_ledger_path_label.pack(fill="x", padx=16, pady=(0, 4))
        row_ld = tk.Frame(f, bg=BG_INPUT)
        row_ld.pack(fill="x", padx=16, pady=(0, 8))
        tk.Button(
            row_ld,
            text="再読込",
            command=self._refresh_usage_ledger_panel,
            bg=BG_PANEL,
            fg=GOLD,
            relief="flat",
            font=FONT_BODY,
            cursor="hand2",
            padx=10,
            pady=4,
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            row_ld,
            text="JSON を別名保存…",
            command=self._export_usage_ledger_json,
            bg=BG_PANEL,
            fg=GOLD,
            relief="flat",
            font=FONT_BODY,
            cursor="hand2",
            padx=10,
            pady=4,
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            row_ld,
            text="CSV 出力…",
            command=self._export_usage_ledger_csv,
            bg=BG_PANEL,
            fg=GOLD,
            relief="flat",
            font=FONT_BODY,
            cursor="hand2",
            padx=10,
            pady=4,
        ).pack(side="left", padx=(0, 6))
        tk.Button(
            row_ld,
            text="保存フォルダを開く",
            command=self._open_usage_ledger_folder,
            bg=BG_PANEL,
            fg=GOLD,
            relief="flat",
            font=FONT_BODY,
            cursor="hand2",
            padx=10,
            pady=4,
        ).pack(side="left")

        self.cost_ledger_summary = tk.Label(
            f,
            text="",
            bg=BG_INPUT,
            fg=FG_MAIN,
            font=FONT_MONO,
            wraplength=840,
            justify="left",
            anchor="w",
        )
        self.cost_ledger_summary.pack(fill="x", padx=16, pady=(0, 8))

        tk.Label(
            f,
            text="直近の記録（最大25件・新しい順）",
            bg=BG_INPUT,
            fg=FG_SUB,
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=16, pady=(0, 4))
        self.cost_ledger_recent = scrolledtext.ScrolledText(
            f,
            height=11,
            bg=BG_PANEL,
            fg=FG_MAIN,
            font=FONT_MONO,
            relief="flat",
            wrap="word",
            state="disabled",
        )
        self.cost_ledger_recent.pack(fill="both", expand=False, padx=16, pady=(0, 16))

        self._section_label(f, "適用単価（⚙ 設定と同期）")
        self.cost_price_summary = tk.Label(
            f,
            text="",
            bg=BG_INPUT,
            fg=FG_MAIN,
            font=FONT_BODY,
            wraplength=840,
            justify="left",
            anchor="w",
        )
        self.cost_price_summary.pack(fill="x", padx=16, pady=(0, 12))

        self._section_label(f, "直近1回の積算（API 応答トークン）")
        self.cost_last_text = tk.Text(
            f,
            height=9,
            bg=BG_PANEL,
            fg=FG_MAIN,
            font=FONT_MONO,
            relief="flat",
            wrap="word",
            state="disabled",
            cursor="arrow",
        )
        self.cost_last_text.pack(fill="x", padx=16, pady=(0, 12))

        self._section_label(f, "この起動中の累計積算")
        self.cost_session_text = tk.Text(
            f,
            height=9,
            bg=BG_PANEL,
            fg=FG_MAIN,
            font=FONT_MONO,
            relief="flat",
            wrap="word",
            state="disabled",
            cursor="arrow",
        )
        self.cost_session_text.pack(fill="x", padx=16, pady=(0, 12))

        self._section_label(f, "想定トークンで試算")
        tk.Label(
            f,
            text="任意の入力・出力トークン数で、同じ単価を適用したときの概算を出します。",
            bg=BG_INPUT,
            fg=FG_SUB,
            font=("Segoe UI", 9),
        ).pack(anchor="w", padx=16)
        row_e = tk.Frame(f, bg=BG_INPUT)
        row_e.pack(fill="x", padx=16, pady=6)
        tk.Label(row_e, text="入力トークン", width=14, anchor="w",
                 bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        tk.Entry(row_e, textvariable=self.cost_est_in_var, bg=BG_PANEL, fg=FG_MAIN,
                 insertbackground=FG_MAIN, relief="flat", font=FONT_BODY, width=16).pack(side="left", padx=4)
        tk.Label(row_e, text="出力トークン", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left", padx=(16, 0))
        tk.Entry(row_e, textvariable=self.cost_est_out_var, bg=BG_PANEL, fg=FG_MAIN,
                 insertbackground=FG_MAIN, relief="flat", font=FONT_BODY, width=16).pack(side="left", padx=4)

        self.cost_estimate_result = tk.Label(
            f,
            text="",
            bg=BG_INPUT,
            fg=GOLD,
            font=FONT_MONO,
            wraplength=840,
            justify="left",
            anchor="w",
        )
        self.cost_estimate_result.pack(fill="x", padx=16, pady=(8, 16))

    # ─── タブ：ログ ───────────────────────────
    def _build_tab_log(self):
        f = self.tab_log
        tk.Label(
            f,
            text="LP 生成・API 呼び出しの履歴です。エラー内容はここに全文が出ます。",
            bg=BG_INPUT,
            fg=FG_SUB,
            font=("Segoe UI", 9),
            wraplength=820,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(16, 8))
        self.log_box = scrolledtext.ScrolledText(
            f,
            bg=BG_PANEL,
            fg=FG_MAIN,
            font=FONT_MONO,
            relief="flat",
            state="disabled",
            wrap="word",
        )
        self.log_box.pack(fill="both", expand=True, padx=16, pady=(0, 16))

    # ─── 下部：生成ボタン＋使用量 ───────────────
    def _build_bottom(self):
        self.bottom_bar = tk.Frame(self, bg=BG_DARK)

        btn_frame = tk.Frame(self.bottom_bar, bg=BG_DARK)
        btn_frame.pack(fill="x", pady=4)

        self.gen_btn = tk.Button(
            btn_frame,
            text="  ▶  LP を生成する  ",
            command=self._start_generate,
            bg=GOLD, fg=BG_DARK,
            relief="flat", font=("Segoe UI", 13, "bold"),
            cursor="hand2", padx=16, pady=10,
        )
        self.gen_btn.pack(side="right", padx=(0, 8))

        self.save_sheet_btn = tk.Button(
            btn_frame,
            text="  INPUT_SHEET.md を保存  ",
            command=self._save_input_sheet,
            bg=BG_PANEL, fg=GOLD,
            relief="flat", font=FONT_BODY,
            cursor="hand2", padx=12, pady=10,
        )
        self.save_sheet_btn.pack(side="right", padx=(0, 8))

        self.status_label = tk.Label(btn_frame, text="待機中", bg=BG_DARK, fg=FG_SUB, font=FONT_BODY)
        self.status_label.pack(side="left", padx=4)

        status_frame = tk.Frame(self.bottom_bar, bg=BG_DARK)
        status_frame.pack(fill="x", pady=(8, 0))
        self.info_label = tk.Label(
            status_frame,
            text="Info: ローカルプレビューURLをここに表示します。",
            bg=BG_DARK,
            fg=FG_SUB,
            font=FONT_BODY,
            anchor="w",
            justify="left",
        )
        self.info_label.pack(side="left", fill="x", expand=True)
        self.preview_url_label = tk.Label(
            status_frame,
            text="",
            bg=BG_DARK,
            fg=GOLD,
            font=FONT_BODY,
            cursor="hand2",
            anchor="e",
            justify="right",
        )
        self.preview_url_label.pack(side="right")
        self.preview_url_label.bind("<Button-1>", lambda _e: self._open_preview_url_from_status())

    # ─── API利用明細 JSON ─────────────────────
    def _usage_ledger_path(self) -> Path:
        return USAGE_LEDGER_JSON

    def _load_usage_ledger_raw(self) -> dict:
        p = self._usage_ledger_path()
        if not p.is_file():
            return {"version": 1, "entries": []}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {"version": 1, "entries": []}
        if not isinstance(data, dict):
            return {"version": 1, "entries": []}
        ent = data.get("entries")
        if not isinstance(ent, list):
            ent = []
        data["entries"] = ent
        data.setdefault("version", 1)
        return data

    def _save_usage_ledger_raw(self, data: dict) -> None:
        p = self._usage_ledger_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)

    def _append_usage_ledger_entry(self, result: dict, meta: dict | None) -> None:
        tin = int(result.get("input_tokens") or 0)
        tout = int(result.get("output_tokens") or 0)
        if not tin and not tout:
            return
        pin, pout = self._parse_mt_prices()
        err = result.get("error")
        entry = {
            "id": f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:10]}",
            "ts": datetime.now().isoformat(timespec="seconds"),
            "model": CLAUDE_LP_MODEL,
            "input_tokens": tin,
            "output_tokens": tout,
            "total_tokens": tin + tout,
            "error": err,
            "label": (meta or {}).get("label") or "",
            "output_dir": (meta or {}).get("output_dir") or "",
            "price_input_per_mtok": pin,
            "price_output_per_mtok": pout,
        }
        data = self._load_usage_ledger_raw()
        data.setdefault("entries", []).append(entry)
        try:
            self._save_usage_ledger_raw(data)
        except OSError as e:
            self._log(f"API利用明細の保存に失敗しました: {e}", RED_ERR)

    def _refresh_usage_ledger_panel(self) -> None:
        if not getattr(self, "cost_ledger_path_label", None):
            return
        p = self._usage_ledger_path()
        self.cost_ledger_path_label.config(text=f"保存ファイル: {p}")

        data = self._load_usage_ledger_raw()
        entries = data.get("entries") or []
        n = len(entries)
        si = so = 0
        for e in entries:
            si += int(e.get("input_tokens") or 0)
            so += int(e.get("output_tokens") or 0)

        pin, pout = self._parse_mt_prices()
        jpy = self._parse_jpy_optional()
        lines = [
            f"── ファイル集計（全 {n} 件）──",
            f"  累計トークン  入力 {si:,} / 出力 {so:,} ・ 合計 {si + so:,}",
        ]
        if pin is not None and pout is not None:
            usd = self._usd_cost(si, so, pin, pout)
            lines.append(f"  現在の設定単価での概算  ${usd:.6f} USD")
            if jpy is not None:
                lines.append(f"  （1 USD = {jpy:g} 円）  約 ¥{usd * jpy:,.4f}")
            lines.append("  ※単価は変更可能のため、過去分の実請求額とは一致しない場合があります。")
        else:
            lines.append("  概算: ⚙ 設定タブで単価を入れると USD 換算が表示されます。")

        self.cost_ledger_summary.config(text="\n".join(lines))

        recent_lines: list[str] = []
        for e in reversed(entries[-25:]):
            ts = e.get("ts") or "—"
            it = int(e.get("input_tokens") or 0)
            ot = int(e.get("output_tokens") or 0)
            lab = (e.get("label") or "").replace("\n", " ")
            if len(lab) > 48:
                lab = lab[:45] + "..."
            er = e.get("error")
            flag = "ERR" if er else "OK"
            recent_lines.append(f"{ts}  {flag}  in {it:,} / out {ot:,}  {lab}")
        recent_txt = "\n".join(recent_lines) if recent_lines else "（まだ記録がありません。LP生成が成功しトークンが返った呼び出しから追記されます。）"
        self.cost_ledger_recent.config(state="normal")
        self.cost_ledger_recent.delete("1.0", "end")
        self.cost_ledger_recent.insert("1.0", recent_txt)
        self.cost_ledger_recent.config(state="disabled")

    def _export_usage_ledger_json(self) -> None:
        data = self._load_usage_ledger_raw()
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("すべて", "*.*")],
            initialfile="lp_builder_api_usage.json",
        )
        if path:
            try:
                Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                messagebox.showinfo("エクスポート完了", f"保存しました:\n{path}")
            except OSError as e:
                messagebox.showerror("エラー", f"保存できませんでした:\n{e}")

    def _export_usage_ledger_csv(self) -> None:
        data = self._load_usage_ledger_raw()
        entries = data.get("entries") or []
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("すべて", "*.*")],
            initialfile="api_usage_ledger.csv",
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fp:
                w = csv.writer(fp)
                w.writerow(
                    [
                        "ts",
                        "id",
                        "model",
                        "input_tokens",
                        "output_tokens",
                        "total_tokens",
                        "label",
                        "output_dir",
                        "error",
                        "price_input_per_mtok",
                        "price_output_per_mtok",
                    ]
                )
                for e in entries:
                    w.writerow(
                        [
                            e.get("ts"),
                            e.get("id"),
                            e.get("model"),
                            e.get("input_tokens"),
                            e.get("output_tokens"),
                            e.get("total_tokens"),
                            e.get("label"),
                            e.get("output_dir"),
                            e.get("error"),
                            e.get("price_input_per_mtok"),
                            e.get("price_output_per_mtok"),
                        ]
                    )
            messagebox.showinfo("エクスポート完了", f"保存しました:\n{path}")
        except OSError as ex:
            messagebox.showerror("エラー", f"保存できませんでした:\n{ex}")

    def _open_usage_ledger_folder(self) -> None:
        folder = self._usage_ledger_path().parent
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        try:
            if sys.platform == "win32":
                os.startfile(str(folder))  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.run(["open", str(folder)], check=False)
            else:
                subprocess.run(["xdg-open", str(folder)], check=False)
        except Exception as e:
            messagebox.showerror("エラー", f"フォルダを開けませんでした:\n{e}")

    # ─── コストタブ更新 ───────────────────────
    @staticmethod
    def _set_readonly_text(widget: tk.Text, content: str) -> None:
        widget.config(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.config(state="disabled")

    def _fmt_cost_breakdown_detail(
        self,
        label: str,
        in_tok: int,
        out_tok: int,
        pin: float | None,
        pout: float | None,
        jpy: float | None,
    ) -> str:
        if pin is None or pout is None:
            return (
                "⚙ 設定タブで「入力 $/100万tok」「出力 $/100万tok」を入力すると、\n"
                "ドル・円での積算が表示されます。\n"
            )
        usd_in = (in_tok / 1_000_000.0) * pin
        usd_out = (out_tok / 1_000_000.0) * pout
        total_usd = usd_in + usd_out
        lines = [
            f"{label}",
            "",
            f"  入力トークン      {in_tok:>14,}  ×  ${pin:.4f} /100万  =  ${usd_in:.6f}",
            f"  出力トークン      {out_tok:>14,}  ×  ${pout:.4f} /100万  =  ${usd_out:.6f}",
            f"  {'─' * 58}",
            f"  合計（USD）                                       ${total_usd:.6f}",
        ]
        if jpy is not None:
            lines.append(f"  合計（円・1 USD = {jpy:g} 円）               ¥{total_usd * jpy:,.4f}")
        lines.extend(["", "  ※ 実請求は Anthropic Console の Usage / Billing を参照してください。"])
        return "\n".join(lines)

    def _refresh_cost_tab(self) -> None:
        if not getattr(self, "cost_last_text", None):
            return
        pin, pout = self._parse_mt_prices()
        jpy = self._parse_jpy_optional()

        if pin is None or pout is None:
            self.cost_price_summary.config(
                text="適用単価: 未設定です。⚙ 設定タブで「入力・出力の $/100万トークン」を入力し、「設定を保存」してください。"
            )
        else:
            jp_s = f"　｜　為替: 1 USD = {jpy:g} 円（任意）" if jpy is not None else "　｜　為替: 未入力（円は表示されません）"
            self.cost_price_summary.config(
                text=(
                    f"入力 ${pin:.4f} / 100万トークン　・　出力 ${pout:.4f} / 100万トークン{jp_s}"
                )
            )

        if self._last_in == 0 and self._last_out == 0:
            last_txt = (
                "まだ LP 生成の記録がありません。\n\n"
                "「LP を生成する」を実行すると、直前1回分のトークンからここに積算されます。"
            )
        else:
            last_txt = self._fmt_cost_breakdown_detail(
                "■ 直近1回",
                self._last_in,
                self._last_out,
                pin,
                pout,
                jpy,
            )

        if self._session_input_tokens == 0 and self._session_output_tokens == 0:
            sess_txt = (
                "この起動中はまだ生成がありません。\n\n"
                "同一セッションで複数回生成すると、ここに累計トークンからの積算が表示されます。"
            )
        else:
            sess_txt = self._fmt_cost_breakdown_detail(
                "■ この起動中の累計",
                self._session_input_tokens,
                self._session_output_tokens,
                pin,
                pout,
                jpy,
            )

        self._set_readonly_text(self.cost_last_text, last_txt)
        self._set_readonly_text(self.cost_session_text, sess_txt)
        self._refresh_cost_estimate()
        self._refresh_usage_ledger_panel()

    def _refresh_cost_estimate(self) -> None:
        if not getattr(self, "cost_estimate_result", None):
            return
        pin, pout = self._parse_mt_prices()
        jpy = self._parse_jpy_optional()
        try:
            raw_i = self.cost_est_in_var.get().replace(",", "").strip()
            raw_o = self.cost_est_out_var.get().replace(",", "").strip()
            ei = int(raw_i) if raw_i else 0
            eo = int(raw_o) if raw_o else 0
            if ei < 0 or eo < 0:
                raise ValueError
        except (TypeError, ValueError):
            self.cost_estimate_result.config(
                text="試算: トークン数は 0 以上の整数で入力してください。",
                fg=RED_ERR,
            )
            return

        if pin is None or pout is None:
            self.cost_estimate_result.config(
                text="試算: ⚙ 設定タブで単価を入力してください。",
                fg=FG_SUB,
            )
            return

        usd = self._usd_cost(ei, eo, pin, pout)
        lines = [
            f"試算コスト（入力 {ei:,} / 出力 {eo:,} トークン）",
            f"  概算 USD:  ${usd:.6f}",
        ]
        if jpy is not None:
            lines.append(f"  概算 JPY:  ¥{usd * jpy:,.4f}（1 USD = {jpy:g} 円）")
        else:
            lines.append("  円換算: 為替レート未入力のため USD のみ表示しています。")
        self.cost_estimate_result.config(text="\n".join(lines), fg=GOLD)

    # ─── ヘルパー ─────────────────────────────
    def _section_label(self, parent, text):
        tk.Label(parent, text=text, bg=BG_INPUT, fg=GOLD,
                 font=FONT_H2, pady=8).pack(anchor="w", padx=16)

    def _browse_output(self):
        try:
            start = str(normalize_output_dir(self.output_dir.get()))
            if not Path(start).is_dir():
                start = str(Path.home())
        except OSError:
            start = str(Path.home())
        d = filedialog.askdirectory(initialdir=start)
        if d:
            self.output_dir.set(d)

    def _parse_mt_prices(self):
        """概算用（USD / 100万トークン）。片方でも不正なら None。"""
        try:
            a = self.price_in_var.get().strip().replace(",", "")
            b = self.price_out_var.get().strip().replace(",", "")
            if not a or not b:
                return None, None
            pin, pout = float(a), float(b)
            if pin < 0 or pout < 0:
                return None, None
            return pin, pout
        except (TypeError, ValueError, tk.TclError):
            return None, None

    def _parse_jpy_optional(self):
        try:
            s = self.jpy_per_usd_var.get().strip().replace(",", "")
            if not s:
                return None
            v = float(s)
            return v if v > 0 else None
        except (TypeError, ValueError, tk.TclError):
            return None

    @staticmethod
    def _usd_cost(in_tok: int, out_tok: int, pin: float, pout: float) -> float:
        return (in_tok / 1_000_000.0) * pin + (out_tok / 1_000_000.0) * pout

    def _fmt_cost_line(self, usd: float | None, jpy_per: float | None) -> str:
        if usd is None:
            return "—（設定の単価が未入力か不正です）"
        s = f"約 ${usd:.4f}"
        if jpy_per is not None:
            s += f"  /  約 ¥{usd * jpy_per:,.2f}"
        return s

    def _bind_pricing_refresh(self):
        def _go(*_args):
            self.after_idle(self._refresh_usage_display)

        for v in (
            self.price_in_var,
            self.price_out_var,
            self.jpy_per_usd_var,
            self.cost_est_in_var,
            self.cost_est_out_var,
        ):
            v.trace_add("write", _go)

    def _usage_display_text(
        self,
        last_in: int,
        last_out: int,
        sess_in: int,
        sess_out: int,
        last_usd: float | None,
        sess_usd: float | None,
        jpy_per: float | None,
    ) -> str:
        def line_tok(tag: str, a: int, b: int) -> str:
            if not a and not b:
                return f"  {tag}: —（未計上）"
            return f"  {tag}: 入力 {a:,} / 出力 {b:,} ・ 合計 {a + b:,}"

        def line_money(tag: str, usd: float | None) -> str:
            return f"  {tag}: {self._fmt_cost_line(usd, jpy_per)}"

        return (
            line_tok("直近の生成（トークン）", last_in, last_out)
            + "\n"
            + line_money("直近の概算", last_usd)
            + "\n"
            + line_tok("この起動中の累計（トークン）", sess_in, sess_out)
            + "\n"
            + line_money("累計の概算", sess_usd)
            + "\n  ※ あくまで概算です。割引・キャッシュ・レートは含みません。"
            " 正確な請求は console.anthropic.com の Usage / Billing を参照してください。"
        )

    def _refresh_usage_display(self) -> None:
        pin, pout = self._parse_mt_prices()
        jpy = self._parse_jpy_optional()
        if pin is not None and pout is not None:
            last_usd = self._usd_cost(self._last_in, self._last_out, pin, pout)
            sess_usd = self._usd_cost(
                self._session_input_tokens, self._session_output_tokens, pin, pout
            )
        else:
            last_usd = None
            sess_usd = None
        if getattr(self, "usage_label", None):
            self.usage_label.config(
                text=self._usage_display_text(
                    self._last_in,
                    self._last_out,
                    self._session_input_tokens,
                    self._session_output_tokens,
                    last_usd,
                    sess_usd,
                    jpy,
                )
            )
        self._refresh_cost_tab()

    def _apply_usage_stats(self, result: dict, meta: dict | None = None) -> None:
        """generate_lp の戻り値からトークン表示を更新（メインスレッド専用）"""
        tin = int(result.get("input_tokens") or 0)
        tout = int(result.get("output_tokens") or 0)
        if tin or tout:
            self._session_input_tokens += tin
            self._session_output_tokens += tout
            self._last_in = tin
            self._last_out = tout
            self._append_usage_ledger_entry(result, meta)
        self._refresh_usage_display()

    def _log(self, msg, color=None):
        """ログとステータスを更新。ワーカースレッドから呼んでもメインスレッドで実行される。"""
        if threading.current_thread() is not threading.main_thread():
            self.after(0, lambda m=msg, c=color: self._log(m, c))
            return
        self.log_box.config(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{ts}] {msg}\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")
        self.status_label.config(text=msg[:60])
        self._update_generate_modal_text(msg)
        self.update_idletasks()

    def _open_generate_modal(self) -> None:
        """LP生成中のモーダル（不定プログレス＋メッセージ）。生成開始時のみメインスレッドから呼ぶ。"""
        self._close_generate_modal()
        top = tk.Toplevel(self)
        top.title("LP 生成中")
        top.configure(bg=BG_PANEL)
        top.resizable(False, False)
        top.transient(self)
        margin = tk.Frame(top, bg=BG_PANEL, padx=28, pady=22)
        margin.pack(fill="both", expand=True)
        tk.Label(
            margin,
            text="LP を生成しています",
            font=FONT_H2,
            bg=BG_PANEL,
            fg=GOLD,
        ).pack(anchor="w")
        tk.Label(
            margin,
            text="Claude API の応答を待っています。完了までこのままにしてください。",
            font=("Segoe UI", 9),
            bg=BG_PANEL,
            fg="#d0d0d0",
            wraplength=400,
            justify="left",
        ).pack(anchor="w", pady=(4, 12))
        # 不定プログレスのトラックとバーのコントラストを上げる（既定の薄灰×薄灰だと視認性が悪い）
        _pb_style = ttk.Style(self)
        _lp_pb = "LpModal.Horizontal.TProgressbar"
        try:
            _base = "Horizontal.TProgressbar"
            try:
                _lay = _pb_style.layout(_base)
                if _lay:
                    _pb_style.layout(_lp_pb, _lay)
            except tk.TclError:
                pass
            _pb_style.configure(
                _lp_pb,
                troughcolor="#141414",
                background=GOLD,
                bordercolor="#141414",
                lightcolor="#f0dfa0",
                darkcolor=GOLD_DARK,
                thickness=14,
            )
        except tk.TclError:
            _lp_pb = "Horizontal.TProgressbar"
        pb = ttk.Progressbar(
            margin,
            mode="indeterminate",
            length=400,
            maximum=100,
            style=_lp_pb,
        )
        pb.pack(fill="x", pady=(0, 10))
        pb.start(14)
        self._modal_progress_pb = pb
        lbl = tk.Label(
            margin,
            text="準備中…",
            font=FONT_MONO,
            bg=BG_PANEL,
            fg=FG_MAIN,
            wraplength=420,
            justify="left",
        )
        lbl.pack(anchor="w")
        self._modal_progress_label = lbl
        self._generate_modal = top
        top.protocol("WM_DELETE_WINDOW", self._on_generate_modal_close_attempt)
        top.grab_set()
        self.update_idletasks()
        top.update_idletasks()
        px = self.winfo_rootx() + max(20, (self.winfo_width() - 460) // 2)
        py = self.winfo_rooty() + max(40, self.winfo_height() // 5)
        top.geometry(f"480x220+{px}+{py}")

    def _on_generate_modal_close_attempt(self) -> None:
        messagebox.showinfo(
            "生成中",
            "LP の生成が完了するまでお待ちください。",
            parent=self._generate_modal,
        )

    def _update_generate_modal_text(self, msg: str) -> None:
        lbl = getattr(self, "_modal_progress_label", None)
        if lbl is None:
            return
        try:
            if lbl.winfo_exists():
                lbl.config(text=(msg or "")[:300])
        except tk.TclError:
            pass

    def _close_generate_modal(self) -> None:
        """生成終了時にモーダルを閉じる（メインスレッドから）。"""
        pb = getattr(self, "_modal_progress_pb", None)
        if pb is not None:
            try:
                pb.stop()
            except tk.TclError:
                pass
        self._modal_progress_pb = None
        self._modal_progress_label = None
        top = getattr(self, "_generate_modal", None)
        self._generate_modal = None
        if top is None:
            return
        try:
            if top.winfo_exists():
                try:
                    top.grab_release()
                except tk.TclError:
                    pass
                top.destroy()
        except tk.TclError:
            pass

    def _collect_sheet(self) -> dict:
        """GUIの入力値を辞書にまとめる（業種は UI で確定済み）"""
        color_name = self.color_var.get()
        color = COLOR_PRESETS.get(color_name, list(COLOR_PRESETS.values())[0])

        tk = normalize_target_tier(self.target_tier_var.get())
        cat_label = self.category_var.get()
        preset_id = resolve_preset_id(tk, cat_label)

        if cat_label == CUSTOM_CATEGORY_LABEL:
            # industry_type = 中分類／個別コード（カスタム）
            industry_type_code = "custom"
            industry_group = "custom"
            industry_label = self.custom_industry_var.get().strip()
            preset_id_final = None
        else:
            if not preset_id:
                fallback_label = category_labels_for_tier(tk)[0]
                preset_id = resolve_preset_id(tk, fallback_label)
            preset_id_final = preset_id
            industry_type_code = preset_id
            industry_label = cat_label
            industry_group = (
                str(INDUSTRY_PRESETS[preset_id]["industry_group"]) if preset_id else "custom"
            )

        shop_info = self.shop_text.get("1.0", "end").strip()
        service_summary = self.service_text.get("1.0", "end").strip()
        selling_points = self.selling_text.get("1.0", "end").strip()

        return {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "target_tier": tk,
            "industry_group": industry_group,
            "industry_type": industry_type_code,
            "industry_label": industry_label or "（未入力）",
            "preset_id": preset_id_final,
            "shop_info": shop_info,
            "service_summary": service_summary,
            "selling_points": selling_points,
            "color": color,
            "color_name": color_name,
            "lp_template": normalize_lp_template_key(
                LP_TEMPLATE_LABEL_TO_KEY.get(self.lp_template_var.get())
            ),
        }

    # ─── 生成処理 ─────────────────────────────
    def _start_generate(self):
        if self.is_generating:
            return
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror("エラー", "APIキーを設定タブに入力してください。")
            self.nb.select(self.tab_settings)
            return

        shop = self.shop_text.get("1.0", "end").strip()
        if not shop:
            messagebox.showerror(
                "エラー",
                "① 入力タブの「店舗情報・本文メモ」に、少なくとも店名や基本情報を入力してください。",
            )
            self.nb.select(self.tab_basic)
            return

        if self.category_var.get() == CUSTOM_CATEGORY_LABEL:
            if not self.custom_industry_var.get().strip():
                messagebox.showerror(
                    "エラー",
                    "業種カテゴリが「その他」のときは、「業種（自由入力）」を入力してください。",
                )
                self.nb.select(self.tab_basic)
                return

        self.is_generating = True
        self.gen_btn.config(state="disabled", text="  生成中...  ", bg=BG_PANEL, fg=FG_SUB)
        self._open_generate_modal()
        sheet = self._collect_sheet()
        self._last_generated_sheet = dict(sheet)
        threading.Thread(target=self._generate_thread, args=(sheet, api_key), daemon=True).start()

    def _generate_thread(self, sheet: dict, api_key: str):
        self._log("LP生成を開始します...")

        # 出力ディレクトリ作成（出力先に「例:」が混入していても正規化）
        site_name = safe_site_dir_segment(sheet)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        # 各LPの一意性（URLパス・サーバー登録用）。ディレクトリ名のサフィックスに使う
        lp_token = secrets.token_hex(12)  # 24 hex
        try:
            root = normalize_output_dir(self.output_dir.get())
            root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self._log(f"出力先フォルダを作成できません: {e}", RED_ERR)
            self.after(0, self._on_generate_done, False, "")
            return
        out_dir = root / f"{site_name}_{ts}_{lp_token}"
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self._log(f"出力フォルダを作成できません: {e}", RED_ERR)
            self.after(0, self._on_generate_done, False, str(root))
            return
        self._log(f"出力先: {out_dir}")
        self._log(f"lp_token: {lp_token}（public URL / サーバー識別子）")

        # INPUT_SHEET.md 保存
        md_path = out_dir / "INPUT_SHEET.md"
        md_path.write_text(build_input_sheet_md(sheet), encoding="utf-8")
        self._log("INPUT_SHEET.md を保存しました")

        # Claude API 呼び出し
        meta = _usage_meta_from_sheet(sheet, out_dir)
        result = generate_lp(sheet, api_key, on_progress=self._log)
        self.after(0, lambda r=result, m=meta: self._apply_usage_stats(r, m))

        if result["error"]:
            self._log(f"エラー: {result['error']}", RED_ERR)
            self.after(0, self._on_generate_done, False, str(out_dir))
            return

        # index.html 保存（キャッシュバスト: 同梱 CSS/JS の参照に ?v= を付与）
        html_path = out_dir / "index.html"
        cache_ver = ts.replace("_", "")
        raw_html = _strip_navbar_inline_styles(result["html"])
        raw_html = _ensure_navbar_class(raw_html)
        raw_html = _normalize_common_anchor_aliases(raw_html)
        raw_html = _ensure_custom_images_enabled(raw_html)
        html_final = _inject_asset_cache_bust(raw_html, cache_ver)
        html_path.write_text(html_final, encoding="utf-8")
        self._log(
            f"index.html を保存しました（{len(html_final):,} 文字・style/script に ?v={cache_ver}）"
        )
        for w in _hash_anchor_mismatches(html_final):
            self._log(f"アンカー確認: {w}", WARN_MSG)

        # 共有ファイルをコピー（選択テーマの style.css を style.css 名で配置）
        self._copy_shared_files(out_dir, sheet, lp_token=lp_token)

        self._log("完了！localhost でプレビューを開きます...")
        self.after(0, self._on_generate_done, True, str(out_dir))

    def _cms_password_bcrypt_hash(self, plain: str) -> str:
        """PHP password_hash(PASSWORD_DEFAULT) と互換の bcrypt。"""
        import bcrypt  # type: ignore

        return bcrypt.hashpw(
            plain.encode("utf-8"),
            bcrypt.gensalt(rounds=10),
        ).decode("ascii")

    def _write_cms_credentials(self, custom_dir: Path, *, site_key: str, lp_token: str) -> None:
        """サーバー CMS が参照する LP 直下の資格情報（users.json は使わない）。"""
        plain = (self.cms_admin_pass_var.get().strip() or CMS_SITE_INITIAL_PASSWORD)
        must_change = plain == CMS_SITE_INITIAL_PASSWORD
        cred = {
            "lp_token": lp_token.lower(),
            "site_key": site_key,
            "password_hash": self._cms_password_bcrypt_hash(plain),
            "must_change_password": must_change,
        }
        (custom_dir / "cms_credentials.json").write_text(
            json.dumps(cred, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self._log("custom/cms_credentials.json を保存（CMS の site-login 用）")

    def _copy_shared_files(self, out_dir: Path, sheet: dict, *, lp_token: str = ""):
        """選択テーマの CSS を style.css としてコピーし、script.js / pexels.js を同梱。custom/lp_meta.json でサーバーへトークンを引き渡す。"""
        import shutil

        tpl = normalize_lp_template_key(sheet.get("lp_template"))
        css_file = LP_TEMPLATE_STYLE_FILES.get(tpl, "classic.css")
        css_src = APP_DIR / "template_styles" / css_file
        if not css_src.is_file():
            css_src = APP_DIR / "style.css"
        shutil.copy2(css_src, out_dir / "style.css")
        self._log(f"style.css をコピーしました（テーマ: {tpl}）")

        for fname in SHARED_FILES:
            src = APP_DIR / fname
            if src.exists():
                shutil.copy2(src, out_dir / fname)
                self._log(f"{fname} をコピーしました")
            else:
                self._log(f"警告: {src} が見つかりません（スキップ）")

        custom_dir = out_dir / "custom"
        custom_dir.mkdir(exist_ok=True)
        if lp_token:
            site_key = out_dir.name
            meta = {
                "lp_token": lp_token,
                "site_key": site_key,
                "generated_at": datetime.now().astimezone().replace(microsecond=0).isoformat(),
            }
            (custom_dir / "lp_meta.json").write_text(
                json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            self._log("custom/lp_meta.json を保存（サーバー側でサイト識別用）")
            self._write_cms_credentials(custom_dir, site_key=site_key, lp_token=lp_token)
        ex = APP_DIR / "custom_config.example.json"
        if ex.exists():
            shutil.copy2(ex, custom_dir / "config.example.json")
            self._log(
                "custom/config.example.json を配置しました。"
                "必要なら custom/config.json と画像を追加すると上書きできます。"
            )

    def _stop_preview_server(self) -> None:
        """直前まで使っていたローカルプレビュー用 HTTP サーバーを止める"""
        if self._preview_httpd is None:
            return
        try:
            self._preview_httpd.shutdown()
        except Exception:
            pass
        try:
            self._preview_httpd.server_close()
        except Exception:
            pass
        self._preview_httpd = None

    def _open_local_preview(self, out_dir: str) -> str | None:
        """
        出力フォルダをルートとする http://127.0.0.1:*/index.html を開く。
        失敗時は file:// にフォールバックし、そのURL文字列を返す。
        """
        root = Path(out_dir).resolve()
        index_path = root / "index.html"
        if not index_path.is_file():
            return None
        self._stop_preview_server()
        try:
            handler = functools.partial(
                http.server.SimpleHTTPRequestHandler,
                directory=str(root),
            )
            self._preview_httpd = _PreviewHTTPServer(("127.0.0.1", 0), handler)
            port = self._preview_httpd.server_address[1]
            threading.Thread(
                target=self._preview_httpd.serve_forever,
                name="lp-builder-preview-http",
                daemon=True,
            ).start()
            url = f"http://127.0.0.1:{port}/index.html"
            webbrowser.open(url)
            self._log(f"ローカルプレビュー: {url}")
            if getattr(self, "preview_url_label", None):
                self.preview_url_label.config(text=url)
            if getattr(self, "info_label", None):
                self.info_label.config(text="Status: 生成完了 / クリックでプレビューを開く")
            return url
        except Exception as e:
            self._log(f"ローカルサーバー起動に失敗: {e} — file:// で開きます", RED_ERR)
            fu = index_path.as_uri()
            webbrowser.open(fu)
            if getattr(self, "preview_url_label", None):
                self.preview_url_label.config(text=fu)
            if getattr(self, "info_label", None):
                self.info_label.config(text="Status: file:// でプレビューを開きました")
            return fu

    def _open_preview_url_from_status(self) -> None:
        t = ""
        if getattr(self, "preview_url_label", None):
            t = (self.preview_url_label.cget("text") or "").strip()
        if t:
            webbrowser.open(t)

    def _on_close(self) -> None:
        self._stop_preview_server()
        self.destroy()

    def _focus_log_tab(self) -> None:
        try:
            self.nb.select(self.tab_log)
        except tk.TclError:
            pass

    def _on_generate_done(self, success: bool, out_dir: str):
        self.is_generating = False
        self._close_generate_modal()
        self.gen_btn.config(state="normal", text="  ▶  LP を生成する  ", bg=GOLD, fg=BG_DARK)
        if success:
            self._last_generated_out_dir = out_dir
            self._set_last_site_key(str(Path(out_dir).name))
            self._apply_cms_login_from_lp_meta(out_dir)
            preview_url = self._open_local_preview(out_dir)
            msg_extra = (
                f"\nプレビュー:\n{preview_url}\n"
                if preview_url
                else "\n（ブラウザでプレビューを開けませんでした）\n"
            )
            messagebox.showinfo(
                "生成完了",
                f"LPが生成されました！\n\n保存先:\n{out_dir}{msg_extra}",
            )
        else:
            self._focus_log_tab()
            messagebox.showerror(
                "生成失敗",
                "LP生成中にエラーが発生しました。\n\n「⑤ ログ」タブに詳細を表示しました。",
            )

    def _save_input_sheet(self):
        sheet = self._collect_sheet()
        md = build_input_sheet_md(sheet)
        path = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("テキスト", "*.txt")],
            initialfile="INPUT_SHEET.md",
        )
        if path:
            Path(path).write_text(md, encoding="utf-8")
            self._log(f"INPUT_SHEET.md を保存: {path}")
            messagebox.showinfo("保存完了", f"INPUT_SHEET.md を保存しました:\n{path}")

    # ─── 設定保存/読み込み ────────────────────
    def _save_config(self):
        _out = str(normalize_output_dir(self.output_dir.get()))
        self.output_dir.set(_out)
        data = {
            "api_key":    self.api_key_var.get(),
            "output_dir": _out,
            "price_input_per_mtok":  self.price_in_var.get().strip(),
            "price_output_per_mtok": self.price_out_var.get().strip(),
            "jpy_per_usd":           self.jpy_per_usd_var.get().strip(),
            "sftp_host": self.sftp_host_var.get().strip(),
            "sftp_port": self.sftp_port_var.get().strip(),
            "sftp_user": self.sftp_user_var.get().strip(),
            "sftp_pass": self.sftp_pass_var.get().strip(),
            "sftp_remote_dir": self.sftp_remote_dir_var.get().strip(),
            "sftp_route_url": self.sftp_route_url_var.get().strip(),
            "cms_admin_user": self.cms_admin_user_var.get().strip(),
            "cms_admin_temp_pass": self.cms_admin_pass_var.get().strip(),
            "last_site_key": self._last_site_key,
            "lp_template": normalize_lp_template_key(
                LP_TEMPLATE_LABEL_TO_KEY.get(self.lp_template_var.get())
            ),
            "target_tier": normalize_target_tier(self.target_tier_var.get()),
            "category_label": self.category_var.get(),
            "custom_industry": self.custom_industry_var.get().strip(),
        }
        CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._save_sftp_env(silent=True)
        self._log("設定を保存しました")
        self._refresh_usage_display()
        messagebox.showinfo("保存完了", "設定を保存しました。")

    def _parse_env_text(self, text: str) -> dict[str, str]:
        out: dict[str, str] = {}
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip()
            if len(v) >= 2 and ((v[0] == '"' and v[-1] == '"') or (v[0] == "'" and v[-1] == "'")):
                v = v[1:-1]
            out[k] = v
        return out

    def _ensure_windows_token(self) -> bytes:
        try:
            if WIN_TOKEN_FILE.is_file():
                b = WIN_TOKEN_FILE.read_bytes()
                if len(b) >= 16:
                    return b
        except Exception:
            pass
        WIN_TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        b = os.urandom(32)
        WIN_TOKEN_FILE.write_bytes(b)
        return b

    def _dpapi_encrypt(self, plain_text: str) -> str:
        if os.name != "nt":
            return plain_text
        blob = plain_text.encode("utf-8")
        entropy = self._ensure_windows_token()

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

        in_buf = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        ent_buf = (ctypes.c_ubyte * len(entropy)).from_buffer_copy(entropy)
        in_blob = DATA_BLOB(len(blob), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_ubyte)))
        ent_blob = DATA_BLOB(len(entropy), ctypes.cast(ent_buf, ctypes.POINTER(ctypes.c_ubyte)))
        out_blob = DATA_BLOB()

        flags = 0x01  # CRYPTPROTECT_UI_FORBIDDEN
        ok = ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(in_blob),
            None,
            ctypes.byref(ent_blob),
            None,
            None,
            flags,
            ctypes.byref(out_blob),
        )
        if not ok:
            raise OSError("CryptProtectData failed")
        try:
            out_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        return "LPB_ENC_V1:" + base64.b64encode(out_bytes).decode("ascii")

    def _dpapi_decrypt(self, text: str) -> str:
        if os.name != "nt":
            return text
        if not text.startswith("LPB_ENC_V1:"):
            return text
        enc = text[len("LPB_ENC_V1:") :].strip()
        cipher = base64.b64decode(enc)
        entropy = self._ensure_windows_token()

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [("cbData", ctypes.c_uint32), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]

        in_buf = (ctypes.c_ubyte * len(cipher)).from_buffer_copy(cipher)
        ent_buf = (ctypes.c_ubyte * len(entropy)).from_buffer_copy(entropy)
        in_blob = DATA_BLOB(len(cipher), ctypes.cast(in_buf, ctypes.POINTER(ctypes.c_ubyte)))
        ent_blob = DATA_BLOB(len(entropy), ctypes.cast(ent_buf, ctypes.POINTER(ctypes.c_ubyte)))
        out_blob = DATA_BLOB()

        flags = 0x01  # CRYPTPROTECT_UI_FORBIDDEN
        ok = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(in_blob),
            None,
            ctypes.byref(ent_blob),
            None,
            None,
            flags,
            ctypes.byref(out_blob),
        )
        if not ok:
            raise OSError("CryptUnprotectData failed")
        try:
            out_bytes = ctypes.string_at(out_blob.pbData, out_blob.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out_blob.pbData)
        return out_bytes.decode("utf-8")

    def _load_env(self) -> dict:
        if not ENV_FILE.is_file():
            return {}
        try:
            text = ENV_FILE.read_text(encoding="utf-8")
        except Exception:
            return {}
        if text.startswith("LPB_ENC_V1:"):
            try:
                dec = self._dpapi_decrypt(text)
                return self._parse_env_text(dec)
            except Exception:
                return {}
        return self._parse_env_text(text)

    def _save_sftp_env(self, silent: bool = False) -> None:
        data = self._load_env()
        data["SFTP_HOST"] = self.sftp_host_var.get().strip()
        data["SFTP_PORT"] = self.sftp_port_var.get().strip() or "22"
        data["SFTP_USER"] = self.sftp_user_var.get().strip()
        data["SFTP_PASS"] = self.sftp_pass_var.get().strip()
        data["SFTP_REMOTE_DIR"] = self.sftp_remote_dir_var.get().strip()
        data["SFTP_ROUTE_URL"] = self.sftp_route_url_var.get().strip() or "https://www.jitan.app/"
        data["CMS_ADMIN_USER"] = self.cms_admin_user_var.get().strip() or "lp-admin"
        data["CMS_ADMIN_TEMP_PASS"] = self.cms_admin_pass_var.get().strip() or CMS_SITE_INITIAL_PASSWORD
        lines = [f'{k}="{str(v).replace(chr(34), "\\\"")}"' for k, v in sorted(data.items())]
        plain = "\n".join(lines) + "\n"
        if os.name == "nt":
            ENV_FILE.write_text(self._dpapi_encrypt(plain), encoding="utf-8")
        else:
            ENV_FILE.write_text(plain, encoding="utf-8")
        self.env_data = dict(data)
        self._refresh_cms_editor_url()
        if os.name == "nt":
            self._log(f".env を暗号化して保存しました: {ENV_FILE}")
        else:
            self._log(f".env を保存しました: {ENV_FILE}")
        if not silent:
            messagebox.showinfo("保存完了", f"SFTP設定を .env に保存しました。\n{ENV_FILE}")

    def _set_last_site_key(self, site_key: str) -> None:
        """直近の LP フォルダ名。CMS を ?site_key= で開く用。"""
        self._last_site_key = (site_key or "").strip()
        self._refresh_cms_editor_url()
        try:
            data = dict(self._load_config())
        except Exception:
            return
        data["last_site_key"] = self._last_site_key
        self.config_data = data
        try:
            CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        except Exception:
            pass

    def _apply_cms_login_from_lp_meta(self, out_dir: str) -> None:
        """生成済み LP のフォルダ名（site_key）と初期パスを②に反映（CMS は site_key + cms_credentials のパスワード）。"""
        root = Path(out_dir)
        sk = root.name.strip()
        if sk:
            self.cms_admin_user_var.set(sk)
        self.cms_admin_pass_var.set(CMS_SITE_INITIAL_PASSWORD)
        self._refresh_cms_editor_url()

    def _refresh_cms_editor_url(self) -> None:
        route = (self.sftp_route_url_var.get() or "").strip().rstrip("/")
        if not route:
            self.cms_editor_url_var.set("")
            return
        base = f"{route}/cms/admin/"
        sk = (self._last_site_key or "").strip()
        if sk:
            q = urllib.parse.urlencode({"site_key": sk})
            self.cms_editor_url_var.set(f"{base}?{q}")
        else:
            self.cms_editor_url_var.set(base)

    def _test_sftp_connection(self) -> None:
        host = self.sftp_host_var.get().strip()
        user = self.sftp_user_var.get().strip()
        pwd = self.sftp_pass_var.get()
        port_s = self.sftp_port_var.get().strip() or "22"
        try:
            port = int(port_s)
        except ValueError:
            messagebox.showerror("入力エラー", "SFTPポートは整数で入力してください。")
            return
        if not host or not user:
            messagebox.showerror("入力エラー", "SFTPホストとユーザー名は必須です。")
            return
        self._save_sftp_env(silent=True)
        self._log(f"SFTP接続テスト開始: {user}@{host}:{port}")
        try:
            import paramiko  # type: ignore
        except Exception:
            messagebox.showerror(
                "依存不足",
                "paramiko が見つかりません。`pip install -r requirements.txt` を実行してください。",
            )
            return
        try:
            tr = paramiko.Transport((host, port))
            tr.banner_timeout = 8
            tr.connect(username=user, password=pwd)
            tr.close()
            self._log("SFTP接続テスト: 成功", GREEN_OK)
            messagebox.showinfo("接続テスト", "SFTP接続に成功しました。")
        except Exception as e:
            self._log(f"SFTP接続テスト: 失敗 ({e})", RED_ERR)
            messagebox.showerror("接続テスト失敗", f"SFTP接続に失敗しました。\n\n{e}")

    def _set_sftp_editable(self, editable: bool) -> None:
        state = "normal" if editable else "readonly"
        for ent in self._sftp_edit_entries:
            try:
                ent.config(state=state)
            except tk.TclError:
                pass
        if self._sftp_pass_toggle_btn is not None:
            try:
                self._sftp_pass_toggle_btn.config(state="normal" if editable else "disabled")
            except tk.TclError:
                pass

    def _toggle_sftp_edit_mode(self) -> None:
        if not self._sftp_editing:
            ok = messagebox.askyesno(
                "接続情報を編集",
                "SFTP接続情報を編集しますか？\n\n「はい」で編集モードに切り替えます。",
            )
            if not ok:
                return
            self._sftp_editing = True
            self._set_sftp_editable(True)
            if self.sftp_edit_btn is not None:
                self.sftp_edit_btn.config(text="保存", bg=GOLD, fg=BG_DARK)
            self._log("SFTP接続情報: 編集モードに切り替えました")
            return

        self._sftp_editing = False
        self._set_sftp_editable(False)
        if self.sftp_edit_btn is not None:
            self.sftp_edit_btn.config(text="接続編集", bg=GOLD_DARK, fg=FG_MAIN)
        self._log("SFTP接続情報の編集を終了しました", GREEN_OK)
        messagebox.showinfo("保存完了", "接続設定を反映しました（.env への書き出しは未実行）。")

    @staticmethod
    def _read_lp_meta(out_dir: Path) -> dict:
        p = out_dir / "custom" / "lp_meta.json"
        if not p.is_file():
            return {}
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _make_site_info_pdf(self, out_dir: Path, site_key: str, *, lp_token: str = "") -> Path:
        """
        簡易 PDF（ASCII中心）を生成。サイト情報とリンクを記録してアップロード対象にする。
        site_key はリモートURLパスに使うディレクトリ名（out_dir.name と同じ）。
        """
        info_path = out_dir / "SITE_INFO.pdf"
        route = self.sftp_route_url_var.get().strip().rstrip("/")
        link = f"{route}/{site_key}/index.html" if route else f"/{site_key}/index.html"
        lines = [
            "LP Builder Upload Report",
            f"site_key: {site_key}",
            f"lp_token: {lp_token or '(not in lp_meta.json)'}",
            f"Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Local Path: {out_dir}",
            f"Public URL: {link}",
            f"Target Host: {self.sftp_host_var.get().strip()}:{self.sftp_port_var.get().strip() or '22'}",
            f"Remote Path: {self.sftp_remote_dir_var.get().strip()}",
        ]

        def esc(s: str) -> str:
            return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

        content_lines = ["BT", "/F1 11 Tf", "50 790 Td", "14 TL"]
        for ln in lines:
            safe = esc(ln.encode("latin-1", "replace").decode("latin-1"))
            content_lines.append(f"({safe}) Tj")
            content_lines.append("T*")
        content_lines.append("ET")
        stream = ("\n".join(content_lines) + "\n").encode("latin-1")

        objs: list[bytes] = []
        objs.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
        objs.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
        objs.append(
            b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj\n"
        )
        objs.append(b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")
        objs.append(
            b"5 0 obj << /Length " + str(len(stream)).encode("ascii") + b" >> stream\n" + stream + b"endstream\nendobj\n"
        )

        out = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        offsets = [0]
        for o in objs:
            offsets.append(len(out))
            out += o
        xref_pos = len(out)
        out += f"xref\n0 {len(objs)+1}\n".encode("ascii")
        out += b"0000000000 65535 f \n"
        for off in offsets[1:]:
            out += f"{off:010d} 00000 n \n".encode("ascii")
        out += (
            b"trailer << /Size "
            + str(len(objs)+1).encode("ascii")
            + b" /Root 1 0 R >>\nstartxref\n"
            + str(xref_pos).encode("ascii")
            + b"\n%%EOF\n"
        )
        info_path.write_bytes(out)
        return info_path

    def _sftp_mkdir_p(self, sftp, remote_dir: str) -> None:
        cur = "/"
        for part in [p for p in remote_dir.split("/") if p]:
            cur = posixpath.join(cur, part)
            try:
                sftp.stat(cur)
            except Exception:
                sftp.mkdir(cur)

    def _sftp_upload_dir(self, sftp, local_dir: Path, remote_dir: str) -> None:
        self._sftp_mkdir_p(sftp, remote_dir)
        for root, dirs, files in os.walk(local_dir):
            rel = Path(root).relative_to(local_dir)
            remote_root = remote_dir if str(rel) == "." else posixpath.join(remote_dir, str(rel).replace("\\", "/"))
            self._sftp_mkdir_p(sftp, remote_root)
            for d in dirs:
                self._sftp_mkdir_p(sftp, posixpath.join(remote_root, d))
            for fn in files:
                lp = Path(root) / fn
                rp = posixpath.join(remote_root, fn)
                sftp.put(str(lp), rp)

    def _upload_latest_via_sftp(self) -> None:
        out_dir_s = (self._last_generated_out_dir or "").strip()
        if not out_dir_s or not Path(out_dir_s).is_dir():
            messagebox.showerror("アップロード不可", "先にLPを生成してください（保存先が見つかりません）。")
            return
        host = self.sftp_host_var.get().strip()
        user = self.sftp_user_var.get().strip()
        pwd = self.sftp_pass_var.get()
        remote_base = self.sftp_remote_dir_var.get().strip()
        route = self.sftp_route_url_var.get().strip().rstrip("/")
        if not host or not user or not remote_base:
            messagebox.showerror("入力エラー", "SFTPホスト・ユーザー名・リモートパスは必須です。")
            return
        try:
            port = int((self.sftp_port_var.get().strip() or "22"))
        except ValueError:
            messagebox.showerror("入力エラー", "SFTPポートは整数で入力してください。")
            return
        try:
            import paramiko  # type: ignore
        except Exception:
            messagebox.showerror("依存不足", "paramiko が見つかりません。`pip install -r requirements.txt` を実行してください。")
            return

        out_dir = Path(out_dir_s)
        site_key = out_dir.name
        meta = self._read_lp_meta(out_dir)
        lp_tok = (meta.get("lp_token") or "").strip() if isinstance(meta, dict) else ""
        remote_release_dir = posixpath.join(remote_base.rstrip("/"), site_key)
        pdf_path = self._make_site_info_pdf(out_dir, site_key, lp_token=lp_tok)
        self._save_sftp_env(silent=True)
        cred_rel = out_dir / "custom" / "cms_credentials.json"
        if not cred_rel.is_file():
            self._log(
                "警告: custom/cms_credentials.json がありません。LP を再生成するか CMS 用資格情報を配置してください。",
                WARN_MSG,
            )
        self._log(
            f"SFTPアップロード開始: {remote_release_dir}（site_key={site_key}, lp_token={lp_tok or '—'}）"
        )
        try:
            cli = paramiko.SSHClient()
            cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            cli.connect(hostname=host, port=port, username=user, password=pwd, timeout=10)
            sftp = cli.open_sftp()
            self._sftp_upload_dir(sftp, out_dir, remote_release_dir)
            sftp.put(str(pdf_path), posixpath.join(remote_release_dir, pdf_path.name))
            sftp.close()
            cli.close()
            public_url = f"{route}/{site_key}/index.html" if route else f"/{site_key}/index.html"
            self.sftp_link_var.set(public_url)
            self._set_last_site_key(site_key)
            self._apply_cms_login_from_lp_meta(str(out_dir))
            self._log(f"SFTPアップロード完了: {public_url}", GREEN_OK)
            messagebox.showinfo("アップロード完了", f"アップロードが完了しました。\n\n{public_url}")
            try:
                self.nb.select(self.tab_sftp)
            except tk.TclError:
                pass
        except Exception as e:
            self._log(f"SFTPアップロード失敗: {e}", RED_ERR)
            messagebox.showerror("アップロード失敗", f"SFTPアップロードに失敗しました。\n\n{e}")

    def _load_config(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _apply_style(self):
        style = ttk.Style()
        style.configure("TScrollbar", background=BG_PANEL, troughcolor=BG_DARK,
                        arrowcolor=FG_SUB, borderwidth=0)

        # Combobox（readonly）：Windows などで field が明色・文字が薄くなる対策
        _cbf, _cfg = BG_PANEL, FG_MAIN
        style.configure(
            "TCombobox",
            fieldbackground=_cbf,
            background=_cbf,
            foreground=_cfg,
            arrowcolor=GOLD,
            borderwidth=1,
            selectbackground=GOLD,
            selectforeground=BG_DARK,
            padding=(6, 4),
        )
        style.map(
            "TCombobox",
            fieldbackground=[
                ("readonly", _cbf),
                ("disabled", BG_PANEL),
                ("focus", _cbf),
                ("active", _cbf),
            ],
            foreground=[
                ("readonly", _cfg),
                ("disabled", FG_SUB),
                ("focus", _cfg),
                ("active", _cfg),
            ],
            background=[
                ("readonly", _cbf),
                ("focus", _cbf),
                ("active", _cbf),
            ],
            arrowcolor=[
                ("readonly", GOLD),
                ("disabled", FG_SUB),
            ],
        )
        # ドロップダウン一覧（環境によっては別要素）
        for lb in ("ComboboxPopdown.Listbox", "Combobox.dropdown"):
            try:
                style.configure(
                    lb,
                    background=BG_PANEL,
                    foreground=FG_MAIN,
                    selectbackground=GOLD,
                    selectforeground=BG_DARK,
                    fieldbackground=BG_PANEL,
                )
            except tk.TclError:
                pass


# ─────────────────────────────────────────────
# エントリーポイント
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = LPBuilderApp()
    app.mainloop()
