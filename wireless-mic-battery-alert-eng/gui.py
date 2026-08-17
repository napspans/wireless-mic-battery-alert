import logging
import threading
import time
import tkinter as tk
import tkinter.filedialog as filedialog
import tkinter.ttk as ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from monitor import DB_FLOOR, AudioMonitor, list_input_devices
import theme
import version
from theme import apply_theme, get_colors, get_system_theme

logger = logging.getLogger(__name__)

_PAD_OUTER = 16
_PAD_INNER = 8
_PAD_ROW = (6, 6)

_SOUND_OPTIONS = ["内蔵: Chime", "内蔵: Error", "内蔵: Marimba", "カスタム..."]
_COMBO_TO_PATH = {
    "内蔵: Chime": "builtin:chime",
    "内蔵: Error": "builtin:error",
    "内蔵: Marimba": "builtin:marimba",
}
_PATH_TO_COMBO = {v: k for k, v in _COMBO_TO_PATH.items()}
_PAUSE_SOUND_OPTIONS = ["内蔵: Notify 04", "内蔵: Notify 11", "内蔵: Chime", "内蔵: Error", "内蔵: Marimba", "カスタム..."]
_PAUSE_COMBO_TO_PATH = {
    "内蔵: Notify 04": "builtin:notify_04",
    "内蔵: Notify 11": "builtin:notify_11",
    "内蔵: Chime": "builtin:chime",
    "内蔵: Error": "builtin:error",
    "内蔵: Marimba": "builtin:marimba",
}
_PAUSE_PATH_TO_COMBO = {v: k for k, v in _PAUSE_COMBO_TO_PATH.items()}



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
        self._checkbuttons: list[tk.Checkbutton] = []
        self._scroll_canvases: list[tk.Canvas] = []

        self._root = tk.Tk()
        self._root.title("マイク電池切れ警告 - 設定")
        self._root.geometry("640x720")
        self._root.resizable(False, False)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._devices = list_input_devices()

        self._build_waveform_area()
        self._build_settings_form()
        self._build_button_area()
        self._root.bind_all("<MouseWheel>", self._on_mousewheel)

        _theme = self._config.get("theme", "system")
        apply_theme(self._root, _theme)
        resolved_theme = self._resolve_theme()
        self._apply_visual_theme(resolved_theme)
        self._apply_graph_theme(resolved_theme)

        if self._monitoring_active():
            self._monitor_btn_var.set("監視 停止")

        self._watch_variables()
        self._suspend_dirty = False

        self._root.after(500, self._update_waveform)

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
            self._sound_combo_var,
            self._sound_var,
            self._pause_sound_enabled_var,
            self._pause_sound_combo_var,
            self._pause_sound_var,
            self._monitor_stop_sound_enabled_var,
            self._monitor_stop_sound_combo_var,
            self._monitor_stop_sound_var,
            self._monitor_resume_sound_enabled_var,
            self._monitor_resume_sound_combo_var,
            self._monitor_resume_sound_var,
            self._auto_pause_enabled_var,
            self._auto_pause_alert_count_var,
            self._idle_suspend_enabled_var,
            self._idle_suspend_sec_var,
            self._mic_share_monitor_enabled_var,
            self._theme_var,
        ]
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
            text="保存中…", foreground=colors["secondary_label"]
        )
        if self._save_after_id is not None:
            self._root.after_cancel(self._save_after_id)
        self._save_after_id = self._root.after(self._SAVE_DEBOUNCE_MS, self._on_save)

    # -------------------------------------------------------------------------
    # UI構築
    # -------------------------------------------------------------------------

    def _resolve_theme(self) -> str:
        theme_name = self._config.get("theme", "system")
        return theme_name if theme_name != "system" else get_system_theme()

    def _add_card(self, parent, colors: dict) -> tk.Frame:
        card_outer = tk.Frame(parent, background=colors["bg"], highlightthickness=0)
        card_outer.pack(fill=tk.BOTH, expand=True, padx=_PAD_INNER, pady=_PAD_INNER)
        card = tk.Frame(card_outer, background=colors["surface"], highlightthickness=0)
        card.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)
        card_inner = tk.Frame(card, background=colors["surface"], highlightthickness=0, padx=12, pady=12)
        card_inner.pack(fill=tk.BOTH, expand=True)
        self._bg_frames.append(card_outer)
        self._cards.append(card)
        self._card_inners.append(card_inner)
        return card_inner

    def _make_body_label(self, parent, text: str, colors: dict, **grid_kwargs):
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

    def _make_headline_label(self, parent, text: str, colors: dict, **grid_kwargs):
        label = tk.Label(
            parent,
            text=text,
            font=theme.FONTS["headline"],
            foreground=colors["label"],
            background=colors["surface"],
        )
        label.grid(**grid_kwargs)
        self._headline_labels.append(label)
        return label

    def _apply_visual_theme(self, resolved_theme: str) -> None:
        colors = get_colors(resolved_theme)
        self._root.configure(background=colors["bg"])
        for frame in self._bg_frames:
            frame.configure(background=colors["bg"])
        for card in self._cards:
            card.configure(background=colors["surface"])
        for inner in self._card_inners:
            inner.configure(background=colors["surface"])
        for label in self._headline_labels:
            label.configure(foreground=colors["label"], background=colors["surface"])
        for label in self._body_labels:
            label.configure(foreground=colors["label"], background=colors["surface"])

        for canvas in self._scroll_canvases:
            canvas.configure(background=colors["bg"])
        if hasattr(self, "_save_status_label"):
            self._save_status_label.configure(background=colors["bg"], foreground=colors["secondary_label"])
        if hasattr(self, "_version_label"):
            self._version_label.configure(background=colors["bg"], foreground=colors["secondary_label"])

    def _make_scrollable_tab(self, notebook, text: str, colors: dict) -> tk.Frame:
        """スクロールできるタブを追加し、中身を載せる枠を返す。

        ウィンドウはサイズ固定のため、設定項目が増えるとタブ内に収まらなくなる。
        """
        frame = ttk.Frame(notebook)
        notebook.add(frame, text=text)

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

    def _make_checkbutton(self, parent, text: str, variable, command, colors: dict) -> tk.Checkbutton:
        checkbutton = ttk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            command=command,
        )
        self._checkbuttons.append(checkbutton)
        return checkbutton

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

        self._zoom_btn_var = tk.StringVar(value='ズーム表示')
        self._zoom_btn = ttk.Button(waveform_frame, textvariable=self._zoom_btn_var, command=self._toggle_zoom)
        self._zoom_btn.pack(anchor='ne', padx=_PAD_INNER, pady=(0, 4))

        self._canvas = FigureCanvasTkAgg(self._fig, master=waveform_frame)
        self._canvas.get_tk_widget().pack(fill=tk.X)
        ttk.Separator(self._root, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=_PAD_OUTER, pady=(4, 0))

        status_row = tk.Frame(self._root, background=colors["bg"], highlightthickness=0)
        status_row.pack(fill=tk.X, padx=_PAD_OUTER, pady=(2, 0))
        self._bg_frames.append(status_row)

        self._status_label = ttk.Label(status_row, text="○ 停止中", font=theme.FONTS["caption"], anchor=tk.W)
        self._status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._monitor_btn_var = tk.StringVar(value="監視 開始")
        self._monitor_btn = ttk.Button(
            status_row,
            textvariable=self._monitor_btn_var,
            command=self._toggle_monitor,
            width=12,
            style="Accent.TButton",
        )
        self._monitor_btn.pack(side=tk.RIGHT)

    def _toggle_zoom(self):
        self._zoom_mode = not self._zoom_mode
        self._zoom_btn_var.set('全体表示' if self._zoom_mode else 'ズーム表示')

    def _apply_graph_theme(self, theme: str) -> None:
        colors = get_colors(theme)
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

    def _build_settings_form(self):
        colors = get_colors(self._resolve_theme())
        notebook = ttk.Notebook(self._root)
        notebook.pack(fill=tk.BOTH, padx=_PAD_OUTER, pady=(_PAD_INNER, _PAD_INNER), expand=True)

        # ── タブ1: 監視設定 ──────────────────────────────────────────────
        monitor_frame = ttk.Frame(notebook)
        notebook.add(monitor_frame, text="監視設定")
        monitor_content = self._add_card(monitor_frame, colors)
        monitor_content.columnconfigure(1, weight=1)

        self._make_headline_label(
            monitor_content,
            text="デバイスと検知パラメータ",
            colors=colors,
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(_PAD_ROW[0], _PAD_INNER),
        )

        # 入力デバイス
        self._make_body_label(monitor_content, "入力デバイス", colors, row=1, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        device_names = [d["name"] for d in self._devices] if self._devices else ["（デバイスなし）"]
        self._device_var = tk.StringVar()
        self._device_combo = ttk.Combobox(monitor_content, textvariable=self._device_var, values=device_names, state="readonly", width=35)
        self._device_combo.grid(row=1, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)
        current_index = self._config.get("device_index")
        if current_index is not None:
            matched = next((d for d in self._devices if d["index"] == current_index), None)
            if matched:
                self._device_var.set(matched["name"])
        elif device_names:
            default_device = next((d for d in self._devices if d.get("is_default")), None)
            if default_device is not None:
                self._device_var.set(default_device["name"])
            else:
                self._device_combo.current(0)

        # アラート間隔 (秒)
        self._make_body_label(monitor_content, "アラート間隔 (秒)", colors, row=2, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._interval_var = tk.IntVar(value=self._config.get("alert_interval_sec", 30))
        self._interval_spinbox = ttk.Spinbox(monitor_content, from_=5, to=600, increment=5, textvariable=self._interval_var, width=10)
        self._interval_spinbox.grid(row=2, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

        # ── タブ2: 通知設定 ──────────────────────────────────────────────
        notify_scrollable_inner = self._make_scrollable_tab(notebook, "通知設定", colors)
        notify_content = self._add_card(notify_scrollable_inner, colors)
        notify_content.columnconfigure(1, weight=1)

        self._make_headline_label(
            notify_content,
            text="アラートと通知",
            colors=colors,
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(_PAD_ROW[0], _PAD_INNER),
        )

        # 全体音量
        self._make_body_label(notify_content, "全体音量 (0-100)", colors, row=1, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        volume_frame = tk.Frame(notify_content, background=colors["surface"], highlightthickness=0)
        volume_frame.grid(row=1, column=1, sticky=tk.EW, padx=6, pady=_PAD_ROW)
        volume_frame.columnconfigure(0, weight=1)
        self._card_inners.append(volume_frame)

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

        # 通知音
        self._make_body_label(notify_content, "通知音", colors, row=2, column=0, sticky=tk.NW, padx=6, pady=_PAD_ROW)
        sound_outer = tk.Frame(notify_content, background=colors["surface"], highlightthickness=0)
        sound_outer.grid(row=2, column=1, sticky=tk.EW, padx=6, pady=_PAD_ROW)
        self._card_inners.append(sound_outer)

        sound_select_frame = tk.Frame(sound_outer, background=colors["surface"], highlightthickness=0)
        sound_select_frame.pack(fill=tk.X)
        self._card_inners.append(sound_select_frame)
        self._sound_combo_var = tk.StringVar()
        self._sound_combo = ttk.Combobox(
            sound_select_frame, textvariable=self._sound_combo_var,
            values=_SOUND_OPTIONS, state="readonly", width=20,
        )
        self._sound_combo.pack(side=tk.LEFT)
        ttk.Button(sound_select_frame, text="テスト再生", command=self._test_play_sound).pack(side=tk.LEFT, padx=(4, 0))

        self._custom_sound_frame = tk.Frame(sound_outer, background=colors["surface"], highlightthickness=0)
        self._card_inners.append(self._custom_sound_frame)
        self._sound_var = tk.StringVar()
        self._sound_entry = ttk.Entry(self._custom_sound_frame, textvariable=self._sound_var, width=28)
        self._sound_entry.pack(side=tk.LEFT)
        ttk.Button(self._custom_sound_frame, text="参照", command=self._browse_sound).pack(side=tk.LEFT, padx=(4, 0))

        self._sound_combo.bind("<<ComboboxSelected>>", self._on_sound_combo_changed)
        self._init_sound_ui()

        self._make_headline_label(
            notify_content,
            text="一時停止サウンド",
            colors=colors,
            row=3, column=0, columnspan=2, sticky=tk.W, pady=(_PAD_ROW[0], _PAD_INNER),
        )

        self._make_body_label(notify_content, "一時停止サウンド", colors, row=4, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._pause_sound_enabled_var = tk.BooleanVar(value=self._config.get("pause_sound_enabled", True))
        self._pause_sound_enabled_check = self._make_checkbutton(
            notify_content,
            text="有効にする",
            variable=self._pause_sound_enabled_var,
            command=self._on_pause_sound_enabled_changed,
            colors=colors,
        )
        self._pause_sound_enabled_check.grid(row=4, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

        self._make_body_label(notify_content, "サウンドファイル", colors, row=5, column=0, sticky=tk.NW, padx=6, pady=_PAD_ROW)
        pause_sound_outer = tk.Frame(notify_content, background=colors["surface"], highlightthickness=0)
        pause_sound_outer.grid(row=5, column=1, sticky=tk.EW, padx=6, pady=_PAD_ROW)
        self._card_inners.append(pause_sound_outer)

        pause_sound_select_frame = tk.Frame(pause_sound_outer, background=colors["surface"], highlightthickness=0)
        pause_sound_select_frame.pack(fill=tk.X)
        self._card_inners.append(pause_sound_select_frame)
        self._pause_sound_combo_var = tk.StringVar()
        self._pause_sound_combo = ttk.Combobox(
            pause_sound_select_frame,
            textvariable=self._pause_sound_combo_var,
            values=_PAUSE_SOUND_OPTIONS,
            state="readonly",
            width=20,
        )
        self._pause_sound_combo.pack(side=tk.LEFT)
        self._pause_sound_test_btn = ttk.Button(
            pause_sound_select_frame,
            text="テスト再生",
            command=self._test_play_pause_sound,
        )
        self._pause_sound_test_btn.pack(side=tk.LEFT, padx=(4, 0))

        self._custom_pause_sound_frame = tk.Frame(pause_sound_outer, background=colors["surface"], highlightthickness=0)
        self._card_inners.append(self._custom_pause_sound_frame)
        self._pause_sound_var = tk.StringVar()
        self._pause_sound_entry = ttk.Entry(self._custom_pause_sound_frame, textvariable=self._pause_sound_var, width=28)
        self._pause_sound_entry.pack(side=tk.LEFT)
        self._pause_sound_browse_btn = ttk.Button(self._custom_pause_sound_frame, text="参照", command=self._browse_pause_sound)
        self._pause_sound_browse_btn.pack(side=tk.LEFT, padx=(4, 0))

        self._pause_sound_combo.bind("<<ComboboxSelected>>", self._on_pause_sound_combo_changed)
        self._init_pause_sound_ui()
        self._update_pause_sound_controls()

        self._make_headline_label(
            notify_content,
            text="監視停止サウンド",
            colors=colors,
            row=6, column=0, columnspan=2, sticky=tk.W, pady=(_PAD_ROW[0], _PAD_INNER),
        )

        self._make_body_label(notify_content, "監視停止サウンド", colors, row=7, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._monitor_stop_sound_enabled_var = tk.BooleanVar(value=self._config.get("monitor_stop_sound_enabled", True))
        self._monitor_stop_sound_enabled_check = self._make_checkbutton(
            notify_content,
            text="有効にする",
            variable=self._monitor_stop_sound_enabled_var,
            command=self._on_monitor_stop_sound_enabled_changed,
            colors=colors,
        )
        self._monitor_stop_sound_enabled_check.grid(row=7, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

        self._make_body_label(notify_content, "サウンドファイル", colors, row=8, column=0, sticky=tk.NW, padx=6, pady=_PAD_ROW)
        monitor_stop_sound_outer = tk.Frame(notify_content, background=colors["surface"], highlightthickness=0)
        monitor_stop_sound_outer.grid(row=8, column=1, sticky=tk.EW, padx=6, pady=_PAD_ROW)
        self._card_inners.append(monitor_stop_sound_outer)

        monitor_stop_sound_select_frame = tk.Frame(monitor_stop_sound_outer, background=colors["surface"], highlightthickness=0)
        monitor_stop_sound_select_frame.pack(fill=tk.X)
        self._card_inners.append(monitor_stop_sound_select_frame)
        self._monitor_stop_sound_combo_var = tk.StringVar()
        self._monitor_stop_sound_combo = ttk.Combobox(
            monitor_stop_sound_select_frame,
            textvariable=self._monitor_stop_sound_combo_var,
            values=_PAUSE_SOUND_OPTIONS,
            state="readonly",
            width=20,
        )
        self._monitor_stop_sound_combo.pack(side=tk.LEFT)
        self._monitor_stop_sound_test_btn = ttk.Button(
            monitor_stop_sound_select_frame,
            text="テスト再生",
            command=self._test_play_monitor_stop_sound,
        )
        self._monitor_stop_sound_test_btn.pack(side=tk.LEFT, padx=(4, 0))

        self._custom_monitor_stop_sound_frame = tk.Frame(monitor_stop_sound_outer, background=colors["surface"], highlightthickness=0)
        self._card_inners.append(self._custom_monitor_stop_sound_frame)
        self._monitor_stop_sound_var = tk.StringVar()
        self._monitor_stop_sound_entry = ttk.Entry(self._custom_monitor_stop_sound_frame, textvariable=self._monitor_stop_sound_var, width=28)
        self._monitor_stop_sound_entry.pack(side=tk.LEFT)
        self._monitor_stop_sound_browse_btn = ttk.Button(self._custom_monitor_stop_sound_frame, text="参照", command=self._browse_monitor_stop_sound)
        self._monitor_stop_sound_browse_btn.pack(side=tk.LEFT, padx=(4, 0))

        self._monitor_stop_sound_combo.bind("<<ComboboxSelected>>", self._on_monitor_stop_sound_combo_changed)
        self._init_monitor_stop_sound_ui()
        self._update_monitor_stop_sound_controls()

        self._make_headline_label(
            notify_content,
            text="監視再開サウンド",
            colors=colors,
            row=9, column=0, columnspan=2, sticky=tk.W, pady=(_PAD_ROW[0], _PAD_INNER),
        )

        self._make_body_label(notify_content, "監視再開サウンド", colors, row=10, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._monitor_resume_sound_enabled_var = tk.BooleanVar(value=self._config.get("monitor_resume_sound_enabled", True))
        self._monitor_resume_sound_enabled_check = self._make_checkbutton(
            notify_content,
            text="有効にする",
            variable=self._monitor_resume_sound_enabled_var,
            command=self._on_monitor_resume_sound_enabled_changed,
            colors=colors,
        )
        self._monitor_resume_sound_enabled_check.grid(row=10, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

        self._make_body_label(notify_content, "サウンドファイル", colors, row=11, column=0, sticky=tk.NW, padx=6, pady=_PAD_ROW)
        monitor_resume_sound_outer = tk.Frame(notify_content, background=colors["surface"], highlightthickness=0)
        monitor_resume_sound_outer.grid(row=11, column=1, sticky=tk.EW, padx=6, pady=_PAD_ROW)
        self._card_inners.append(monitor_resume_sound_outer)

        monitor_resume_sound_select_frame = tk.Frame(monitor_resume_sound_outer, background=colors["surface"], highlightthickness=0)
        monitor_resume_sound_select_frame.pack(fill=tk.X)
        self._card_inners.append(monitor_resume_sound_select_frame)
        self._monitor_resume_sound_combo_var = tk.StringVar()
        self._monitor_resume_sound_combo = ttk.Combobox(
            monitor_resume_sound_select_frame,
            textvariable=self._monitor_resume_sound_combo_var,
            values=_PAUSE_SOUND_OPTIONS,
            state="readonly",
            width=20,
        )
        self._monitor_resume_sound_combo.pack(side=tk.LEFT)
        self._monitor_resume_sound_test_btn = ttk.Button(
            monitor_resume_sound_select_frame,
            text="テスト再生",
            command=self._test_play_monitor_resume_sound,
        )
        self._monitor_resume_sound_test_btn.pack(side=tk.LEFT, padx=(4, 0))

        self._custom_monitor_resume_sound_frame = tk.Frame(monitor_resume_sound_outer, background=colors["surface"], highlightthickness=0)
        self._card_inners.append(self._custom_monitor_resume_sound_frame)
        self._monitor_resume_sound_var = tk.StringVar()
        self._monitor_resume_sound_entry = ttk.Entry(self._custom_monitor_resume_sound_frame, textvariable=self._monitor_resume_sound_var, width=28)
        self._monitor_resume_sound_entry.pack(side=tk.LEFT)
        self._monitor_resume_sound_browse_btn = ttk.Button(self._custom_monitor_resume_sound_frame, text="参照", command=self._browse_monitor_resume_sound)
        self._monitor_resume_sound_browse_btn.pack(side=tk.LEFT, padx=(4, 0))

        self._monitor_resume_sound_combo.bind("<<ComboboxSelected>>", self._on_monitor_resume_sound_combo_changed)
        self._init_monitor_resume_sound_ui()
        self._update_monitor_resume_sound_controls()

        # ── タブ3: 詳細設定 ──────────────────────────────────────────────
        detail_scrollable_inner = self._make_scrollable_tab(notebook, "詳細設定", colors)
        detail_content = self._add_card(detail_scrollable_inner, colors)
        detail_content.columnconfigure(1, weight=1)

        self._make_headline_label(
            detail_content,
            text="監視の自動一時停止",
            colors=colors,
            row=0, column=0, columnspan=2, sticky=tk.W, pady=(_PAD_ROW[0], _PAD_INNER),
        )

        self._make_body_label(detail_content, "自動一時停止", colors, row=1, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._auto_pause_enabled_var = tk.BooleanVar(value=self._config.get("auto_pause_enabled", True))
        self._auto_pause_enabled_check = self._make_checkbutton(
            detail_content,
            text="アラート後に監視を一時停止する",
            variable=self._auto_pause_enabled_var,
            command=self._mark_dirty,
            colors=colors,
        )
        self._auto_pause_enabled_check.grid(row=1, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

        self._make_body_label(detail_content, "一時停止までのアラート回数", colors, row=2, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._auto_pause_alert_count_var = tk.IntVar(value=self._config.get("auto_pause_alert_count", 1))
        self._auto_pause_alert_count_spinbox = ttk.Spinbox(
            detail_content, from_=1, to=10, increment=1,
            textvariable=self._auto_pause_alert_count_var, width=10,
        )
        self._auto_pause_alert_count_spinbox.grid(row=2, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

        self._make_body_label(
            detail_content, "信号が戻ると自動的に監視を再開します", colors,
            row=3, column=1, sticky=tk.W, padx=6, pady=(0, _PAD_INNER),
        )

        self._make_headline_label(
            detail_content,
            text="スリープ連動",
            colors=colors,
            row=4, column=0, columnspan=2, sticky=tk.W, pady=(_PAD_ROW[0], _PAD_INNER),
        )

        self._make_body_label(detail_content, "無操作で自動停止", colors, row=5, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._idle_suspend_enabled_var = tk.BooleanVar(
            value=self._config.get("idle_suspend_enabled", True))
        self._idle_suspend_enabled_check = self._make_checkbutton(
            detail_content,
            text="PC の無操作が続いたら監視を止める",
            variable=self._idle_suspend_enabled_var,
            command=self._mark_dirty,
            colors=colors,
        )
        self._idle_suspend_enabled_check.grid(row=5, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

        self._make_body_label(detail_content, "無操作と判定するまで（秒）", colors, row=6, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._idle_suspend_sec_var = tk.IntVar(value=self._config.get("idle_suspend_sec", 180))
        self._idle_suspend_sec_spinbox = ttk.Spinbox(
            detail_content, from_=30, to=1800, increment=30,
            textvariable=self._idle_suspend_sec_var, width=10,
        )
        self._idle_suspend_sec_spinbox.grid(row=6, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

        self._make_body_label(
            detail_content, "Windows のスリープ設定より短くしてください", colors,
            row=7, column=1, sticky=tk.W, padx=6, pady=(0, _PAD_ROW[1]),
        )

        self._make_body_label(detail_content, "他アプリ使用中は継続", colors, row=8, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._mic_share_monitor_enabled_var = tk.BooleanVar(
            value=self._config.get("mic_share_monitor_enabled", True))
        self._mic_share_monitor_enabled_check = self._make_checkbutton(
            detail_content,
            text="他のアプリがマイクを使用中は監視を続ける",
            variable=self._mic_share_monitor_enabled_var,
            command=self._mark_dirty,
            colors=colors,
        )
        self._mic_share_monitor_enabled_check.grid(row=8, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

        self._make_body_label(
            detail_content, "マイクを開いたままだと Windows がスリープしません", colors,
            row=9, column=1, sticky=tk.W, padx=6, pady=(0, _PAD_INNER),
        )

        self._make_headline_label(
            detail_content,
            text="アプリ設定",
            colors=colors,
            row=10, column=0, columnspan=2, sticky=tk.W, pady=(_PAD_ROW[0], _PAD_INNER),
        )

        self._make_body_label(detail_content, "テーマ", colors, row=11, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._theme_var = tk.StringVar(value=self._config.get("theme", "system"))
        self._theme_combo = ttk.Combobox(detail_content, textvariable=self._theme_var, values=["system", "light", "dark"], state="readonly", width=10)
        self._theme_combo.grid(row=11, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW)

        self._make_body_label(detail_content, "バージョン", colors, row=12, column=0, sticky=tk.W, padx=6, pady=_PAD_ROW)
        self._make_body_label(
            detail_content, version.version_line(), colors,
            row=12, column=1, sticky=tk.W, padx=6, pady=_PAD_ROW,
        )

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

    # -------------------------------------------------------------------------
    # イベントハンドラ
    # -------------------------------------------------------------------------

    def _init_sound_ui(self):
        path = self._config.get("alert_sound_path", "builtin:error")
        if path in _PATH_TO_COMBO:
            self._sound_combo_var.set(_PATH_TO_COMBO[path])
            self._custom_sound_frame.pack_forget()
        else:
            self._sound_combo_var.set("カスタム...")
            custom_path = path[len("custom:"):] if path.startswith("custom:") else path
            self._sound_var.set(custom_path)
            self._custom_sound_frame.pack(fill=tk.X, pady=(2, 0))

    def _on_sound_combo_changed(self, event=None):
        if self._sound_combo_var.get() == "カスタム...":
            self._custom_sound_frame.pack(fill=tk.X, pady=(2, 0))
        else:
            self._custom_sound_frame.pack_forget()
            self._mark_dirty()

    def _init_pause_sound_ui(self):
        path = self._config.get("pause_sound_path", "builtin:marimba")
        if path in _PAUSE_PATH_TO_COMBO:
            self._pause_sound_combo_var.set(_PAUSE_PATH_TO_COMBO[path])
            self._custom_pause_sound_frame.pack_forget()
        else:
            self._pause_sound_combo_var.set("カスタム...")
            custom_path = path[len("custom:"):] if path.startswith("custom:") else path
            self._pause_sound_var.set(custom_path)
            self._custom_pause_sound_frame.pack(fill=tk.X, pady=(2, 0))

    def _on_pause_sound_combo_changed(self, event=None):
        if self._pause_sound_combo_var.get() == "カスタム...":
            self._custom_pause_sound_frame.pack(fill=tk.X, pady=(2, 0))
        else:
            self._custom_pause_sound_frame.pack_forget()
        self._mark_dirty()

    def _init_monitor_stop_sound_ui(self):
        path = self._config.get("monitor_stop_sound_path", "builtin:marimba")
        if path.startswith("custom:builtin:"):
            normalized_path = path[len("custom:"):]
            if normalized_path in _PAUSE_PATH_TO_COMBO:
                path = normalized_path
                self._config["monitor_stop_sound_path"] = normalized_path
        if path in _PAUSE_PATH_TO_COMBO:
            self._monitor_stop_sound_combo_var.set(_PAUSE_PATH_TO_COMBO[path])
            self._custom_monitor_stop_sound_frame.pack_forget()
        else:
            self._monitor_stop_sound_combo_var.set("カスタム...")
            custom_path = path[len("custom:"):] if path.startswith("custom:") else path
            self._monitor_stop_sound_var.set(custom_path)
            self._custom_monitor_stop_sound_frame.pack(fill=tk.X, pady=(2, 0))

    def _on_monitor_stop_sound_combo_changed(self, event=None):
        if self._monitor_stop_sound_combo_var.get() == "カスタム...":
            self._custom_monitor_stop_sound_frame.pack(fill=tk.X, pady=(2, 0))
        else:
            self._custom_monitor_stop_sound_frame.pack_forget()
        self._mark_dirty()

    def _init_monitor_resume_sound_ui(self):
        path = self._config.get("monitor_resume_sound_path", "builtin:notify_11")
        if path.startswith("custom:builtin:"):
            normalized_path = path[len("custom:"):]
            if normalized_path in _PAUSE_PATH_TO_COMBO:
                path = normalized_path
                self._config["monitor_resume_sound_path"] = normalized_path
        if path in _PAUSE_PATH_TO_COMBO:
            self._monitor_resume_sound_combo_var.set(_PAUSE_PATH_TO_COMBO[path])
            self._custom_monitor_resume_sound_frame.pack_forget()
        else:
            self._monitor_resume_sound_combo_var.set("カスタム...")
            custom_path = path[len("custom:"):] if path.startswith("custom:") else path
            self._monitor_resume_sound_var.set(custom_path)
            self._custom_monitor_resume_sound_frame.pack(fill=tk.X, pady=(2, 0))

    def _on_monitor_resume_sound_combo_changed(self, event=None):
        if self._monitor_resume_sound_combo_var.get() == "カスタム...":
            self._custom_monitor_resume_sound_frame.pack(fill=tk.X, pady=(2, 0))
        else:
            self._custom_monitor_resume_sound_frame.pack_forget()
        self._mark_dirty()

    def _update_pause_sound_controls(self):
        enabled = self._pause_sound_enabled_var.get()
        combo_state = "readonly" if enabled else "disabled"
        button_state = "normal" if enabled else "disabled"
        entry_state = "normal" if enabled else "disabled"
        self._pause_sound_combo.config(state=combo_state)
        self._pause_sound_test_btn.config(state=button_state)
        self._pause_sound_entry.config(state=entry_state)
        self._pause_sound_browse_btn.config(state=button_state)

    def _on_pause_sound_enabled_changed(self):
        self._update_pause_sound_controls()
        self._mark_dirty()

    def _update_monitor_stop_sound_controls(self):
        enabled = self._monitor_stop_sound_enabled_var.get()
        combo_state = "readonly" if enabled else "disabled"
        button_state = "normal" if enabled else "disabled"
        entry_state = "normal" if enabled else "disabled"
        self._monitor_stop_sound_combo.config(state=combo_state)
        self._monitor_stop_sound_test_btn.config(state=button_state)
        self._monitor_stop_sound_entry.config(state=entry_state)
        self._monitor_stop_sound_browse_btn.config(state=button_state)

    def _on_monitor_stop_sound_enabled_changed(self):
        self._update_monitor_stop_sound_controls()
        self._mark_dirty()

    def _update_monitor_resume_sound_controls(self):
        enabled = self._monitor_resume_sound_enabled_var.get()
        combo_state = "readonly" if enabled else "disabled"
        button_state = "normal" if enabled else "disabled"
        entry_state = "normal" if enabled else "disabled"
        self._monitor_resume_sound_combo.config(state=combo_state)
        self._monitor_resume_sound_test_btn.config(state=button_state)
        self._monitor_resume_sound_entry.config(state=entry_state)
        self._monitor_resume_sound_browse_btn.config(state=button_state)

    def _on_monitor_resume_sound_enabled_changed(self):
        self._update_monitor_resume_sound_controls()
        self._mark_dirty()

    def _get_sound_path_value(self) -> str:
        selected = self._sound_combo_var.get()
        if selected in _COMBO_TO_PATH:
            return _COMBO_TO_PATH[selected]
        return f"custom:{self._sound_var.get()}"

    def _get_pause_sound_path_value(self) -> str:
        selected = self._pause_sound_combo_var.get()
        if selected in _PAUSE_COMBO_TO_PATH:
            return _PAUSE_COMBO_TO_PATH[selected]
        return f"custom:{self._pause_sound_var.get()}"

    def _get_monitor_stop_sound_path_value(self) -> str:
        selected = self._monitor_stop_sound_combo_var.get()
        if selected in _PAUSE_COMBO_TO_PATH:
            return _PAUSE_COMBO_TO_PATH[selected]
        return f"custom:{self._monitor_stop_sound_var.get()}"

    def _get_monitor_resume_sound_path_value(self) -> str:
        selected = self._monitor_resume_sound_combo_var.get()
        if selected in _PAUSE_COMBO_TO_PATH:
            return _PAUSE_COMBO_TO_PATH[selected]
        return f"custom:{self._monitor_resume_sound_var.get()}"

    def _test_play_sound(self):
        path = self._get_sound_path_value()
        volume = self._config.get("alert_volume", 50)

        def _play():
            try:
                from notifier import Notifier
                Notifier().play_sound(path, volume)
            except Exception as e:
                logger.error("テスト再生に失敗しました: %s", e)

        threading.Thread(target=_play, daemon=True).start()

    def _test_play_pause_sound(self):
        path = self._get_pause_sound_path_value()
        volume = self._config.get("alert_volume", 50)

        def _play():
            try:
                from notifier import Notifier
                Notifier().play_sound(path, volume)
            except Exception as e:
                logger.error("一時停止サウンドのテスト再生に失敗しました: %s", e)

        threading.Thread(target=_play, daemon=True).start()

    def _test_play_monitor_stop_sound(self):
        path = self._get_monitor_stop_sound_path_value()
        volume = self._config.get("alert_volume", 50)

        def _play():
            try:
                from notifier import Notifier
                Notifier().play_sound(path, volume)
            except Exception as e:
                logger.error("監視停止サウンドのテスト再生に失敗しました: %s", e)

        threading.Thread(target=_play, daemon=True).start()

    def _test_play_monitor_resume_sound(self):
        path = self._get_monitor_resume_sound_path_value()
        volume = self._config.get("alert_volume", 50)

        def _play():
            try:
                from notifier import Notifier
                Notifier().play_sound(path, volume)
            except Exception as e:
                logger.error("監視再開サウンドのテスト再生に失敗しました: %s", e)

        threading.Thread(target=_play, daemon=True).start()

    def _browse_sound(self):
        path = filedialog.askopenfilename(
            title="通知音ファイルを選択",
            filetypes=[("WAV ファイル", "*.wav"), ("すべてのファイル", "*.*")],
        )
        if path:
            self._sound_var.set(path)

    def _browse_pause_sound(self):
        path = filedialog.askopenfilename(
            title="一時停止サウンドファイルを選択",
            filetypes=[("WAV ファイル", "*.wav"), ("すべてのファイル", "*.*")],
        )
        if path:
            self._pause_sound_var.set(path)

    def _browse_monitor_stop_sound(self):
        path = filedialog.askopenfilename(
            title="監視停止サウンドファイルを選択",
            filetypes=[("WAV ファイル", "*.wav"), ("すべてのファイル", "*.*")],
        )
        if path:
            self._monitor_stop_sound_var.set(path)

    def _browse_monitor_resume_sound(self):
        path = filedialog.askopenfilename(
            title="監視再開サウンドファイルを選択",
            filetypes=[("WAV ファイル", "*.wav"), ("すべてのファイル", "*.*")],
        )
        if path:
            self._monitor_resume_sound_var.set(path)

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
            self._config["alert_interval_sec"] = self._read_int(
                self._interval_var, "alert_interval_sec", 5, 600)
            self._config["alert_sound_path"] = self._get_sound_path_value()
            self._config["pause_sound_enabled"] = self._pause_sound_enabled_var.get()
            self._config["pause_sound_path"] = self._get_pause_sound_path_value()
            self._config["monitor_stop_sound_enabled"] = self._monitor_stop_sound_enabled_var.get()
            self._config["monitor_stop_sound_path"] = self._get_monitor_stop_sound_path_value()
            self._config["monitor_resume_sound_enabled"] = self._monitor_resume_sound_enabled_var.get()
            self._config["monitor_resume_sound_path"] = self._get_monitor_resume_sound_path_value()
            self._config["alert_volume"] = self._read_int(self._volume_var, "alert_volume", 0, 100)
            self._config["theme"] = self._theme_var.get()
            self._config["auto_pause_enabled"] = self._auto_pause_enabled_var.get()
            self._config["auto_pause_alert_count"] = self._read_int(
                self._auto_pause_alert_count_var, "auto_pause_alert_count", 1, 10)
            self._config["idle_suspend_enabled"] = self._idle_suspend_enabled_var.get()
            self._config["idle_suspend_sec"] = self._read_int(
                self._idle_suspend_sec_var, "idle_suspend_sec", 30, 1800)
            self._config["mic_share_monitor_enabled"] = self._mic_share_monitor_enabled_var.get()

            self._on_config_save(self._config)

            apply_theme(self._root, self._config["theme"])
            resolved_theme = self._resolve_theme()
            colors = get_colors(resolved_theme)
            self._apply_visual_theme(resolved_theme)
            self._apply_graph_theme(resolved_theme)

            self._dirty = False
            # 保存のたびに文字列が変わらないと、2回目以降に保存されたのかが
            # 分からない。時刻を添えて更新されたことを見えるようにする。
            self._save_status_label.config(
                text=f"✓ {time.strftime('%H:%M:%S')} に保存しました",
                foreground=colors["success"],
            )
        finally:
            self._suspend_dirty = False

    def _selected_device_index(self) -> int | None:
        selected = self._device_var.get()
        matched = next((d for d in self._devices if d["name"] == selected), None)
        return matched["index"] if matched else self._config.get("device_index")

    def _toggle_monitor(self):
        if self._on_toggle_monitor is not None:
            self._on_toggle_monitor()
            self._monitor_btn_var.set("監視 停止" if self._monitoring_active() else "監視 開始")
        elif not self._monitor.is_running:
            self._monitor.start()
            self._monitor_btn_var.set("監視 停止")
        else:
            self._monitor.stop()
            self._monitor_btn_var.set("監視 開始")

    # -------------------------------------------------------------------------
    # 波形更新
    # -------------------------------------------------------------------------

    def _update_status(self) -> None:
        resolved_theme = self._config.get("theme", "system")
        if resolved_theme == "system":
            resolved_theme = get_system_theme()
        colors = get_colors(resolved_theme)

        # 自動停止は監視ボタンを押さずに起きるため、トグル時だけの更新では
        # 表示が実態とずれる。ポーリングのたびに合わせ直す。
        self._monitor_btn_var.set("監視 停止" if self._monitoring_active() else "監視 開始")

        if self._is_suspended is not None and self._is_suspended():
            self._status_label.config(
                text="⏸ 自動停止中（PC 無操作）", foreground=colors["warning"]
            )
            return

        if not self._monitor.is_running:
            self._status_label.config(text="○ 停止中", foreground=colors["secondary_label"])
            return

        db, zero_ratio = self._monitor.levels
        levels = f"   {db:.1f} dB / ゼロ率 {zero_ratio * 100:.0f}%"
        if self._monitor.is_paused:
            self._status_label.config(text="⏸ 一時停止中" + levels, foreground=colors["warning"])
        else:
            self._status_label.config(text="● 監視中" + levels, foreground=colors["success"])

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
        self._monitor_btn_var = None
        self._root.destroy()
