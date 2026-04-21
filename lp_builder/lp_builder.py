"""
LP Builder — ランディングページ自動生成ツール
Python 3.x + tkinter（追加インストール不要）
"""

import functools
import http.server
import json
import os
import socketserver
import sys
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
from datetime import datetime
from pathlib import Path

# パスを通す（同ディレクトリのモジュールを読む）
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prompt_template import (
    INDUSTRY_KEYS,
    COLOR_PRESETS,
    build_input_sheet_md,
    LP_TEMPLATE_OPTIONS,
    LP_TEMPLATE_LABEL_TO_KEY,
    LP_TEMPLATE_STYLE_FILES,
    normalize_lp_template_key,
)
from api_client import generate_lp

# ─────────────────────────────────────────────
# 定数
# ─────────────────────────────────────────────
APP_TITLE   = "LP Builder  —  ランディングページ自動生成"
APP_VERSION = "1.0.0"
CONFIG_FILE = Path.home() / ".lp_builder_config.json"

BG_DARK   = "#1a1a1a"
BG_PANEL  = "#242424"
BG_INPUT  = "#2e2e2e"
FG_MAIN   = "#f0f0f0"
FG_SUB    = "#aaaaaa"
GOLD      = "#c9a96e"
GOLD_DARK = "#a07840"
RED_ERR   = "#e05555"
GREEN_OK  = "#55c055"

