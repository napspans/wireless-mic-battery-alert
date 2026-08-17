"""設定画面が構築でき、自動停止の表示に追随することを確認する。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
import settings
from gui import SettingsGUI
from monitor import DB_FLOOR

failures = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        failures.append(name)


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
        return -42.5, 0.0

    def get_db_history(self):
        return np.full(200, DB_FLOOR, dtype=np.float32)


state = {"suspended": False}
monitor = FakeMonitor()
saved = []

gui = SettingsGUI(
    monitor,
    settings.DEFAULT_CONFIG.copy(),
    on_config_save=saved.append,
    on_toggle_monitor=lambda: None,
    is_suspended=lambda: state["suspended"],
)
check("設定画面が例外なく構築できる", True)

# 新しい設定ウィジェットが存在し、既定値が入っている
check("無操作自動停止のチェックが既定でオン", gui._idle_suspend_enabled_var.get() is True)
check("無操作しきい値の既定が 180", gui._idle_suspend_sec_var.get() == 180)
check("他アプリ継続のチェックが既定でオン", gui._mic_share_monitor_enabled_var.get() is True)
check("バージョン表記が画面にある", "1.1.0" in gui._version_label.cget("text"),
      gui._version_label.cget("text"))

# 監視中の表示
gui._update_status()
check("監視中はボタンが「監視 停止」", gui._monitor_btn_var.get() == "監視 停止")
check("監視中のステータス表示", "監視中" in gui._status_label.cget("text"),
      gui._status_label.cget("text"))

# 自動停止に切り替わったときの追随
state["suspended"] = True
monitor.running = False
gui._update_status()
check("自動停止中もボタンは「監視 停止」のまま",
      gui._monitor_btn_var.get() == "監視 停止")
check("自動停止中のステータス表示",
      "自動停止中" in gui._status_label.cget("text"), gui._status_label.cget("text"))

# 手動停止と区別されること
state["suspended"] = False
gui._update_status()
check("手動停止ではボタンが「監視 開始」", gui._monitor_btn_var.get() == "監視 開始")
check("手動停止のステータス表示",
      "停止中" in gui._status_label.cget("text")
      and "自動" not in gui._status_label.cget("text"),
      gui._status_label.cget("text"))

# 保存で新キーが書き出されること
gui._idle_suspend_sec_var.set(240)
gui._mic_share_monitor_enabled_var.set(False)
gui._on_save()
check("保存が呼ばれた", len(saved) == 1)
cfg = saved[-1]
check("しきい値が保存される", cfg["idle_suspend_sec"] == 240, str(cfg.get("idle_suspend_sec")))
check("他アプリ継続の設定が保存される", cfg["mic_share_monitor_enabled"] is False)
check("alert_interval_sec が 10 で保存される", cfg["alert_interval_sec"] == 10)

# 範囲外入力のクランプ
gui._idle_suspend_sec_var.set(5000)
gui._on_save()
check("しきい値が上限にクランプされる", saved[-1]["idle_suspend_sec"] == 1800)
gui._idle_suspend_sec_var.set(1)
gui._on_save()
check("しきい値が下限にクランプされる", saved[-1]["idle_suspend_sec"] == 30)

# テーマ切り替えで新ラベルが壊れないこと
for name in ("dark", "light"):
    gui._theme_var.set(name)
    gui._on_save()
check("テーマ切り替えが例外なく通る", True)

gui._running = False
gui._root.destroy()

print()
if failures:
    print(f"{len(failures)} 件失敗: {failures}")
    sys.exit(1)
print("すべて成功")
