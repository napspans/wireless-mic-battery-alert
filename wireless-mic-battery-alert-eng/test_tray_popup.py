"""トレイのツールチップ・簡易ポップアップ・UI スレッドの一本化を確認する。"""
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

import i18n
import settings
import tray
import tray_popup
from gui import SettingsGUI
from monitor import DB_FLOOR
from tray_popup import TrayPopup, _RECT, compute_position
from ui_host import UIHost

failures = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        failures.append(name)


# ── ツールチップ ────────────────────────────────────────────────────
i18n.set_language("ja")
tip = tray.build_tooltip("monitoring", "RX-01")
check("ツールチップがアプリ名・状態・デバイスの3行",
      tip.split("\n") == [i18n.APP_NAME, i18n.t("status.monitoring"), "RX-01"], repr(tip))
check("信号途絶中の表示がある", "信号途絶" in tray.build_tooltip("alert", "x"))
long_tip = tray.build_tooltip("suspended", "マイク" * 100)
check("長いデバイス名でも上限に収まる", len(long_tip) <= tray.TOOLTIP_MAX, str(len(long_tip)))
check("詰めたことが分かる", long_tip.endswith("…"))
check("状態行は削られない", i18n.t("status.idle_suspended") in long_tip)
for language in i18n.LANGUAGES:
    i18n.set_language(language)
    for state in ("idle", "monitoring", "alert", "paused", "suspended"):
        text = tray.state_text(state)
        if text.startswith("status."):
            check(f"{language}/{state} の状態文言がある", False, text)
i18n.set_language("ja")


# ── 左クリックの割り当て ────────────────────────────────────────────
calls = []
icon = tray.TrayIcon(on_open_settings=lambda: calls.append("settings"),
                     on_quit=lambda: None, on_toggle_monitor=lambda: None,
                     is_monitoring=lambda: False,
                     on_activate=lambda: calls.append("popup"))
icon._icon()  # 左クリック相当（pystray は既定項目を呼ぶ）
check("左クリックでポップアップが呼ばれる", calls == ["popup"], str(calls))
visible = [str(item) for item in icon._icon.menu]
check("ポップアップの既定項目はメニューに出ない",
      i18n.APP_NAME not in visible, str(visible))
check("右クリックメニューに設定がある", i18n.t("tray.open_settings") in visible)

calls.clear()
legacy = tray.TrayIcon(on_open_settings=lambda: calls.append("settings"),
                       on_quit=lambda: None, on_toggle_monitor=lambda: None,
                       is_monitoring=lambda: False)
legacy._icon()
check("on_activate 無しなら従来どおり設定を開く", calls == ["settings"], str(calls))


# ── 表示位置 ────────────────────────────────────────────────────────
def rect(l, t, r, b):
    return _RECT(l, t, r, b)


mon = rect(0, 0, 1920, 1080)
x, y = compute_position((1800, 1060), mon, rect(0, 0, 1920, 1032), 320, 300)
check("下タスクバー: 作業領域の下端に沿う", y == 1032 - 300 - 12, f"{x},{y}")
check("下タスクバー: 右端からはみ出さない", x + 320 <= 1920 - 12, f"{x},{y}")
x, y = compute_position((500, 10), mon, rect(0, 48, 1920, 1080), 320, 300)
check("上タスクバー: 作業領域の上端に沿う", y == 48 + 12 and x == 500 - 160, f"{x},{y}")
x, y = compute_position((10, 600), mon, rect(48, 0, 1920, 1080), 320, 300)
check("左タスクバー", x == 48 + 12, f"{x},{y}")
x, y = compute_position((1910, 600), mon, rect(0, 0, 1872, 1080), 320, 300)
check("右タスクバー", x == 1872 - 320 - 12, f"{x},{y}")
x, y = compute_position((900, 1075), mon, rect(0, 0, 1920, 1080), 320, 300)
check("自動で隠す場合はカーソルに近い辺", y == 1080 - 300 - 12, f"{x},{y}")
sub = rect(-1920, 0, 0, 1080)
x, y = compute_position((-10, 1060), sub, rect(-1920, 0, 0, 1032), 320, 300)
check("左側のサブモニタでも画面内に収まる", -1920 <= x and x + 320 <= 0, f"{x},{y}")


# ── UI スレッド ─────────────────────────────────────────────────────
host = UIHost()
host.start()


def on_ui(fn, timeout=10):
    """UI スレッドで fn を実行し、結果を返す。"""
    box = {}
    done = threading.Event()

    def run():
        try:
            box["value"] = fn()
        except Exception as exc:
            box["error"] = exc
        finally:
            done.set()

    host.call(run)
    if not done.wait(timeout):
        raise TimeoutError("UI スレッドが応答しません")
    if "error" in box:
        raise box["error"]
    return box.get("value")


check("call は UI スレッドで実行される", on_ui(host.is_ui_thread) is True)
check("呼び出し元は UI スレッドではない", host.is_ui_thread() is False)
host.call(lambda: 1 / 0)
check("例外が起きても UI スレッドは止まらない", on_ui(lambda: "alive") == "alive")


class FakeMonitor:
    running = True
    paused = False

    @property
    def is_running(self):
        return self.running

    @property
    def is_paused(self):
        return self.paused

    @property
    def levels(self):
        return -30.0, 0.0

    @property
    def device_name(self):
        return "RX-01"

    def get_db_history(self):
        return np.full(200, DB_FLOOR, dtype=np.float32)


