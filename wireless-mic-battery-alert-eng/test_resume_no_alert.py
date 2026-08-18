"""無操作からの再開でアラートが鳴り直さないことを確認する。

送信機を切ったまま席を立ち、戻ってくる状況を再現する。
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import activity
import settings
from main import App
from monitor import AudioMonitor

failures = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        failures.append(name)


class FakeStream:
    def start(self): pass
    def stop(self): pass
    def close(self): pass


def make_monitor(config, on_alert, on_pause, on_resume):
    """実デバイスを使わずに AudioMonitor を動かす。"""
    m = AudioMonitor(config, on_alert=on_alert, on_auto_pause=on_pause,
                     on_auto_resume=on_resume)
    m._WARMUP_SEC = 0.05
    m._SIGNAL_LOST_SEC = 0.05
    m._SIGNAL_BACK_SEC = 0.05

    import threading
    def fake_start(preserve_state=False):
        m._stop_event.clear()
        if not preserve_state:
            m._alert_count = 0
            m._paused = False
        m._warmup_start = time.monotonic()
        m._stream = FakeStream()
        m._monitor_thread = threading.Thread(target=m._monitor_loop, daemon=True)
        m._monitor_thread.start()
    m.start = fake_start
    return m


def set_signal(m, lost: bool):
    with m._silence_lock:
        m._is_silent = lost


# 送信機OFF（デジタル無音）の状態で監視する
cfg = settings.DEFAULT_CONFIG.copy()
cfg["alert_interval_sec"] = 1

events = []
app = App()
app._config = cfg
app._monitor = make_monitor(
    cfg,
    on_alert=lambda: events.append("alert"),
    on_pause=lambda: events.append("pause"),
    on_resume=lambda: events.append("resume"),
)
app._play = lambda p: None

app._monitor.start()
app._monitor_desired = True
set_signal(app._monitor, True)   # 送信機OFF
time.sleep(0.6)

check("送信機OFFでアラートが鳴る", "alert" in events, str(events))
check("アラート後に自動一時停止する", app._monitor.is_paused is True)
first = list(events)

# 無操作 → 自動停止
activity.get_idle_seconds = lambda: 999
activity.other_app_using_mic = lambda: False
app._evaluate_idle_suspend()
check("無操作でストリームが閉じる", app._suspended is True and not app._monitor.is_running)

events.clear()
# 席に戻る → 自動再開（送信機は切ったまま）
activity.get_idle_seconds = lambda: 0
app._evaluate_idle_suspend()
check("操作再開で監視が戻る", app._suspended is False and app._monitor.is_running)
set_signal(app._monitor, True)
time.sleep(0.8)

check("再開後にアラートが鳴り直さない", "alert" not in events, str(events))
check("再開後に一時停止サウンドも鳴らない", "pause" not in events, str(events))
check("一時停止状態が引き継がれている", app._monitor.is_paused is True)

# 送信機を入れ直したら復帰する（回帰確認）
events.clear()
set_signal(app._monitor, False)
time.sleep(0.5)
check("信号が戻れば一時停止が解除される", app._monitor.is_paused is False)
check("復帰サウンドは鳴る", "resume" in events, str(events))

# --- スリープ復帰の再現 ---------------------------------------------------
# 復帰直後はデバイスの再開が遅く、最初のブロックが届くまで数秒かかる。
# start() は _is_silent=False で始まるため、その間「信号あり」に見える。
app._monitor.stop()
app._monitor._paused = True          # 送信機OFFで一時停止済みの状態
app._monitor._alert_count = 1
app._monitor._WARMUP_SEC = 1.0
events.clear()

app._monitor.start(preserve_state=True)
set_signal(app._monitor, False)      # デバイスがまだ何も返していない
time.sleep(0.6)                      # SIGNAL_BACK_SEC(0.05) は既に超えている
check("復帰直後の無反応を「信号が戻った」と誤認しない",
      app._monitor.is_paused is True and "resume" not in events, str(events))

set_signal(app._monitor, True)       # デバイスが動き出し、実際は無音だった
time.sleep(0.8)
check("その後アラートが鳴り直さない", "alert" not in events, str(events))
check("一時停止のままである", app._monitor.is_paused is True)
app._monitor.stop()
app._monitor._WARMUP_SEC = 0.05

# ウォームアップを抜けた後は、本当に信号が戻れば復帰する
app._monitor._paused = True
app._monitor.start(preserve_state=True)
time.sleep(0.2)
events.clear()
set_signal(app._monitor, False)
time.sleep(0.4)
check("ウォームアップ後は本物の復帰を拾う",
      app._monitor.is_paused is False and "resume" in events, str(events))
app._monitor.stop()

# 手動で開始した場合は従来どおりリセットされる
app._monitor.stop()
app._monitor._paused = True
app._monitor._alert_count = 5
app._monitor.start()
check("手動開始では状態がリセットされる",
      app._monitor.is_paused is False and app._monitor._alert_count == 0)
app._monitor.stop()

print()
if failures:
    print(f"{len(failures)} 件失敗: {failures}")
    sys.exit(1)
print("すべて成功")