FONT_H1   = ("Segoe UI", 16, "bold")
FONT_H2   = ("Segoe UI", 12, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_MONO = ("Consolas", 9)

# 共有ファイル（アプリと同じフォルダに同梱）
SHARED_FILES = ["script.js", "pexels.js"]
APP_DIR = Path(os.path.dirname(os.path.abspath(__file__)))

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


def safe_site_dir_segment(sheet: dict) -> str:
    """出力サブフォルダ名用。プレースホルダ除去・Windows禁止文字除去。"""
    raw = (sheet.get("name_en") or sheet.get("name_ja") or "lp_site").strip()
    raw = _strip_example_prefix(raw)
    if not raw:
        raw = "lp_site"
    for c in '<>:"/\\|?*':
        raw = raw.replace(c, "_")
    return raw.replace(" ", "_").lower()[:120]


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
        self.geometry("900x860")
        self.minsize(800, 760)
        self.configure(bg=BG_DARK)

        # 設定読み込み
        self.config_data = self._load_config()

        # ウィジェット変数
        self.api_key_var = tk.StringVar(value=self.config_data.get("api_key", ""))
        _cfg_out = self.config_data.get("output_dir", "")
        _init_out = (
            str(normalize_output_dir(str(_cfg_out)))
            if str(_cfg_out).strip()
            else str((Path.home() / "LP_Projects").resolve())
        )
        self.output_dir = tk.StringVar(value=_init_out)
        self.industry_var  = tk.StringVar(value=list(INDUSTRY_KEYS.keys())[0])
        self.color_var     = tk.StringVar(value=list(COLOR_PRESETS.keys())[0])
        _cfg_tpl = normalize_lp_template_key(self.config_data.get("lp_template", "classic"))
        _tpl_label = next(
            (lab for lab, k in LP_TEMPLATE_OPTIONS if k == _cfg_tpl),
            LP_TEMPLATE_OPTIONS[0][0],
        )
        self.lp_template_var = tk.StringVar(value=_tpl_label)
        self.is_generating = False
        self._session_input_tokens = 0
        self._session_output_tokens = 0
        self._last_in = 0
        self._last_out = 0

        cd = self.config_data

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

        self._build_ui()
        self._apply_style()
        self._bind_pricing_refresh()
        self._refresh_usage_display()

        self._preview_httpd: http.server.HTTPServer | None = None
        self.protocol("WM_DELETE_WINDOW", self._on_close)

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
        self.nb.pack(fill="both", expand=True, padx=16, pady=(0, 8))

        self.tab_basic    = self._make_tab("① 基本情報")
        self.tab_services = self._make_tab("② サービス")
        self.tab_reasons  = self._make_tab("③ 推しポイント")
        self.tab_settings = self._make_tab("⚙ 設定")
        self.tab_log      = self._make_tab("④ ログ")

        self._build_tab_basic()
        self._build_tab_services()
        self._build_tab_reasons()
        self._build_tab_settings()
        self._build_tab_log()

        # 下部：生成ボタン＋トークン概要
        self._build_bottom()

    def _make_tab(self, label):
        frame = tk.Frame(self.nb, bg=BG_INPUT)
        self.nb.add(frame, text=label)
        return frame

    # ─── タブ①：基本情報 ─────────────────────
    def _build_tab_basic(self):
        f = self.tab_basic
        canvas = tk.Canvas(f, bg=BG_INPUT, highlightthickness=0)
        sb = ttk.Scrollbar(f, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG_INPUT)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        canvas.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        p = 16
        self._section_label(inner, "業種・デザイン")
        row = tk.Frame(inner, bg=BG_INPUT)
        row.pack(fill="x", padx=p, pady=4)
        tk.Label(row, text="業種", width=14, anchor="w", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        cb = ttk.Combobox(row, textvariable=self.industry_var,
                          values=list(INDUSTRY_KEYS.keys()), state="readonly", width=28)
        cb.pack(side="left", padx=4)

        row2 = tk.Frame(inner, bg=BG_INPUT)
        row2.pack(fill="x", padx=p, pady=4)
        tk.Label(row2, text="カラー", width=14, anchor="w", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        cb2 = ttk.Combobox(row2, textvariable=self.color_var,
                           values=list(COLOR_PRESETS.keys()), state="readonly", width=36)
        cb2.pack(side="left", padx=4)

        row_tpl = tk.Frame(inner, bg=BG_INPUT)
        row_tpl.pack(fill="x", padx=p, pady=4)
        tk.Label(row_tpl, text="LPテンプレート", width=14, anchor="w", bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        cb_tpl = ttk.Combobox(
            row_tpl,
            textvariable=self.lp_template_var,
            values=[lab for lab, _ in LP_TEMPLATE_OPTIONS],
            state="readonly",
            width=36,
        )
        cb_tpl.pack(side="left", padx=4)

        self._section_label(inner, "店舗情報")
        fields = [
            ("name_ja",  "店舗名（日本語）", "例: PAWS MINATO"),
            ("name_en",  "店舗名（英語）",   "例: PAWS MINATO"),
            ("catch",    "キャッチコピー",   "例: 愛犬に、最高の一日を。"),
            ("sub_copy", "サブコピー",       "例: 港区の小型犬専門プレミアムサロン"),
            ("address",  "住所",             "例: 東京都港区麻布十番2-1-1"),
            ("tel",      "電話番号",         "例: 03-1234-5678"),
            ("hours",    "営業時間",         "例: 10:00〜19:00"),
            ("holiday",  "定休日",           "例: 火曜日"),
            ("station",  "最寄り駅",         "例: 麻布十番駅 徒歩2分"),
            ("url",      "WebサイトURL",     "例: https://example.com"),
        ]
        self.basic_vars = {}
        for key, label, placeholder in fields:
            self.basic_vars[key] = self._entry_row(inner, label, placeholder, p)

    # ─── タブ②：サービス ─────────────────────
    def _build_tab_services(self):
        f = self.tab_services
        self._section_label(f, "サービス内容（3〜6項目）")
        tk.Label(f, text="タイトルと説明を入力してください。空欄は自動補完されます。",
                 bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(padx=16, anchor="w")

        self.service_vars = []
        for i in range(6):
            grp = tk.LabelFrame(f, text=f"サービス {i+1}",
                                bg=BG_INPUT, fg=GOLD, font=FONT_BODY,
                                bd=1, relief="groove")
            grp.pack(fill="x", padx=16, pady=4)
            t_var = tk.StringVar()
            d_var = tk.StringVar()
            row1 = tk.Frame(grp, bg=BG_INPUT)
            row1.pack(fill="x", padx=8, pady=2)
            tk.Label(row1, text="タイトル", width=8, anchor="w",
                     bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
            tk.Entry(row1, textvariable=t_var, bg=BG_PANEL, fg=FG_MAIN,
                     insertbackground=FG_MAIN, relief="flat", font=FONT_BODY).pack(side="left", fill="x", expand=True, padx=4)
            row2 = tk.Frame(grp, bg=BG_INPUT)
            row2.pack(fill="x", padx=8, pady=2)
            tk.Label(row2, text="説明", width=8, anchor="w",
                     bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
            tk.Entry(row2, textvariable=d_var, bg=BG_PANEL, fg=FG_MAIN,
                     insertbackground=FG_MAIN, relief="flat", font=FONT_BODY).pack(side="left", fill="x", expand=True, padx=4)
            self.service_vars.append({"title": t_var, "desc": d_var})

    # ─── タブ③：推しポイント ──────────────────
    def _build_tab_reasons(self):
        f = self.tab_reasons
        self._section_label(f, "推しポイント / 選ばれる理由（最大3つ）")
        tk.Label(f, text="空欄は業種に合わせて自動補完されます。",
                 bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(padx=16, anchor="w")

        self.reason_vars = []
        for i in range(3):
            grp = tk.LabelFrame(f, text=f"REASON {i+1:02d}",
                                bg=BG_INPUT, fg=GOLD, font=FONT_BODY,
                                bd=1, relief="groove")
            grp.pack(fill="x", padx=16, pady=6)
            t_var = tk.StringVar()
            d_var = tk.StringVar()
            f1_var, f2_var, f3_var = tk.StringVar(), tk.StringVar(), tk.StringVar()

            for label, var, ph in [
                ("タイトル", t_var, "例: 完全個室でストレスゼロ"),
                ("説明文",   d_var, "例: 他の犬と接触なし、リアルタイム動画配信"),
            ]:
                row = tk.Frame(grp, bg=BG_INPUT)
                row.pack(fill="x", padx=8, pady=2)
                tk.Label(row, text=label, width=8, anchor="w",
                         bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
                e = tk.Entry(row, textvariable=var, bg=BG_PANEL, fg=FG_MAIN,
                             insertbackground=FG_MAIN, relief="flat", font=FONT_BODY)
                e.pack(side="left", fill="x", expand=True, padx=4)
                e.insert(0, ph)
                e.config(fg=FG_SUB)
                e.bind("<FocusIn>",  lambda ev, v=var, p=ph: self._clear_placeholder(ev, v, p))
                e.bind("<FocusOut>", lambda ev, v=var, p=ph: self._set_placeholder(ev, v, p))

            feat_row = tk.Frame(grp, bg=BG_INPUT)
            feat_row.pack(fill="x", padx=8, pady=2)
            tk.Label(feat_row, text="特徴3つ", width=8, anchor="w",
                     bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
            for fv in [f1_var, f2_var, f3_var]:
                tk.Entry(feat_row, textvariable=fv, bg=BG_PANEL, fg=FG_MAIN,
                         insertbackground=FG_MAIN, relief="flat", font=FONT_BODY,
                         width=18).pack(side="left", padx=2)

            self.reason_vars.append({
                "title": t_var, "desc": d_var,
                "features": [f1_var, f2_var, f3_var]
            })

    # ─── タブ④：設定 ─────────────────────────
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

    # ─── タブ⑤：ログ ─────────────────────────
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
        bottom = tk.Frame(self, bg=BG_DARK)
        bottom.pack(fill="x", padx=16, pady=(0, 12))

        btn_frame = tk.Frame(bottom, bg=BG_DARK)
        btn_frame.pack(fill="x", pady=4)

        self.gen_btn = tk.Button(
            btn_frame,
            text="  ▶  LP を生成する  ",
            command=self._start_generate,
            bg=GOLD, fg=BG_DARK,
            relief="flat", font=("Segoe UI", 13, "bold"),
            cursor="hand2", padx=16, pady=10,
        )
        self.gen_btn.pack(side="left")

        self.save_sheet_btn = tk.Button(
            btn_frame,
            text="  INPUT_SHEET.md を保存  ",
            command=self._save_input_sheet,
            bg=BG_PANEL, fg=GOLD,
            relief="flat", font=FONT_BODY,
            cursor="hand2", padx=12, pady=10,
        )
        self.save_sheet_btn.pack(side="left", padx=8)

        self.status_label = tk.Label(
            btn_frame, text="待機中", bg=BG_DARK, fg=FG_SUB, font=FONT_BODY
        )
        self.status_label.pack(side="right", padx=8)

        usage_frame = tk.Frame(bottom, bg=BG_DARK)
        usage_frame.pack(fill="x", pady=(8, 0))
        tk.Label(
            usage_frame,
            text="APIトークン・概算コスト",
            bg=BG_DARK,
            fg=GOLD,
            font=("Segoe UI", 9, "bold"),
        ).pack(anchor="w")
        self.usage_label = tk.Label(
            usage_frame,
            text="",
            bg=BG_DARK,
            fg=FG_SUB,
            font=FONT_MONO,
            justify="left",
            anchor="w",
        )
        self.usage_label.pack(fill="x", pady=(2, 0))

    # ─── ヘルパー ─────────────────────────────
    def _section_label(self, parent, text):
        tk.Label(parent, text=text, bg=BG_INPUT, fg=GOLD,
                 font=FONT_H2, pady=8).pack(anchor="w", padx=16)

    def _entry_row(self, parent, label, placeholder, padx):
        row = tk.Frame(parent, bg=BG_INPUT)
        row.pack(fill="x", padx=padx, pady=3)
        tk.Label(row, text=label, width=16, anchor="w",
                 bg=BG_INPUT, fg=FG_SUB, font=FONT_BODY).pack(side="left")
        var = tk.StringVar()
        e = tk.Entry(row, textvariable=var, bg=BG_PANEL, fg=FG_SUB,
                     insertbackground=FG_MAIN, relief="flat", font=FONT_BODY)
        e.pack(side="left", fill="x", expand=True, padx=4)
        e.insert(0, placeholder)
        e.bind("<FocusIn>",  lambda ev, v=var, p=placeholder: self._clear_placeholder(ev, v, p))
        e.bind("<FocusOut>", lambda ev, v=var, p=placeholder: self._set_placeholder(ev, v, p))
        return var

    def _clear_placeholder(self, event, var, placeholder):
        if event.widget.get() == placeholder:
            event.widget.delete(0, "end")
            event.widget.config(fg=FG_MAIN)

    def _set_placeholder(self, event, var, placeholder):
        if not event.widget.get():
            event.widget.insert(0, placeholder)
            event.widget.config(fg=FG_SUB)

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

        for v in (self.price_in_var, self.price_out_var, self.jpy_per_usd_var):
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

    def _apply_usage_stats(self, result: dict) -> None:
        """generate_lp の戻り値からトークン表示を更新（メインスレッド専用）"""
        tin = int(result.get("input_tokens") or 0)
        tout = int(result.get("output_tokens") or 0)
        if tin or tout:
            self._session_input_tokens += tin
            self._session_output_tokens += tout
            self._last_in = tin
            self._last_out = tout
        self._refresh_usage_display()

    def _log(self, msg, color=None):
        self.log_box.config(state="normal")
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_box.insert("end", f"[{ts}] {msg}\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")
        self.status_label.config(text=msg[:60])
        self.update_idletasks()

    def _collect_sheet(self) -> dict:
        """GUIの入力値を辞書にまとめる"""
        color_name = self.color_var.get()
        color = COLOR_PRESETS.get(color_name, list(COLOR_PRESETS.values())[0])

        # プレースホルダーを除外
        def clean(var, placeholder=""):
            v = var.get().strip()
            return "" if v == placeholder else v

        services = []
        for sv in self.service_vars:
            t = sv["title"].get().strip()
            d = sv["desc"].get().strip()
            if t:
                services.append({"title": t, "desc": d})

        reasons = []
        for rv in self.reason_vars:
            t = rv["title"].get().strip()
            d = rv["desc"].get().strip()
            feats = [fv.get().strip() for fv in rv["features"] if fv.get().strip()]
            if t:
                reasons.append({"title": t, "desc": d, "features": feats})

        return {
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "industry":   self.industry_var.get(),
            "name_ja":    self.basic_vars["name_ja"].get(),
            "name_en":    self.basic_vars["name_en"].get(),
            "catch":      self.basic_vars["catch"].get(),
            "sub_copy":   self.basic_vars["sub_copy"].get(),
            "address":    self.basic_vars["address"].get(),
            "tel":        self.basic_vars["tel"].get(),
            "hours":      self.basic_vars["hours"].get(),
            "holiday":    self.basic_vars["holiday"].get(),
            "station":    self.basic_vars["station"].get(),
            "url":        self.basic_vars["url"].get(),
            "services":   services,
            "reasons":    reasons,
            "color":      color,
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
            self.nb.select(3)
            return

        name = self.basic_vars["name_en"].get().strip() or self.basic_vars["name_ja"].get().strip()
        if not name:
            messagebox.showerror("エラー", "① 基本情報タブで店舗名を入力してください。")
            self.nb.select(0)
            return

        self.is_generating = True
        self.gen_btn.config(state="disabled", text="  生成中...  ", bg=BG_PANEL, fg=FG_SUB)
        sheet = self._collect_sheet()
        threading.Thread(target=self._generate_thread, args=(sheet, api_key), daemon=True).start()

    def _generate_thread(self, sheet: dict, api_key: str):
        self._log("LP生成を開始します...")

        # 出力ディレクトリ作成（出力先に「例:」が混入していても正規化）
        site_name = safe_site_dir_segment(sheet)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        try:
            root = normalize_output_dir(self.output_dir.get())
            root.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self._log(f"出力先フォルダを作成できません: {e}", RED_ERR)
            self.after(0, self._on_generate_done, False, "")
            return
        out_dir = root / f"{site_name}_{ts}"
        try:
            out_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self._log(f"出力フォルダを作成できません: {e}", RED_ERR)
            self.after(0, self._on_generate_done, False, str(root))
            return
        self._log(f"出力先: {out_dir}")

        # INPUT_SHEET.md 保存
        md_path = out_dir / "INPUT_SHEET.md"
        md_path.write_text(build_input_sheet_md(sheet), encoding="utf-8")
        self._log("INPUT_SHEET.md を保存しました")

        # Claude API 呼び出し
        result = generate_lp(sheet, api_key, on_progress=self._log)
        self.after(0, lambda r=result: self._apply_usage_stats(r))

        if result["error"]:
            self._log(f"エラー: {result['error']}", RED_ERR)
            self.after(0, self._on_generate_done, False, str(out_dir))
            return

        # index.html 保存
        html_path = out_dir / "index.html"
        html_path.write_text(result["html"], encoding="utf-8")
        self._log(f"index.html を保存しました（{len(result['html']):,} 文字）")

        # 共有ファイルをコピー（選択テーマの style.css を style.css 名で配置）
        self._copy_shared_files(out_dir, sheet)

        self._log("完了！localhost でプレビューを開きます...")
        self.after(0, self._on_generate_done, True, str(out_dir))

    def _copy_shared_files(self, out_dir: Path, sheet: dict):
        """選択テーマの CSS を style.css としてコピーし、script.js / pexels.js を同梱"""
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
            return url
        except Exception as e:
            self._log(f"ローカルサーバー起動に失敗: {e} — file:// で開きます", RED_ERR)
            fu = index_path.as_uri()
            webbrowser.open(fu)
            return fu

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
        self.gen_btn.config(state="normal", text="  ▶  LP を生成する  ", bg=GOLD, fg=BG_DARK)
        if success:
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
                "LP生成中にエラーが発生しました。\n\n「④ ログ」タブに詳細を表示しました。",
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
            "lp_template": normalize_lp_template_key(
                LP_TEMPLATE_LABEL_TO_KEY.get(self.lp_template_var.get())
            ),
        }
        CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        self._log("設定を保存しました")
        self._refresh_usage_display()
        messagebox.showinfo("保存完了", "設定を保存しました。")

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
        style.configure("TCombobox", fieldbackground=BG_PANEL, background=BG_PANEL,
                        foreground=FG_MAIN, selectbackground=GOLD, selectforeground=BG_DARK)


# ─────────────────────────────────────────────
# エントリーポイント
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = LPBuilderApp()
    app.mainloop()
