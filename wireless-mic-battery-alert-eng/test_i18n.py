"""翻訳カタログの整合と、5言語での設定画面の構築を確認する。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

import i18n
import settings
import theme
from gui import SettingsGUI
from monitor import DB_FLOOR

failures = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        failures.append(name)


# ── カタログの整合 ─────────────────────────────────────────────────
reference = set(i18n._TRANSLATIONS[i18n.DEFAULT_LANGUAGE])
for language in i18n.LANGUAGES:
    keys = set(i18n._TRANSLATIONS[language])
    check(f"{language} のキーが日本語版と一致する",
          keys == reference,
          f"不足 {sorted(reference - keys)} 余分 {sorted(keys - reference)}")

check("言語名が全言語ぶん用意されている",
      all(lang in i18n.LANGUAGE_LABELS for lang in i18n.LANGUAGES))
check("フォント候補が全言語ぶん用意されている",
      all(i18n.font_families(lang) for lang in i18n.LANGUAGES))

# 書式引数を持つキーは、全言語で同じプレースホルダを含まなければ実行時に
# 表示が欠ける。ここで検出しておく。
_FORMAT_KEYS = {
    "device.default_suffix": "{name}",
    "status.levels": "{db}",
    "save.saved": "{time}",
    "error.device_body": "{error}",
}
for key, placeholder in _FORMAT_KEYS.items():
    missing = [lang for lang in i18n.LANGUAGES
               if placeholder not in i18n._TRANSLATIONS[lang][key]]
    check(f"{key} が全言語で {placeholder} を含む", not missing, str(missing))

# ── t() の頑健さ ────────────────────────────────────────────────────
i18n.set_language("ja")
check("未知のキーは例外にせずキーを返す", i18n.t("no.such.key") == "no.such.key")
check("書式引数が足りなくても例外にしない",
      isinstance(i18n.t("save.saved"), str))
i18n.set_language("xx")
check("未対応の言語は英語に落ちる", i18n.get_language() == "en")

# ── ロケール推定 ────────────────────────────────────────────────────
original_getdefaultlocale = i18n.locale.getdefaultlocale
try:
    for tag, expected in [("ja_JP", "ja"), ("en_US", "en"), ("ko_KR", "ko"),
                          ("zh_CN", "zh"), ("fr_FR", "fr"), ("xx_YY", "en")]:
        i18n.locale.getdefaultlocale = lambda t=tag: (t, "UTF-8")
        check(f"{tag} を {expected} と推定する",
              i18n.detect_system_language() == expected)
    i18n.locale.getdefaultlocale = lambda: (None, None)
    check("ロケール不明でも英語に落ちる", i18n.detect_system_language() == "en")
finally:
    i18n.locale.getdefaultlocale = original_getdefaultlocale


# ── 5言語での画面構築 ───────────────────────────────────────────────
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


for language in i18n.LANGUAGES:
    i18n.set_language(language)
    config = settings.DEFAULT_CONFIG.copy()
    config["language"] = language
    saved = []
    try:
        gui = SettingsGUI(FakeMonitor(), config, on_config_save=saved.append,
                          on_toggle_monitor=lambda: None,
                          is_suspended=lambda: False)
    except Exception as exc:
        check(f"{language} で画面が構築できる", False, repr(exc))
        continue
    check(f"{language} で画面が構築できる", True)
    check(f"{language} のタイトルがアプリ名＋訳語になる",
          gui._root.title() == i18n.settings_window_title(), gui._root.title())
    check(f"{language} でもアプリ名は訳さない",
          gui._root.title().startswith(i18n.APP_NAME), gui._root.title())
    check(f"{language} の通知音が言語ごとの表記になる",
          gui._alert_sound.combo.widget.cget("values")[0] == i18n.t("sound.builtin:chime"),
          str(gui._alert_sound.combo.widget.cget("values")[0]))
    expected_family = theme.pick_font_family(gui._root, language)
    check(f"{language} でフォントが解決できる", bool(expected_family), expected_family)

    # sv_ttk はテーマ適用時にウィジェットへ直接 `-font SunValleyBodyFont` を
    # 書き込む。ウィジェット側の指定はスタイルより強いため、名前付きフォントを
    # 差し替えないと Combobox や Entry だけ別のフォントで描かれる。実体の
    # "Segoe UI Variable Text" は CJK を持たず、既定フォントへ落ちてしまう。
    for widget_name, widget in [
        ("言語Combobox", gui._language_combo.widget),
        ("テーマCombobox", gui._theme_combo.widget),
        ("音量Entry", gui._volume_entry),
        ("間隔Spinbox", gui._interval_spinbox),
    ]:
        actual = gui._root.tk.call("font", "actual", widget.cget("font"), "-family")
        check(f"{language} の{widget_name}が本文と同じフォントを使う",
              actual == expected_family,
              f"実際={actual!r} 期待={expected_family!r}")

    gui._running = False
    gui._root.destroy()

# ── 言語切替が値を壊さないこと ──────────────────────────────────────
i18n.set_language("ja")
config = settings.DEFAULT_CONFIG.copy()
config["alert_sound_path"] = "builtin:marimba"
config["monitor_stop_sound_path"] = "custom:C:/sounds/mine.wav"
saved = []
gui = SettingsGUI(FakeMonitor(), config, on_config_save=saved.append,
                  on_toggle_monitor=lambda: None, is_suspended=lambda: False)

check("内蔵音がキーとして読み込まれる",
      gui._alert_sound.key_var.get() == "builtin:marimba",
      gui._alert_sound.key_var.get())
check("カスタム音のパスが復元される",
      gui._stop_sound.path_var.get() == "C:/sounds/mine.wav",
      gui._stop_sound.path_var.get())

before = gui._alert_sound.key_var.get()
gui._language_var.set("ko")
check("言語を変えても通知音のキーが変わらない",
      gui._alert_sound.key_var.get() == before, gui._alert_sound.key_var.get())
check("言語を変えると表示が訳し直される",
      gui._alert_sound.combo.widget.cget("values")[0] == i18n.t("sound.builtin:chime"),
      str(gui._alert_sound.combo.widget.cget("values")[0]))
check("言語を変えるとタブ名も訳し直される",
      i18n.get_language() == "ko")

gui._on_save()
check("選んだ言語が保存される", saved[-1]["language"] == "ko", str(saved[-1].get("language")))
check("保存後も通知音のパスが保たれる",
      saved[-1]["alert_sound_path"] == "builtin:marimba",
      saved[-1]["alert_sound_path"])
check("保存後もカスタム音のパスが保たれる",
      saved[-1]["monitor_stop_sound_path"] == "custom:C:/sounds/mine.wav",
      saved[-1]["monitor_stop_sound_path"])

# 壊れた値の自動補正が効いていること（過去のビルドが書いた "custom:builtin:" 形式）
gui._running = False
gui._root.destroy()

i18n.set_language("ja")
config = settings.DEFAULT_CONFIG.copy()
config["monitor_stop_sound_path"] = "custom:builtin:marimba"
gui = SettingsGUI(FakeMonitor(), config, on_config_save=lambda c: None,
                  on_toggle_monitor=lambda: None, is_suspended=lambda: False)
check("壊れたパスが内蔵音に補正される",
      gui._stop_sound.key_var.get() == "builtin:marimba",
      gui._stop_sound.key_var.get())
gui._running = False
gui._root.destroy()

print()
if failures:
    print(f"{len(failures)} 件失敗: {failures}")
    sys.exit(1)
print("すべて成功")
