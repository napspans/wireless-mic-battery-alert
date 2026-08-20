import logging
import os
import threading
import time
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.ttk as ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import i18n
from i18n import t
from monitor import DB_FLOOR, AudioMonitor, list_input_devices
import settings
import theme
import version
from theme import apply_theme, get_colors, get_system_theme

logger = logging.getLogger(__name__)

_PAD_OUTER = 16
_PAD_INNER = 8
_PAD_ROW = (6, 6)
# 補足文の折り返し幅。設定値の列に収まる範囲。翻訳の長さは言語によって
# 倍ほど違うため、日本語で1行に収まる文もフランス語・韓国語では溢れる。
_HINT_WRAP = 320

# 通知音は「安定キー」で持つ。表示は t() を通してその場で作る。以前は
# Combobox の値が日本語文字列そのもので、それが dict のキーも兼ねていた
# ため、言語を変えると設定の読み書きが成立しなくなる構造だった。
_CUSTOM_SOUND_KEY = "custom"
_ALERT_SOUND_KEYS = [
    "builtin:chime",
    "builtin:error",
    "builtin:marimba",
    _CUSTOM_SOUND_KEY,
]
_STATUS_SOUND_KEYS = [
    "builtin:notify_04",
    "builtin:notify_11",
    "builtin:chime",
    "builtin:error",
    "builtin:marimba",
    _CUSTOM_SOUND_KEY,
]

_THEME_KEYS = ["system", "light", "dark"]


def _sound_label(key: str) -> str:
    return t(f"sound.{key}")


class _KeyedCombo:
    """表示は翻訳し、値は安定キーで保持する Combobox。

    Combobox は表示文字列しか持てないため、そのままでは表示と値が癒着する。
    キーを別の変数に持ち、選択時に表示→キー、言語切替時にキー→表示へ
    翻訳し直すことで、表示言語と設定値を切り離す。
    """

    def __init__(self, parent, keys, label_for, key_var, width=20):
        self._keys = list(keys)
        self._label_for = label_for
        self.key_var = key_var
        self._display_var = tk.StringVar()
        self.widget = ttk.Combobox(
            parent,
            textvariable=self._display_var,
            state="readonly",
            width=width,
        )
        self.widget.bind("<<ComboboxSelected>>", self._on_selected)
        # キーは生成後に入ることが多い（設定の読み込みが後段にある）。表示を
        # 追随させておかないと、値は入っているのに欄が空のままになる。
        self.key_var.trace_add("write", lambda *_: self.sync_display())
        self.retranslate()

    @property
    def keys(self) -> list:
        return list(self._keys)

    def set_keys(self, keys) -> None:
        self._keys = list(keys)
        self.retranslate()

    def _on_selected(self, event=None) -> None:
        display = self._display_var.get()
        for key in self._keys:
            if self._label_for(key) == display:
                self.key_var.set(key)
                return

    def retranslate(self) -> None:
        """表示だけを訳し直す。キーには触れない。"""
        self.widget.configure(values=[self._label_for(k) for k in self._keys])
        self.sync_display()

    def sync_display(self) -> None:
        key = self.key_var.get()
        if key in self._keys:
            self._display_var.set(self._label_for(key))

    def config(self, **kwargs) -> None:
        self.widget.config(**kwargs)


class _SoundSection:
    """1つの通知音設定（選択肢・カスタムパス・有効チェック）をまとめて持つ。

    通知音の設定は4系統あり、構造はどれも同じ。個別に書き下すと gui.py の
    1/4 を占めるうえ、i18n 化で同じ修正を4回することになる。
    """

    def __init__(self, config_key, enabled_key, keys, default_path,
                 browse_title_key):
        self.config_key = config_key
        self.enabled_key = enabled_key
        self.keys = keys
        self.default_path = default_path
        self.browse_title_key = browse_title_key
        self.key_var: tk.StringVar = None
        self.path_var: tk.StringVar = None
        self.enabled_var: tk.BooleanVar = None
        self.combo: _KeyedCombo = None
        self.custom_frame: tk.Frame = None
        self.test_btn: ttk.Button = None
        self.entry: ttk.Entry = None
        self.browse_btn: ttk.Button = None


