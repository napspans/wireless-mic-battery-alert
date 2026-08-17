"""監視サスペンドの状態遷移テスト（実デバイスを使わない）。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import activity
import settings
from main import App

failures = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        failures.append(name)


class FakeMonitor:
    def __init__(self):
        self.running = False
        self.starts = 0
        self.stops = 0
        self.fail_start = False

    @property
    def is_running(self):
        return self.running

    @property
    def is_paused(self):
        return False

    def start(self):
        if self.fail_start:
            raise RuntimeError("device busy")
        self.running = True
        self.starts += 1

    def stop(self):
        self.running = False
        self.stops += 1


def make_app(idle, mic_shared=False):
    app = App()
    app._config = settings.DEFAULT_CONFIG.copy()
    app._monitor = FakeMonitor()
    app._sounds = []
    app._play = lambda path: app._sounds.append(path)
    activity.get_idle_seconds = lambda: idle
    activity.other_app_using_mic = lambda: mic_shared
    return app


def set_idle(value):
    activity.get_idle_seconds = lambda: value


# --- 1. 無操作で自動停止 ----------------------------------------------------
app = make_app(idle=0)
app._monitor.start()
app._monitor_desired = True

app._evaluate_idle_suspend()
check("操作直後は停止しない", app._monitor.running is True and app._suspended is False)

set_idle(200)
app._evaluate_idle_suspend()
check("しきい値超過でストリームを閉じる",
      app._monitor.running is False and app._suspended is True)
check("自動停止では通知音を鳴らさない", app._sounds == [], str(app._sounds))
check("トレイ状態が suspended になる", app._is_suspended() is True)
check("監視の意図は保持される", app._is_monitoring() is True)

# --- 2. 自動停止の継続 ------------------------------------------------------
before = app._monitor.stops
app._evaluate_idle_suspend()
check("停止中に stop を重ねて呼ばない", app._monitor.stops == before)

# --- 3. 操作再開で自動再開 --------------------------------------------------
set_idle(0)
app._evaluate_idle_suspend()
check("操作再開でストリームを開き直す",
      app._monitor.running is True and app._suspended is False)
check("自動再開でも通知音を鳴らさない", app._sounds == [], str(app._sounds))

before = app._monitor.starts
app._evaluate_idle_suspend()
check("再開済みで start を重ねて呼ばない", app._monitor.starts == before)

# --- 4. 手動停止の尊重 ------------------------------------------------------
app = make_app(idle=200)
app._monitor.start()
app._monitor_desired = True
app._evaluate_idle_suspend()
check("前提: 自動停止している", app._suspended is True)

app._toggle_monitor()
check("自動停止中の手動トグルは停止として扱う",
      app._suspended is False and app._monitor_desired is False)
check("手動停止では停止音を鳴らす",
      app._sounds == [settings.DEFAULT_CONFIG["monitor_stop_sound_path"]], str(app._sounds))

set_idle(0)
app._sounds.clear()
app._evaluate_idle_suspend()
check("手動停止後は操作を再開しても監視が復活しない",
      app._monitor.running is False and app._monitor.starts == 1)

app._toggle_monitor()
check("手動で再開できる",
      app._monitor.running is True and app._monitor_desired is True)
check("手動再開では再開音を鳴らす",
      app._sounds == [settings.DEFAULT_CONFIG["monitor_resume_sound_path"]], str(app._sounds))

# --- 5. 再開失敗のリトライ --------------------------------------------------
app = make_app(idle=200)
app._monitor.start()
app._monitor_desired = True
app._evaluate_idle_suspend()
app._monitor.fail_start = True
set_idle(0)
app._evaluate_idle_suspend()
check("再開に失敗しても自動停止状態を維持する",
      app._suspended is True and app._monitor.running is False)
app._monitor.fail_start = False
app._evaluate_idle_suspend()
check("次の巡回で再開に成功する",
      app._suspended is False and app._monitor.running is True)

# --- 6. 他アプリ使用中は継続（案2） -----------------------------------------
app = make_app(idle=9999, mic_shared=True)
app._monitor.start()
app._monitor_desired = True
app._evaluate_idle_suspend()
check("他アプリがマイク使用中は無操作でも止めない",
      app._monitor.running is True and app._suspended is False)

activity.other_app_using_mic = lambda: False
app._evaluate_idle_suspend()
check("他アプリが手放したら止める", app._suspended is True)

# --- 7. 機能を無効にした場合 ------------------------------------------------
app = make_app(idle=9999)
app._monitor.start()
app._monitor_desired = True
app._config["idle_suspend_enabled"] = False
app._evaluate_idle_suspend()
check("無効時は無操作でも止めない", app._monitor.running is True and app._suspended is False)

app._config["idle_suspend_enabled"] = True
app._evaluate_idle_suspend()
check("有効に戻すと止まる", app._suspended is True)
app._config["idle_suspend_enabled"] = False
app._evaluate_idle_suspend()
check("自動停止中に無効化したら再開する",
      app._suspended is False and app._monitor.running is True)

# --- 8. デバイス変更時 ------------------------------------------------------
app = make_app(idle=200)
app._monitor.start()
app._monitor_desired = True
app._evaluate_idle_suspend()
saved = {}
settings.save = lambda cfg: saved.update(cfg)
before = app._monitor.starts
app._on_config_save({**app._config, "device_index": 7})
check("自動停止中のデバイス変更でストリームを開き直さない",
      app._monitor.starts == before and app._monitor.running is False)
check("設定自体は保存される", saved.get("device_index") == 7)

print()
if failures:
    print(f"{len(failures)} 件失敗: {failures}")
    sys.exit(1)
print("すべて成功")
