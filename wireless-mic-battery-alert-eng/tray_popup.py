"""トレイアイコンの左クリックで出す簡易ポップアップ。

Windows 11 の音量・電源のフライアウトに倣い、タスクバーの際に枠なしで出し、
他所をクリックしたら閉じる。設定画面を開くほどでもない確認（今監視して
いるか、どのデバイスか、信号が来ているか）と、監視の開始／停止をここで
済ませられるようにする。

UI スレッド（ui_host.py）からのみ呼ぶこと。
"""

import ctypes
import logging
import sys
import time
import tkinter as tk
import tkinter.ttk as ttk
from ctypes import wintypes

import sv_ttk

import i18n
import theme
import tray
from i18n import t
from monitor import DB_FLOOR

logger = logging.getLogger(__name__)

_WIDTH = 320
_PAD = 16
_MARGIN = 12  # タスクバーおよび画面端からの距離
_METER_HEIGHT = 6
_REFRESH_MS = 250
_FOCUS_POLL_MS = 120
# フォーカス喪失で閉じた直後のクリックは「閉じる」の意図とみなす。
# アイコンを押すとまずタスクバーにフォーカスが移ってポップアップが閉じ、
# その後にクリックが届くため、これが無いと閉じた瞬間に開き直してしまう。
_REOPEN_GUARD_SEC = 0.4


class _RECT(ctypes.Structure):
    _fields_ = [("left", wintypes.LONG), ("top", wintypes.LONG),
                ("right", wintypes.LONG), ("bottom", wintypes.LONG)]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", _RECT),
                ("rcWork", _RECT), ("dwFlags", wintypes.DWORD)]


def _cursor_and_monitor():
    """カーソル位置と、そのモニタの (全体, 作業領域) を返す。取れなければ None。"""
    if sys.platform != "win32":
        return None
    try:
        user32 = ctypes.windll.user32
        point = wintypes.POINT()
        if not user32.GetCursorPos(ctypes.byref(point)):
            return None
        user32.MonitorFromPoint.restype = wintypes.HMONITOR
        user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
        monitor = user32.MonitorFromPoint(point, 2)  # MONITOR_DEFAULTTONEAREST
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            return None
        return (point.x, point.y), info.rcMonitor, info.rcWork
    except Exception:
        logger.debug("カーソル位置を取得できませんでした", exc_info=True)
        return None


def compute_position(cursor, monitor, work, width, height, margin=_MARGIN):
    """ポップアップの左上座標を決める。

    タスクバーのある辺は、作業領域がモニタ全体より欠けている辺で判定する。
    自動で隠す設定では欠けが無いので、カーソルに最も近い辺とみなす。
    """
    cx, cy = cursor
    gaps = {
        "bottom": monitor.bottom - work.bottom,
        "top": work.top - monitor.top,
        "left": work.left - monitor.left,
        "right": monitor.right - work.right,
    }
    edge = max(gaps, key=gaps.get)
    if gaps[edge] <= 0:
        distances = {
            "bottom": monitor.bottom - cy,
            "top": cy - monitor.top,
            "left": cx - monitor.left,
            "right": monitor.right - cx,
        }
        edge = min(distances, key=distances.get)

    if edge == "bottom":
        x, y = cx - width // 2, work.bottom - height - margin
    elif edge == "top":
        x, y = cx - width // 2, work.top + margin
    elif edge == "left":
        x, y = work.left + margin, cy - height // 2
    else:
        x, y = work.right - width - margin, cy - height // 2

    x = max(work.left + margin, min(x, work.right - width - margin))
    y = max(work.top + margin, min(y, work.bottom - height - margin))
    return x, y


def _round_corners(hwnd: int) -> bool:
    """Windows 11 の角丸を適用する。未対応の OS では False を返す。"""
    if sys.platform != "win32":
        return False
    try:
        preference = ctypes.c_int(2)  # DWMWCP_ROUND
        result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), 33,  # DWMWA_WINDOW_CORNER_PREFERENCE
            ctypes.byref(preference), ctypes.sizeof(preference))
        return result == 0
    except Exception:
        return False


def _foreground_window() -> int | None:
    if sys.platform != "win32":
        return None
    try:
        return ctypes.windll.user32.GetForegroundWindow() or None
    except Exception:
        return None


def _set_foreground(hwnd: int) -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.user32.SetForegroundWindow(wintypes.HWND(hwnd))
    except Exception:
        pass