class SettingsGUI:
    _SAVE_DEBOUNCE_MS = 500

    def __init__(
        self,
        monitor: AudioMonitor,
        config: dict,
        on_config_save: callable,
        on_toggle_monitor=None,
        is_suspended=None,
    ):
        self._monitor = monitor
        self._config = config
        self._on_config_save = on_config_save
        self._on_toggle_monitor = on_toggle_monitor
        self._is_suspended = is_suspended
        self._running = True
        self._zoom_mode = False
        self._dirty = False
        self._suspend_dirty = True  # UI構築中と保存中は変更として扱わない
        self._save_after_id = None
        self._cards: list[tk.Frame] = []
        self._card_inners: list[tk.Frame] = []
        self._bg_frames: list[tk.Frame] = []
        self._headline_labels: list[tk.Label] = []
        self._body_labels: list[tk.Label] = []
        self._checkbuttons: list[ttk.Checkbutton] = []
        self._scroll_canvases: list[tk.Canvas] = []
        self._comboboxes: list[ttk.Combobox] = []
        # 言語が変わったときに表示を訳し直す処理。ウィジェット生成時に登録する。
        self._retranslate_hooks: list = []

        self._root = tk.Tk()

        # フォントと option DB はウィジェット生成より前に用意する必要がある。
        # 名前付きフォントが未定義のまま生成されると Tk の既定フォントに落ち、
        # あとから定義しても遡って適用されない。Combobox のポップダウンも
        # 同様に、生成時の option DB しか見ない。
        language = self._config.get("language") or i18n.get_language()
        i18n.set_language(language)
        self._configured_theme = self._config.get("theme", "system")
        theme.init_fonts(self._root, i18n.get_language())
        theme.init_options(self._root, self._configured_theme)

        self._root.title(i18n.settings_window_title())
        self._register(lambda: self._root.title(i18n.settings_window_title()))
        self._apply_window_icon()
        self._root.geometry("640x720")
        self._root.resizable(False, False)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._devices = list_input_devices()

        self._build_waveform_area()
        self._build_settings_form()
        self._build_button_area()
        self._root.bind_all("<MouseWheel>", self._on_mousewheel)

        apply_theme(self._root, self._configured_theme, i18n.get_language())
        resolved_theme = self._resolve_theme()
        self._apply_visual_theme(resolved_theme)
        self._apply_graph_theme(resolved_theme)

        if self._monitoring_active():
            self._monitor_btn_var.set(t("button.monitor_stop"))

        self._watch_variables()
        self._suspend_dirty = False

        self._root.after(500, self._update_waveform)

    # -------------------------------------------------------------------------
    # 翻訳の登録と適用
    # -------------------------------------------------------------------------

    def _register(self, hook) -> None:
        """言語切替時に呼び直す処理を登録する。"""
        self._retranslate_hooks.append(hook)

    def _retranslate(self) -> None:
        """再起動せずに表示を訳し直す。

        言語だけを変えたのに設定が保存され直すのは筋が悪いので、訳し直しの
        間は変更検知を止める（Combobox の表示変更が dirty 扱いになるため）。
        """
        previous = self._suspend_dirty
        self._suspend_dirty = True
        try:
            theme.init_fonts(self._root, i18n.get_language())
            theme.init_options(self._root, self._configured_theme)
            for hook in self._retranslate_hooks:
                try:
                    hook()
                except Exception:
                    logger.exception("表示の再翻訳に失敗しました")
            resolved_theme = self._resolve_theme()
            for combobox in self._comboboxes:
                theme.style_popdown(combobox, resolved_theme)
            self._update_zoom_button()
            self._update_status()
            self._save_status_label.config(text="")
        finally:
            self._suspend_dirty = previous

    def _watch_variables(self) -> None:
        """設定に対応する全ての入力を監視する。

        個々のウィジェットに <FocusOut> を張る方式では、入力欄に文字を打った直後や
        スピンボックスの矢印を押しただけでは変更が拾えず、他所をクリックするまで
        保存対象にならなかった。変数そのものを監視して取りこぼしをなくす。
        """
        self._tracked_vars = [
            self._device_var,
            self._interval_var,
            self._volume_var,
            self._auto_pause_enabled_var,
            self._auto_pause_alert_count_var,
            self._idle_suspend_enabled_var,
            self._idle_suspend_sec_var,
            self._mic_share_monitor_enabled_var,
            self._theme_var,
            self._language_var,
        ]
        for section in self._sound_sections:
            self._tracked_vars.append(section.key_var)
            self._tracked_vars.append(section.path_var)
            if section.enabled_var is not None:
                self._tracked_vars.append(section.enabled_var)
        for var in self._tracked_vars:
            var.trace_add("write", lambda *_: self._mark_dirty())

    def _monitoring_active(self) -> bool:
        """ユーザーから見て監視中か。

        無操作による自動停止中はストリームが閉じているため is_running は False に
        なるが、監視する意図は残っている。ボタン表示はこちらを基準にする。
        """
        if self._monitor.is_running:
            return True
        return bool(self._is_suspended and self._is_suspended())

    def _mark_dirty(self, event=None) -> None:
        """変更を受けて自動保存を予約する。

        変数監視は1文字打つたびに発火するため、そのまま保存すると config.json への
        書き込みとデバイス再起動が連打される。入力が止まってから一度だけ保存する。
        """
        if self._suspend_dirty or not self._running:
            return
        self._dirty = True
        colors = get_colors(self._resolve_theme())
        self._save_status_label.config(
            text=t("save.saving"), foreground=colors["secondary_label"]
        )
        if self._save_after_id is not None:
            self._root.after_cancel(self._save_after_id)
        self._save_after_id = self._root.after(self._SAVE_DEBOUNCE_MS, self._on_save)

    # -------------------------------------------------------------------------
    # UI構築
    # -------------------------------------------------------------------------

    def _apply_window_icon(self) -> None:
        """タイトルバーとタスクバーのアイコンを差し替える。

        指定しないと Tk 既定の羽根アイコンのままになる。`.ico` には複数の
        サイズが入っており、Windows が表示場所ごとに適したものを選ぶ。
        """
        path = os.path.join(settings.get_resource_dir(), "assets", "app.ico")
        if not os.path.exists(path):
            logger.warning("アプリアイコンが見つかりません: %s", path)
            return
        try:
            self._root.iconbitmap(default=path)
        except tk.TclError:
            logger.warning("アプリアイコンを適用できませんでした: %s", path,
                           exc_info=True)

    def _resolve_theme(self) -> str:
        theme_name = self._config.get("theme", "system")
        return theme_name if theme_name != "system" else get_system_theme()

    def _add_card(self, parent, colors: dict) -> tk.Frame:
        card_outer = tk.Frame(parent, background=colors["bg"], highlightthickness=0)
        card_outer.pack(fill=tk.BOTH, expand=True, padx=_PAD_INNER, pady=_PAD_INNER)
        # 地の色は sv_ttk と同値でなければスプライトの縁が浮く。カードの
        # 区切りは塗り分けではなくボーダーで付ける（theme.py の説明を参照）。
        card = tk.Frame(
            card_outer,
            background=colors["surface"],
            highlightthickness=1,
            highlightbackground=colors["border"],
            highlightcolor=colors["border"],
        )
        card.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        card_inner = tk.Frame(card, background=colors["surface"], highlightthickness=0, padx=12, pady=12)
        card_inner.pack(fill=tk.BOTH, expand=True)
        self._bg_frames.append(card_outer)
        self._cards.append(card)
        self._card_inners.append(card_inner)
        return card_inner

    def _make_body_label(self, parent, key: str, colors: dict, wrap: int = 0,
                         **grid_kwargs):
        """設定項目のラベルを作る。

        `wrap` を渡すとその幅で折り返す。翻訳の長さは言語によって倍ほど違い、
        日本語で収まる補足文がフランス語・韓国語では枠から溢れて左右が
        切れてしまうため、補足文には折り返しを指定する。
        """
        label = tk.Label(
            parent,
            text=t(key),
            font=theme.FONTS["body"],
            foreground=colors["label"],
            background=colors["surface"],
            wraplength=wrap,
            justify=tk.LEFT,
        )
        label.grid(**grid_kwargs)
        self._body_labels.append(label)
        self._register(lambda: label.config(text=t(key)))
        return label

    def _make_value_label(self, parent, text: str, colors: dict, **grid_kwargs):
        """訳す必要のない値（バージョン番号など）を出す。"""
        label = tk.Label(
            parent,
            text=text,
            font=theme.FONTS["body"],
            foreground=colors["label"],
            background=colors["surface"],
        )
        label.grid(**grid_kwargs)
        self._body_labels.append(label)
        return label

    def _make_headline_label(self, parent, key: str, colors: dict, **grid_kwargs):
        label = tk.Label(
            parent,
            text=t(key),
            font=theme.FONTS["headline"],
            foreground=colors["label"],
            background=colors["surface"],
        )
        label.grid(**grid_kwargs)
        self._headline_labels.append(label)
        self._register(lambda: label.config(text=t(key)))
        return label

    def _make_button(self, parent, key: str, command, **kwargs):
        button = ttk.Button(parent, text=t(key), command=command, **kwargs)
        self._register(lambda: button.config(text=t(key)))
        return button

    def _make_frame(self, parent, colors: dict) -> tk.Frame:
        frame = tk.Frame(parent, background=colors["surface"], highlightthickness=0)
        self._card_inners.append(frame)
        return frame

    def _apply_visual_theme(self, resolved_theme: str) -> None:
        colors = get_colors(resolved_theme)
        self._root.configure(background=colors["bg"])
        for frame in self._bg_frames:
            frame.configure(background=colors["bg"])
        for card in self._cards:
            card.configure(
                background=colors["surface"],
                highlightbackground=colors["border"],
                highlightcolor=colors["border"],
            )
        for inner in self._card_inners:
            inner.configure(background=colors["surface"])
        for label in self._headline_labels:
            label.configure(foreground=colors["label"], background=colors["surface"])
        for label in self._body_labels:
            label.configure(foreground=colors["label"], background=colors["surface"])

        for canvas in self._scroll_canvases:
            canvas.configure(background=colors["bg"])
        # ポップダウンは option DB を生成時にしか読まないため、切替後は実体を直接叩く。
        for combobox in self._comboboxes:
            theme.style_popdown(combobox, resolved_theme)
        if hasattr(self, "_save_status_label"):
            self._save_status_label.configure(background=colors["bg"], foreground=colors["secondary_label"])
        if hasattr(self, "_version_label"):
            self._version_label.configure(background=colors["bg"], foreground=colors["secondary_label"])

    def _make_scrollable_tab(self, notebook, key: str, colors: dict) -> tk.Frame:
        """スクロールできるタブを追加し、中身を載せる枠を返す。

        ウィンドウはサイズ固定のため、設定項目が増えるとタブ内に収まらなくなる。
        """
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=t(key))
        self._register(lambda: notebook.tab(frame, text=t(key)))

        canvas = tk.Canvas(
            frame,
            highlightthickness=0,
            background=colors["bg"],
            yscrollincrement=20,
        )
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, background=colors["bg"], highlightthickness=0)

        window = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda e: canvas.itemconfigure(window, width=e.width),
        )
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._scroll_canvases.append(canvas)
        return inner

    def _on_mousewheel(self, event) -> None:
        """ポインタが乗っているタブをスクロールする。

        タブごとに bind_all すると後から張った側が全体を奪う。ホイールは
        1箇所で受け、イベントの発生元から辿って対象のタブを決める。
        """
        widget = event.widget
        while widget is not None:
            if widget in self._scroll_canvases:
                widget.yview_scroll(int(-event.delta / 120), "units")
                return
            widget = getattr(widget, "master", None)

    def _make_checkbutton(self, parent, key: str, variable, command) -> ttk.Checkbutton:
        checkbutton = ttk.Checkbutton(
            parent,
            text=t(key),
            variable=variable,
            command=command,
        )
        self._checkbuttons.append(checkbutton)
        self._register(lambda: checkbutton.config(text=t(key)))
        return checkbutton

    def _make_combo(self, parent, keys, label_for, key_var, width=20) -> _KeyedCombo:
        combo = _KeyedCombo(parent, keys, label_for, key_var, width=width)
        self._comboboxes.append(combo.widget)
        self._register(combo.retranslate)
        return combo

    def _build_waveform_area(self):
        colors = get_colors(self._resolve_theme())
        self._fig = Figure(figsize=(5.8, 2.2), tight_layout=True)
        self._ax = self._fig.add_subplot(111)
        self._ax.set_ylim(DB_FLOOR, 0)
        self._ax.set_ylabel("dB", fontsize=8)
        self._ax.set_xticks([])
        self._line, = self._ax.plot([], [], lw=0.8)

        waveform_frame = tk.Frame(self._root, background=colors["bg"], highlightthickness=0)
        waveform_frame.pack(fill=tk.X, padx=_PAD_OUTER, pady=(_PAD_OUTER, 0))
        self._bg_frames.append(waveform_frame)

        self._zoom_btn_var = tk.StringVar(value=t("button.zoom_in"))
        self._zoom_btn = ttk.Button(waveform_frame, textvariable=self._zoom_btn_var, command=self._toggle_zoom)
        self._zoom_btn.pack(anchor='ne', padx=_PAD_INNER, pady=(0, 4))

        self._canvas = FigureCanvasTkAgg(self._fig, master=waveform_frame)
        self._canvas.get_tk_widget().pack(fill=tk.X)
        ttk.Separator(self._root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=_PAD_OUTER, pady=(4, 0))

        status_row = tk.Frame(self._root, background=colors["bg"], highlightthickness=0)
        status_row.pack(fill=tk.X, padx=_PAD_OUTER, pady=(2, 0))
        self._bg_frames.append(status_row)

        self._status_label = ttk.Label(status_row, text=t("status.stopped"), font=theme.FONTS["caption"], anchor=tk.W)
        self._status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._monitor_btn_var = tk.StringVar(value=t("button.monitor_start"))
        self._monitor_btn = ttk.Button(
            status_row,
            textvariable=self._monitor_btn_var,
            command=self._toggle_monitor,
            width=14,
            style="Accent.TButton",
        )
        self._monitor_btn.pack(side=tk.RIGHT)

    def _update_zoom_button(self) -> None:
        self._zoom_btn_var.set(t("button.zoom_out") if self._zoom_mode else t("button.zoom_in"))

    def _toggle_zoom(self):
        self._zoom_mode = not self._zoom_mode
        self._update_zoom_button()

    def _apply_graph_theme(self, theme_name: str) -> None:
        colors = get_colors(theme_name)
        bg = colors["surface"]
        fg = colors["label"]
        spine_color = colors["border"]

        self._fig.patch.set_facecolor(bg)
        self._ax.set_facecolor(bg)
        self._ax.tick_params(colors=fg, labelsize=7)
        self._ax.yaxis.label.set_color(fg)
        for spine in self._ax.spines.values():
            spine.set_color(spine_color)
        self._canvas.draw_idle()

    # -------------------------------------------------------------------------
    # デバイス一覧
    # -------------------------------------------------------------------------

    def _device_label(self, raw_name: str) -> str:
        """一覧に出すデバイス名。既定デバイスの注記は言語に合わせて付ける。"""
        matched = next((d for d in self._devices if d["raw_name"] == raw_name), None)
        if matched is None:
            return raw_name
        if matched.get("is_default"):
            return t("device.default_suffix", name=raw_name)
        return raw_name

    # -------------------------------------------------------------------------
    # 通知音セクション
    # -------------------------------------------------------------------------

    def _add_sound_section(self, parent, colors, section: _SoundSection, row: int,
                           section_key: str, label_key: str) -> int:
        """通知音1系統ぶんの UI を組み、次に使える行番号を返す。

        4系統とも構造は同じで、違うのは見出しと設定キー、選択肢だけ。
        """
        if section_key is not None:
            self._make_headline_label(
                parent, section_key, colors,
                row=row, column=0, columnspan=2, sticky=tk.W,
                pady=(_PAD_ROW[0], _PAD_INNER),
            )
            row += 1

        if section.enabled_key is not None:
            self._make_body_label(parent, label_key, colors,
                                  row=row, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
            section.enabled_var = tk.BooleanVar(
                value=self._config.get(section.enabled_key, True))
            check = self._make_checkbutton(
                parent, "check.enable", section.enabled_var,
                lambda s=section: self._on_sound_enabled_changed(s),
            )
            check.grid(row=row, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)
            row += 1
            file_label_key = "label.sound_file"
        else:
            file_label_key = label_key

        self._make_body_label(parent, file_label_key, colors,
                              row=row, column=0, sticky=tk.NW, padx=6, pady=_PAD_ROW)
        outer = self._make_frame(parent, colors)
        outer.grid(row=row, column=1, sticky=tk.EW, padx=6, pady=_PAD_ROW)

        select_frame = self._make_frame(outer, colors)
        select_frame.pack(fill=tk.X)

        section.key_var = tk.StringVar()
        section.path_var = tk.StringVar()
        section.combo = self._make_combo(
            select_frame, section.keys, _sound_label, section.key_var, width=20)
        section.combo.widget.pack(side=tk.LEFT)
        section.test_btn = self._make_button(
            select_frame, "button.test_play",
            lambda s=section: self._test_play(s))
        section.test_btn.pack(side=tk.LEFT, padx=(4, 0))

        section.custom_frame = self._make_frame(outer, colors)
        section.entry = ttk.Entry(section.custom_frame, textvariable=section.path_var, width=28)
        section.entry.pack(side=tk.LEFT)
        section.browse_btn = self._make_button(
            section.custom_frame, "button.browse",
            lambda s=section: self._browse_sound(s))
        section.browse_btn.pack(side=tk.LEFT, padx=(4, 0))

        section.key_var.trace_add(
            "write", lambda *_, s=section: self._update_custom_frame(s))
        self._init_sound_section(section)
        self._update_sound_controls(section)
        return row + 1

    def _init_sound_section(self, section: _SoundSection) -> None:
        path = self._config.get(section.config_key, section.default_path)
        # 過去のビルドが "custom:builtin:xxx" という壊れた値を書いていた。
        # 読み込み時に直しておかないと、内蔵音がカスタム扱いのまま残る。
        if path.startswith("custom:builtin:"):
            normalized = path[len("custom:"):]
            if normalized in section.keys:
                path = normalized
                self._config[section.config_key] = normalized
        if path in section.keys:
            section.key_var.set(path)
        else:
            section.key_var.set(_CUSTOM_SOUND_KEY)
            section.path_var.set(
                path[len("custom:"):] if path.startswith("custom:") else path)
        self._update_custom_frame(section)

    def _update_custom_frame(self, section: _SoundSection) -> None:
        if section.key_var.get() == _CUSTOM_SOUND_KEY:
            section.custom_frame.pack(fill=tk.X, pady=(2, 0))
        else:
            section.custom_frame.pack_forget()

    def _update_sound_controls(self, section: _SoundSection) -> None:
        if section.enabled_var is None:
            return
        enabled = section.enabled_var.get()
        section.combo.config(state="readonly" if enabled else "disabled")
        section.test_btn.config(state="normal" if enabled else "disabled")
        section.entry.config(state="normal" if enabled else "disabled")
        section.browse_btn.config(state="normal" if enabled else "disabled")

    def _on_sound_enabled_changed(self, section: _SoundSection) -> None:
        self._update_sound_controls(section)
        self._mark_dirty()

    def _sound_path_value(self, section: _SoundSection) -> str:
        key = section.key_var.get()
        if key != _CUSTOM_SOUND_KEY:
            return key
        return f"custom:{section.path_var.get()}"

    def _test_play(self, section: _SoundSection) -> None:
        path = self._sound_path_value(section)
        volume = self._config.get("alert_volume", 50)

        def _play():
            try:
                from notifier import Notifier
                Notifier().play_sound(path, volume)
            except Exception as e:
                logger.error("テスト再生に失敗しました (%s): %s", section.config_key, e)

        threading.Thread(target=_play, daemon=True).start()

    def _browse_sound(self, section: _SoundSection) -> None:
        path = filedialog.askopenfilename(
            title=t(section.browse_title_key),
            filetypes=[(t("filetype.wav"), "*.wav"), (t("filetype.all"), "*.*")],
        )
        if path:
            section.path_var.set(path)

    # -------------------------------------------------------------------------
    # 設定フォーム
    # -------------------------------------------------------------------------

    def _build_settings_form(self):
        colors = get_colors(self._resolve_theme())
        notebook = ttk.Notebook(self._root)
        notebook.pack(fill=tk.BOTH, padx=_PAD_OUTER, pady=(_PAD_INNER, _PAD_INNER), expand=True)

        self._build_monitor_tab(notebook, colors)
        self._build_notify_tab(notebook, colors)
        self._build_detail_tab(notebook, colors)

    def _build_monitor_tab(self, notebook, colors):
        monitor_frame = ttk.Frame(notebook)
        notebook.add(monitor_frame, text=t("tab.monitor"))
        self._register(lambda: notebook.tab(monitor_frame, text=t("tab.monitor")))
        content = self._add_card(monitor_frame, colors)
        content.columnconfigure(1, weight=1)

        self._make_headline_label(
            content, "section.device", colors,
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(_PAD_ROW[0], _PAD_INNER),
        )

        self._make_body_label(content, "label.input_device", colors,
                              row=1, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        device_keys = [d["raw_name"] for d in self._devices]
        self._device_var = tk.StringVar()
        self._device_combo = self._make_combo(
            content, device_keys, self._device_label, self._device_var, width=35)
        self._device_combo.widget.grid(row=1, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._select_initial_device(device_keys)

        self._make_body_label(content, "label.alert_interval", colors,
                              row=2, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._interval_var = tk.IntVar(value=self._config.get("alert_interval_sec", 30))
        self._interval_spinbox = ttk.Spinbox(
            content, from_=5, to=600, increment=5,
            textvariable=self._interval_var, width=10)
        self._interval_spinbox.grid(row=2, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

    def _select_initial_device(self, device_keys: list) -> None:
        if not device_keys:
            return
        saved_name = self._config.get("device_name")
        if saved_name in device_keys:
            self._device_var.set(saved_name)
            return
        saved_index = self._config.get("device_index")
        if saved_index is not None:
            matched = next((d for d in self._devices if d["index"] == saved_index), None)
            if matched is not None:
                self._device_var.set(matched["raw_name"])
                return
        default_device = next((d for d in self._devices if d.get("is_default")), None)
        self._device_var.set(
            default_device["raw_name"] if default_device else device_keys[0])

    def _build_notify_tab(self, notebook, colors):
        content = self._add_card(
            self._make_scrollable_tab(notebook, "tab.notify", colors), colors)
        content.columnconfigure(1, weight=1)

        self._make_headline_label(
            content, "section.alert", colors,
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(_PAD_ROW[0], _PAD_INNER),
        )

        self._make_body_label(content, "label.volume", colors,
                              row=1, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        volume_frame = self._make_frame(content, colors)
        volume_frame.grid(row=1, column=1, sticky=tk.EW, padx=6, pady=_PAD_ROW)
        volume_frame.columnconfigure(0, weight=1)

        self._volume_var = tk.IntVar(value=self._config.get("alert_volume", 50))
        self._volume_scale = ttk.Scale(
            volume_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self._volume_var,
            command=lambda v: self._volume_var.set(round(float(v))),
        )
        self._volume_scale.grid(row=0, column=0, sticky=tk.EW)

        self._volume_entry = ttk.Entry(volume_frame, textvariable=self._volume_var, width=5)
        self._volume_entry.grid(row=0, column=1, sticky=tk.W, padx=(8, 0))
        self._volume_entry.bind("<FocusOut>", self._on_volume_entry_commit)
        self._volume_entry.bind("<Return>", self._on_volume_entry_commit)

        self._alert_sound = _SoundSection(
            "alert_sound_path", None, _ALERT_SOUND_KEYS,
            "builtin:error", "dialog.select_alert_sound")
        self._pause_sound = _SoundSection(
            "pause_sound_path", "pause_sound_enabled", _STATUS_SOUND_KEYS,
            "builtin:marimba", "dialog.select_pause_sound")
        self._stop_sound = _SoundSection(
            "monitor_stop_sound_path", "monitor_stop_sound_enabled", _STATUS_SOUND_KEYS,
            "builtin:marimba", "dialog.select_stop_sound")
        self._resume_sound = _SoundSection(
            "monitor_resume_sound_path", "monitor_resume_sound_enabled", _STATUS_SOUND_KEYS,
            "builtin:notify_11", "dialog.select_resume_sound")
        self._sound_sections = [
            self._alert_sound, self._pause_sound, self._stop_sound, self._resume_sound,
        ]

        row = 2
        row = self._add_sound_section(content, colors, self._alert_sound, row,
                                      None, "label.alert_sound")
        row = self._add_sound_section(content, colors, self._pause_sound, row,
                                      "section.pause_sound", "label.pause_sound")
        row = self._add_sound_section(content, colors, self._stop_sound, row,
                                      "section.stop_sound", "label.stop_sound")
        self._add_sound_section(content, colors, self._resume_sound, row,
                                "section.resume_sound", "label.resume_sound")

    def _build_detail_tab(self, notebook, colors):
        content = self._add_card(
            self._make_scrollable_tab(notebook, "tab.detail", colors), colors)
        content.columnconfigure(1, weight=1)

        self._make_headline_label(
            content, "section.auto_pause", colors,
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(_PAD_ROW[0], _PAD_INNER),
        )

        self._make_body_label(content, "label.auto_pause", colors,
                              row=1, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._auto_pause_enabled_var = tk.BooleanVar(
            value=self._config.get("auto_pause_enabled", True))
        self._auto_pause_enabled_check = self._make_checkbutton(
            content, "check.auto_pause", self._auto_pause_enabled_var, self._mark_dirty)
        self._auto_pause_enabled_check.grid(row=1, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

        self._make_body_label(content, "label.auto_pause_count", colors,
                              row=2, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._auto_pause_alert_count_var = tk.IntVar(
            value=self._config.get("auto_pause_alert_count", 1))
        self._auto_pause_alert_count_spinbox = ttk.Spinbox(
            content, from_=1, to=10, increment=1,
            textvariable=self._auto_pause_alert_count_var, width=10)
        self._auto_pause_alert_count_spinbox.grid(row=2, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

        self._make_body_label(content, "hint.auto_resume", colors, wrap=_HINT_WRAP,
                              row=3, column=1, sticky=tk.W, padx=6, pady=(0, _PAD_INNER))

        self._make_headline_label(
            content, "section.sleep", colors,
            row=4, column=0, columnspan=2, sticky=tk.W, pady=(_PAD_ROW[0], _PAD_INNER),
        )

        self._make_body_label(content, "label.idle_suspend", colors,
                              row=5, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._idle_suspend_enabled_var = tk.BooleanVar(
            value=self._config.get("idle_suspend_enabled", True))
        self._idle_suspend_enabled_check = self._make_checkbutton(
            content, "check.idle_suspend", self._idle_suspend_enabled_var, self._mark_dirty)
        self._idle_suspend_enabled_check.grid(row=5, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

        self._make_body_label(content, "label.idle_suspend_sec", colors,
                              row=6, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._idle_suspend_sec_var = tk.IntVar(value=self._config.get("idle_suspend_sec", 180))
        self._idle_suspend_sec_spinbox = ttk.Spinbox(
            content, from_=30, to=1800, increment=30,
            textvariable=self._idle_suspend_sec_var, width=10)
        self._idle_suspend_sec_spinbox.grid(row=6, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

        self._make_body_label(content, "hint.idle_suspend_sec", colors, wrap=_HINT_WRAP,
                              row=7, column=1, sticky=tk.W, padx=6, pady=(0, _PAD_ROW[1]))

        self._make_body_label(content, "label.mic_share", colors,
                              row=8, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._mic_share_monitor_enabled_var = tk.BooleanVar(
            value=self._config.get("mic_share_monitor_enabled", True))
        self._mic_share_monitor_enabled_check = self._make_checkbutton(
            content, "check.mic_share", self._mic_share_monitor_enabled_var, self._mark_dirty)
        self._mic_share_monitor_enabled_check.grid(row=8, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

        self._make_body_label(content, "hint.mic_share", colors, wrap=_HINT_WRAP,
                              row=9, column=1, sticky=tk.W, padx=6, pady=(0, _PAD_INNER))

        self._make_headline_label(
            content, "section.app", colors,
            row=10, column=0, columnspan=2, sticky=tk.W, pady=(_PAD_ROW[0], _PAD_INNER),
        )

        self._make_body_label(content, "label.theme", colors,
                              row=11, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._theme_var = tk.StringVar(value=self._config.get("theme", "system"))
        self._theme_combo = self._make_combo(
            content, _THEME_KEYS, lambda k: t(f"theme.{k}"), self._theme_var, width=18)
        self._theme_combo.widget.grid(row=11, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

        self._make_body_label(content, "label.language", colors,
                              row=12, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._language_var = tk.StringVar(value=i18n.get_language())
        # 言語名はその言語自身の表記で出すため、訳し直す必要がない。
        self._language_combo = self._make_combo(
            content, i18n.available_languages(),
            lambda k: i18n.LANGUAGE_LABELS.get(k, k), self._language_var, width=18)
        self._language_combo.widget.grid(row=12, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._language_var.trace_add("write", lambda *_: self._on_language_selected())

        self._make_body_label(content, "label.version", colors,
                              row=13, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        version_value = self._make_value_label(
            content, version.version_line(), colors,
            row=13, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)
        # 更新日の書き方は言語ごとに違うため、版番号だけでも訳し直す必要がある。
        self._register(lambda: version_value.config(text=version.version_line()))

    def _on_language_selected(self) -> None:
        """言語プルダウンの選択を即座に画面へ反映する。

        再起動を求めると、選んだ言語が読めているのか確かめられない。
        """
        language = self._language_var.get()
        if language == i18n.get_language():
            return
        i18n.set_language(language)
        self._retranslate()

    def _build_button_area(self):
        colors = get_colors(self._resolve_theme())
        btn_frame = tk.Frame(self._root, background=colors["bg"], highlightthickness=0)
        btn_frame.pack(fill=tk.X, padx=_PAD_OUTER, pady=(_PAD_INNER, _PAD_OUTER))
        self._bg_frames.append(btn_frame)

        self._save_status_label = tk.Label(
            btn_frame,
            text="",
            font=theme.FONTS["caption"],
            background=colors["bg"],
            foreground=colors["secondary_label"],
        )
        self._save_status_label.pack(side=tk.LEFT, padx=8)

        self._version_label = tk.Label(
            btn_frame,
            text=version.version_line(),
            font=theme.FONTS["caption"],
            background=colors["bg"],
            foreground=colors["secondary_label"],
        )
        self._version_label.pack(side=tk.RIGHT, padx=8)
        self._register(lambda: self._version_label.config(text=version.version_line()))

    # -------------------------------------------------------------------------
    # イベントハンドラ
    # -------------------------------------------------------------------------

    def _on_volume_entry_commit(self, event=None):
        self._sync_volume_var()
        self._mark_dirty()

    def _sync_volume_var(self):
        try:
            value = int(self._volume_var.get())
        except (tk.TclError, ValueError):
            value = self._config.get("alert_volume", 50)
        self._volume_var.set(max(0, min(100, value)))

    def _read_int(self, var: tk.IntVar, key: str, low: int, high: int) -> int:
        """入力途中の空文字などで例外を出さずに読み取る。"""
        try:
            value = int(var.get())
        except (tk.TclError, ValueError):
            return self._config.get(key, low)
        return max(low, min(high, value))

    def _on_save(self, event=None):
        if self._save_after_id is not None:
            self._root.after_cancel(self._save_after_id)
            self._save_after_id = None
        self._suspend_dirty = True
        try:
            self._config["device_index"] = self._selected_device_index()
            self._config["device_name"] = self._selected_device_name()
            self._config["alert_interval_sec"] = self._read_int(
                self._interval_var, "alert_interval_sec", 5, 600)
            self._config["alert_sound_path"] = self._sound_path_value(self._alert_sound)
            self._config["pause_sound_enabled"] = self._pause_sound.enabled_var.get()
            self._config["pause_sound_path"] = self._sound_path_value(self._pause_sound)
            self._config["monitor_stop_sound_enabled"] = self._stop_sound.enabled_var.get()
            self._config["monitor_stop_sound_path"] = self._sound_path_value(self._stop_sound)
            self._config["monitor_resume_sound_enabled"] = self._resume_sound.enabled_var.get()
            self._config["monitor_resume_sound_path"] = self._sound_path_value(self._resume_sound)
            self._config["alert_volume"] = self._read_int(self._volume_var, "alert_volume", 0, 100)
            self._config["theme"] = self._theme_var.get()
            self._config["language"] = self._language_var.get()
            self._config["auto_pause_enabled"] = self._auto_pause_enabled_var.get()
            self._config["auto_pause_alert_count"] = self._read_int(
                self._auto_pause_alert_count_var, "auto_pause_alert_count", 1, 10)
            self._config["idle_suspend_enabled"] = self._idle_suspend_enabled_var.get()
            self._config["idle_suspend_sec"] = self._read_int(
                self._idle_suspend_sec_var, "idle_suspend_sec", 30, 1800)
            self._config["mic_share_monitor_enabled"] = self._mic_share_monitor_enabled_var.get()

            self._on_config_save(self._config)

            self._configured_theme = self._config["theme"]
            apply_theme(self._root, self._configured_theme, i18n.get_language())
            resolved_theme = self._resolve_theme()
            colors = get_colors(resolved_theme)
            self._apply_visual_theme(resolved_theme)
            self._apply_graph_theme(resolved_theme)

            self._dirty = False
            # 保存のたびに文字列が変わらないと、2回目以降に保存されたのかが
            # 分からない。時刻を添えて更新されたことを見えるようにする。
            self._save_status_label.config(
                text=t("save.saved", time=time.strftime('%H:%M:%S')),
                foreground=colors["success"],
            )
        finally:
            self._suspend_dirty = False

    def _selected_device(self) -> dict | None:
        selected = self._device_var.get()
        return next((d for d in self._devices if d["raw_name"] == selected), None)

    def _selected_device_index(self) -> int | None:
        matched = self._selected_device()
        return matched["index"] if matched else self._config.get("device_index")

    def _selected_device_name(self) -> str | None:
        matched = self._selected_device()
        return matched["raw_name"] if matched else self._config.get("device_name")

    def _toggle_monitor(self):
        if self._on_toggle_monitor is not None:
            self._on_toggle_monitor()
        elif not self._monitor.is_running:
            self._monitor.start()
        else:
            self._monitor.stop()
        self._monitor_btn_var.set(
            t("button.monitor_stop") if self._monitoring_active()
            else t("button.monitor_start"))

    # -------------------------------------------------------------------------
    # 波形更新
    # -------------------------------------------------------------------------

    def _update_status(self) -> None:
        colors = get_colors(self._resolve_theme())

        # 自動停止は監視ボタンを押さずに起きるため、トグル時だけの更新では
        # 表示が実態とずれる。ポーリングのたびに合わせ直す。
        self._monitor_btn_var.set(
            t("button.monitor_stop") if self._monitoring_active()
            else t("button.monitor_start"))

        if self._is_suspended is not None and self._is_suspended():
            self._status_label.config(
                text=t("status.idle_suspended"), foreground=colors["warning"]
            )
            return

        if not self._monitor.is_running:
            self._status_label.config(
                text=t("status.stopped"), foreground=colors["secondary_label"])
            return

        db, zero_ratio = self._monitor.levels
        levels = t("status.levels", db=f"{db:.1f}", ratio=f"{zero_ratio * 100:.0f}")
        if self._monitor.is_paused:
            self._status_label.config(
                text=t("status.paused") + levels, foreground=colors["warning"])
        else:
            self._status_label.config(
                text=t("status.monitoring") + levels, foreground=colors["success"])

    def _update_waveform(self):
        if not self._running:
            return

        self._update_status()

        if self._monitor.is_running:
            db_history = self._monitor.get_db_history()
            self._line.set_data(range(len(db_history)), db_history)
            self._ax.set_xlim(0, len(db_history))
            if self._zoom_mode:
                valid = db_history[db_history > DB_FLOOR]
                if len(valid) > 0:
                    self._ax.set_ylim(valid.min() - 5, min(valid.max() + 5, 0))
            else:
                self._ax.set_ylim(DB_FLOOR, 0)
        else:
            self._line.set_data([], [])

        self._canvas.draw_idle()
        self._root.after(500, self._update_waveform)

    # -------------------------------------------------------------------------
    # ライフサイクル
    # -------------------------------------------------------------------------

    def run(self) -> None:
        self._root.mainloop()

    def _on_close(self) -> None:
        # 保存待ちのまま閉じられると変更が失われるので、ここで確定させる
        if self._save_after_id is not None:
            self._root.after_cancel(self._save_after_id)
            self._save_after_id = None
        if self._dirty:
            self._on_save()
        self.destroy()

    def destroy(self) -> None:
        self._running = False
        self._suspend_dirty = True
        if self._save_after_id is not None:
            self._root.after_cancel(self._save_after_id)
            self._save_after_id = None
        for var in getattr(self, "_tracked_vars", []):
            for name in var.trace_info():
                var.trace_remove(name[0], name[1])
        self._tracked_vars = []
        self._retranslate_hooks = []
        self._monitor_btn_var = None
        self._root.destroy()