monitor = FakeMonitor()
snapshot = {"state": "monitoring", "device": "RX-01", "running": True,
            "db": -30.0, "monitoring": True}
events = []
popup = TrayPopup(host.root, get_snapshot=lambda: dict(snapshot),
                  on_toggle_monitor=lambda: events.append("toggle"),
                  on_open_settings=lambda: events.append("settings"),
                  get_theme=lambda: "dark")

for language in i18n.LANGUAGES:
    i18n.set_language(language)
    try:
        on_ui(popup.show)
        ok = on_ui(lambda: popup.is_open)
        check(f"{language} でポップアップが開く", ok)
        texts = on_ui(lambda: (popup._status_label.cget("text"),
                               popup._monitor_btn.cget("text"),
                               popup._device_label.cget("text")))
        check(f"{language} の状態表示", texts[0] == i18n.t("status.monitoring"), texts[0])
        check(f"{language} の監視ボタン", texts[1] == i18n.t("button.monitor_stop"), texts[1])
    except Exception as exc:
        check(f"{language} でポップアップが開く", False, repr(exc))
    finally:
        on_ui(popup.hide)
i18n.set_language("ja")

on_ui(popup.show)
geometry = on_ui(lambda: (popup._win.winfo_width(), popup._win.winfo_height()))
check("ポップアップに大きさがある", geometry[0] >= 300 and geometry[1] > 100, str(geometry))
check("枠なしで表示される", on_ui(lambda: bool(popup._win.overrideredirect())))

bar = on_ui(lambda: popup._meter.coords(popup._meter_bar))
check("レベルに応じてメーターが伸びる", bar[2] > 0, str(bar))

snapshot.update(state="idle", running=False, monitoring=False)
on_ui(popup._toggle_monitor)
check("監視ボタンで切替が呼ばれる", events == ["toggle"], str(events))
after = on_ui(lambda: (popup._status_label.cget("text"),
                       popup._monitor_btn.cget("text"),
                       popup._level_label.cget("text"),
                       popup._meter.coords(popup._meter_bar)))
check("切替後すぐに表示が追随する", after[0] == i18n.t("status.stopped"), after[0])
check("停止中は開始ボタン", after[1] == i18n.t("button.monitor_start"), after[1])
check("停止中はレベルを出さない", after[2] == "—" and after[3][2] == 0, str(after))

on_ui(popup._open_settings)
check("設定ボタンでポップアップが閉じる", on_ui(lambda: popup.is_open) is False)
check("設定ボタンで設定画面が呼ばれる", events[-1] == "settings", str(events))

# トグル: 開いていれば閉じる。フォーカス喪失で閉じた直後のクリックは開き直さない。
on_ui(popup.toggle)
check("トグルで開く", on_ui(lambda: popup.is_open))
on_ui(popup.toggle)
check("トグルで閉じる", on_ui(lambda: popup.is_open) is False)
popup._closed_by_focus_at = time.monotonic()
on_ui(popup.toggle)
check("フォーカス喪失で閉じた直後のクリックでは開かない", on_ui(lambda: popup.is_open) is False)
popup._closed_by_focus_at = 0.0

# フォーカス監視: 他のウィンドウが前面に来たら閉じる
on_ui(popup.show)
original = tray_popup._foreground_window
try:
    tray_popup._foreground_window = lambda: popup._hwnd
    on_ui(popup._watch_focus)
    check("自分が前面なら開いたまま", on_ui(lambda: popup.is_open))
    tray_popup._foreground_window = lambda: 0xDEAD
    on_ui(popup._watch_focus)
    check("他のウィンドウが前面に来たら閉じる", on_ui(lambda: popup.is_open) is False)
finally:
    tray_popup._foreground_window = original


# ── 設定画面を Toplevel として開く ───────────────────────────────────
closed = []
gui = on_ui(lambda: SettingsGUI(monitor, settings.DEFAULT_CONFIG.copy(),
                                on_config_save=lambda c: None,
                                on_toggle_monitor=lambda: None,
                                is_suspended=lambda: False,
                                master=host.root,
                                on_closed=lambda: closed.append(True)))
check("設定画面が UI スレッド上に構築できる", gui is not None)
check("設定画面はルートを所有しない", gui._owns_root is False)
on_ui(gui.bring_to_front)

# 設定画面を開いたままポップアップも開ける（同じインタプリタで共存する）
on_ui(popup.show)
check("設定画面と同時にポップアップを開ける", on_ui(lambda: popup.is_open))
on_ui(popup.hide)

on_ui(gui._on_close)
check("閉じると通知が来る", closed == [True])
check("ルートは生きている", on_ui(lambda: bool(host.root.winfo_exists())))

# 閉じたあと、もう一度開ける
gui2 = on_ui(lambda: SettingsGUI(monitor, settings.DEFAULT_CONFIG.copy(),
                                 on_config_save=lambda c: None,
                                 on_toggle_monitor=lambda: None,
                                 is_suspended=lambda: False,
                                 master=host.root))
check("設定画面を開き直せる", gui2 is not None)
on_ui(gui2._on_close)

# os._exit は標準出力を書き出さずに終わるため、先に流しておく。
print()
if failures:
    print(f"{len(failures)} 件失敗: {failures}")
    sys.stdout.flush()
    os._exit(1)
print("すべて成功")
sys.stdout.flush()
os._exit(0)