class TrayPopup:
    def __init__(self, root: tk.Misc, get_snapshot, on_toggle_monitor,
                 on_open_settings, get_theme):
        """
        get_snapshot: 現在の状態を dict で返す。キーは state / device /
            running / db / monitoring（監視の意図があるか）。
        get_theme: 設定上のテーマ名（system / light / dark）を返す。
        """
        self._root = root
        self._get_snapshot = get_snapshot
        self._on_toggle_monitor = on_toggle_monitor
        self._on_open_settings = on_open_settings
        self._get_theme = get_theme
        self._win: tk.Toplevel | None = None
        self._hwnd: int | None = None
        self._had_focus = False
        self._foreground_at_open: int | None = None
        self._closed_by_focus_at = 0.0
        # 予約中の after をループごとに1つだけ持つ。閉じるときに全て取り消す。
        self._after_ids: dict = {}

    @property
    def is_open(self) -> bool:
        return self._win is not None

    def toggle(self) -> None:
        if self.is_open:
            self.hide()
            return
        if time.monotonic() - self._closed_by_focus_at < _REOPEN_GUARD_SEC:
            return
        self.show()

    def show(self) -> None:
        if self.is_open:
            return
        resolved = theme.resolve_theme(self._get_theme())
        # sv_ttk はインタプリタ全体のテーマを切り替える。設定画面が開いて
        # いれば既に当たっているので、違うときだけ当て直す。
        if sv_ttk.get_theme() != resolved:
            theme.apply_theme(self._root, resolved, i18n.get_language())
        else:
            theme.init_fonts(self._root, i18n.get_language())
        self._colors = theme.get_colors(resolved)
        self._build()
        self._refresh()
        self._place()
        self._activate()

    def hide(self) -> None:
        for after_id in self._after_ids.values():
            try:
                self._root.after_cancel(after_id)
            except tk.TclError:
                pass
        self._after_ids = {}
        if self._win is not None:
            try:
                self._win.destroy()
            except tk.TclError:
                pass
        self._win = None
        self._hwnd = None

    # -------------------------------------------------------------------------
    # 構築
    # -------------------------------------------------------------------------

    def _label(self, parent, font, color_key="label", **kwargs) -> tk.Label:
        kwargs.setdefault("anchor", tk.W)
        return tk.Label(parent, font=font, background=self._colors["surface"],
                        foreground=self._colors[color_key],
                        justify=tk.LEFT, **kwargs)

    def _build(self) -> None:
        colors = self._colors
        win = tk.Toplevel(self._root)
        win.withdraw()
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.configure(background=colors["surface"])
        self._win = win

        body = tk.Frame(win, background=colors["surface"], padx=_PAD, pady=_PAD)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=1)
        self._body = body

        self._label(body, theme.FONTS["headline"], text=i18n.APP_NAME).grid(
            row=0, column=0, columnspan=2, sticky=tk.W)

        status_row = tk.Frame(body, background=colors["surface"])
        status_row.grid(row=1, column=0, columnspan=2, sticky=tk.W, pady=(6, 0))
        self._status_label = self._label(status_row, theme.FONTS["body"])
        self._status_label.pack(side=tk.LEFT)

        self._label(body, theme.FONTS["caption"], "secondary_label",
                    text=t("label.input_device")).grid(
            row=2, column=0, columnspan=2, sticky=tk.W, pady=(12, 0))
        self._device_label = self._label(body, theme.FONTS["body"],
                                         wraplength=_WIDTH - _PAD * 2)
        self._device_label.grid(row=3, column=0, columnspan=2, sticky=tk.W)

        self._label(body, theme.FONTS["caption"], "secondary_label",
                    text=t("popup.level")).grid(
            row=4, column=0, sticky=tk.W, pady=(12, 0))
        self._level_label = self._label(body, theme.FONTS["caption"],
                                        "secondary_label", anchor=tk.E)
        self._level_label.grid(row=4, column=1, sticky=tk.E, pady=(12, 0))

        self._meter = tk.Canvas(body, height=_METER_HEIGHT, highlightthickness=0,
                                background=colors["border"],
                                width=_WIDTH - _PAD * 2)
        self._meter.grid(row=5, column=0, columnspan=2, sticky=tk.EW, pady=(4, 0))
        self._meter_bar = self._meter.create_rectangle(0, 0, 0, _METER_HEIGHT,
                                                       width=0)

        ttk.Separator(body, orient=tk.HORIZONTAL).grid(
            row=6, column=0, columnspan=2, sticky=tk.EW, pady=(16, 12))

        buttons = tk.Frame(body, background=colors["surface"])
        buttons.grid(row=7, column=0, columnspan=2, sticky=tk.EW)
        buttons.columnconfigure(0, weight=1, uniform="b")
        buttons.columnconfigure(1, weight=1, uniform="b")
        self._monitor_btn = ttk.Button(buttons, style="Accent.TButton",
                                       command=self._toggle_monitor)
        self._monitor_btn.grid(row=0, column=0, sticky=tk.EW, padx=(0, 4))
        ttk.Button(buttons, text=t("popup.settings"),
                   command=self._open_settings).grid(
            row=0, column=1, sticky=tk.EW, padx=(4, 0))

        theme.apply_widget_fonts(win)
        win.bind("<Escape>", lambda e: self.hide())

    def _place(self) -> None:
        win = self._win
        win.update_idletasks()
        width = max(_WIDTH, win.winfo_reqwidth())
        height = win.winfo_reqheight()
        found = _cursor_and_monitor()
        if found is None:
            x = win.winfo_screenwidth() - width - _MARGIN
            y = win.winfo_screenheight() - height - 60
        else:
            cursor, monitor, work = found
            x, y = compute_position(cursor, monitor, work, width, height)
        win.geometry(f"{width}x{height}+{x}+{y}")

    def _activate(self) -> None:
        win = self._win
        win.deiconify()
        win.update_idletasks()
        try:
            self._hwnd = int(win.wm_frame(), 16)
        except (tk.TclError, ValueError):
            self._hwnd = None
        rounded = self._hwnd is not None and _round_corners(self._hwnd)
        # 角丸にできない環境では地の色と見分けが付かないので縁を付ける。
        win.configure(highlightthickness=0 if rounded else 1,
                      highlightbackground=self._colors["border"],
                      highlightcolor=self._colors["border"])

        self._foreground_at_open = _foreground_window()
        self._had_focus = False
        win.lift()
        win.focus_force()
        if self._hwnd is not None:
            _set_foreground(self._hwnd)
        self._schedule("focus", _FOCUS_POLL_MS, self._watch_focus)
        self._schedule("refresh", _REFRESH_MS, self._refresh_loop)

    def _schedule(self, name, ms, fn) -> None:
        self._after_ids[name] = self._root.after(ms, fn)

    # -------------------------------------------------------------------------
    # 更新
    # -------------------------------------------------------------------------

    def _refresh_loop(self) -> None:
        if not self.is_open:
            return
        try:
            self._refresh()
        except Exception:
            logger.exception("ポップアップの更新に失敗しました")
        self._schedule("refresh", _REFRESH_MS, self._refresh_loop)

    def _refresh(self) -> None:
        snap = self._get_snapshot()
        state = snap["state"]
        color = tray.state_color(state)
        self._status_label.config(text=tray.state_text(state), foreground=color)
        self._device_label.config(text=snap["device"])
        self._monitor_btn.config(
            text=t("button.monitor_stop") if snap["monitoring"]
            else t("button.monitor_start"))

        width = self._meter.winfo_width()
        if width <= 1:
            width = _WIDTH - _PAD * 2
        if snap["running"]:
            db = snap["db"]
            ratio = max(0.0, min(1.0, (db - DB_FLOOR) / -DB_FLOOR))
            self._level_label.config(text=f"{db:.1f} dB")
        else:
            ratio = 0.0
            self._level_label.config(text="—")
        self._meter.coords(self._meter_bar, 0, 0, int(width * ratio), _METER_HEIGHT)
        self._meter.itemconfigure(self._meter_bar, fill=color)

    def _watch_focus(self) -> None:
        """他所がアクティブになったら閉じる。

        枠なしのウィンドウは <FocusOut> が当てにならない（そもそもフォーカスを
        得られないことがある）ため、前面のウィンドウを直接見る。フォーカスを
        得られなかった場合も、開いたときと別のウィンドウが前面に来たら閉じる。
        """
        if not self.is_open:
            return
        foreground = _foreground_window()
        if foreground is not None and self._hwnd is not None:
            if foreground == self._hwnd:
                self._had_focus = True
            elif self._had_focus or foreground != self._foreground_at_open:
                self._closed_by_focus_at = time.monotonic()
                self.hide()
                return
        self._schedule("focus", _FOCUS_POLL_MS, self._watch_focus)

    # -------------------------------------------------------------------------
    # 操作
    # -------------------------------------------------------------------------

    def _toggle_monitor(self) -> None:
        self._on_toggle_monitor()
        if self.is_open:
            self._refresh()

    def _open_settings(self) -> None:
        self.hide()
        self._on_open_settings()
