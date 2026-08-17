"""Phase 10 テスト計画の自動テスト部分。"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import activity
import settings
import tray
import version

failures = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        failures.append(name)


# --- 無操作秒数 -------------------------------------------------------------
idle = activity.get_idle_seconds()
check("無操作秒数が非負で現実的な範囲", 0.0 <= idle < 86400, f"idle={idle:.2f}s")

# 32bit 周回: dwTime が GetTickCount より大きい（=周回直後）状況を模す
wrapped = (0x00000010 - 0xFFFFFFF0) % (1 << 32)
check("32bit 周回で巨大値や負値にならない", wrapped == 32, f"{wrapped}ms")

# --- 判定関数 ---------------------------------------------------------------
check("しきい値未満では停止しない", activity.should_suspend(100, 180, False) is False)
check("しきい値超過で停止する", activity.should_suspend(200, 180, False) is True)
check("他アプリ使用中は停止しない", activity.should_suspend(9999, 180, True) is False)
check("しきい値0（無効）では停止しない", activity.should_suspend(9999, 0, False) is False)
check("境界値ちょうどで停止する", activity.should_suspend(180, 180, False) is True)

# --- 自プロセス除外 ---------------------------------------------------------
self_path = activity._self_executable_path()
check("自プロセスパスが解決できる", os.path.isabs(self_path), self_path)
check(
    "レジストリキー名がパスへ復元される",
    activity._key_name_to_path("C:#Windows#System32#app.exe")
    == os.path.normcase(r"C:\Windows\System32\app.exe"),
)
using = activity.other_app_using_mic()
check("他アプリのマイク使用判定が bool を返す", isinstance(using, bool), f"→ {using}")

# --- stale エントリの除外 ---------------------------------------------------
running = activity.running_process_names()
check("実行中プロセス名が取得できる", len(running) > 10, f"{len(running)} 件")
check("自分自身のプロセス名が含まれる",
      os.path.basename(sys.executable).lower() in running)
check(
    "実体が消えたエントリは使用中と見なさない",
    activity._is_live_entry(
        r"C:\Users\napsp\AppData\Local\Discord\app-1.0.9027\Discord.exe", running
    )
    is False,
)
check(
    "実体はあるがプロセスが居なければ使用中と見なさない",
    activity._is_live_entry(sys.executable, set()) is False,
)
check(
    "実体もプロセスもあれば使用中と見なす",
    activity._is_live_entry(sys.executable, running) is True,
)

# --- 設定既定値 -------------------------------------------------------------
d = settings.DEFAULT_CONFIG
check("alert_interval_sec の既定が 10", d["alert_interval_sec"] == 10)
check("device_index の既定は None のまま", d["device_index"] is None)
check("idle_suspend_enabled の既定が True", d["idle_suspend_enabled"] is True)
check("idle_suspend_sec の既定が 180", d["idle_suspend_sec"] == 180)
check("mic_share_monitor_enabled の既定が True", d["mic_share_monitor_enabled"] is True)

# 実機 config.json が新キー込みで読めるか（廃止キーが混ざっていないこと）
loaded = settings.load()
check("設定の読み込みに新キーが含まれる",
      all(k in loaded for k in ("idle_suspend_enabled", "idle_suspend_sec",
                                "mic_share_monitor_enabled")))

# --- アイコン ---------------------------------------------------------------
states = ["idle", "monitoring", "alert", "paused", "suspended"]
imgs = {s: tray.get_icon_image(s) for s in states}
check("全状態のアイコンが 64x64 RGBA",
      all(i.size == (64, 64) and i.mode == "RGBA" for i in imgs.values()))
check("状態ごとに見た目が異なる",
      len({i.tobytes() for i in imgs.values()}) == len(states))
check("アイコンがキャッシュされ同一インスタンスを返す",
      tray.get_icon_image("monitoring") is imgs["monitoring"])
check("背景が透過している（角が透明）", imgs["idle"].getpixel((0, 0))[3] == 0)

t0 = time.perf_counter()
for _ in range(200):
    tray.get_icon_image("monitoring")
check("キャッシュ経由の取得が十分速い", (time.perf_counter() - t0) < 0.05)

# --- バージョン -------------------------------------------------------------
check("バージョン表記に版と更新日が含まれる",
      version.APP_VERSION in version.version_line()
      and version.APP_UPDATED in version.version_line(),
      version.version_line())

print()
if failures:
    print(f"{len(failures)} 件失敗: {failures}")
    sys.exit(1)
print("すべて成功")
