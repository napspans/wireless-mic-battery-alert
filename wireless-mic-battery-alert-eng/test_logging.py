"""ログが肥大化しないことを確認する。"""
import logging
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import applog

failures = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        failures.append(name)


def reset_root():
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        h.close()


tmp = tempfile.mkdtemp(prefix="wmba_log_")
try:
    reset_root()
    path = applog.setup(tmp)
    check("ログファイルが用意される", path is not None and os.path.dirname(path).endswith("logs"), str(path))
    check("get_log_path が同じ場所を返す", applog.get_log_path() == path)

    log = logging.getLogger("test.size")

    # --- 重複の畳み込み ---
    for _ in range(500):
        log.info("再開に失敗しました")
    log.info("別の記録")
    for h in logging.getLogger().handlers:
        h.flush()
    text = open(path, encoding="utf-8").read()
    check("同じ記録が500件でも1件に畳まれる",
          text.count("再開に失敗しました") == 1, f"{text.count('再開に失敗しました')} 件")
    omitted = next((l for l in text.splitlines() if "省略" in l), "")
    check("省略件数が残る", "499 件省略" in text, omitted.strip()[-40:])

    # --- サイズ上限 ---
    for i in range(40000):
        log.info("状態が変わりました %d", i)   # 毎回異なる＝畳まれない
    for h in logging.getLogger().handlers:
        h.flush()

    log_dir = os.path.join(tmp, "logs")
    files = sorted(os.listdir(log_dir))
    total = sum(os.path.getsize(os.path.join(log_dir, f)) for f in files)
    check("世代数が上限内に収まる", len(files) <= 3, f"{len(files)} ファイル: {files}")
    check("合計サイズが 1.5MB を超えない",
          total <= 1.5 * 1024 * 1024 * 1.05, f"{total/1024:.0f} KB")

    # --- 既定は INFO、DEBUG は出さない ---
    before = os.path.getsize(path)
    log.debug("詳細な巡回ログ")
    for h in logging.getLogger().handlers:
        h.flush()
    check("既定では DEBUG を書かない", os.path.getsize(path) == before)

    applog.set_debug(True)
    log.debug("詳細な巡回ログ")
    for h in logging.getLogger().handlers:
        h.flush()
    check("設定を有効にすると DEBUG を書く", os.path.getsize(path) > before)

    applog.set_debug(False)
    check("無効に戻すと INFO に戻る",
          logging.getLogger().level == logging.INFO)

    # --- ライブラリのノイズを抑える ---
    check("matplotlib は WARNING 以上のみ",
          logging.getLogger("matplotlib").level == logging.WARNING)
    check("PIL は WARNING 以上のみ",
          logging.getLogger("PIL").level == logging.WARNING)

    # --- 書き込めない場所でも起動できる ---
    reset_root()
    bad = applog.setup(os.path.join(tmp, "logs", "app.log"))  # ファイルをディレクトリに使えない
    check("ログを置けなくても例外にしない", bad is None, str(bad))
finally:
    reset_root()
    shutil.rmtree(tmp, ignore_errors=True)

print()
if failures:
    print(f"{len(failures)} 件失敗: {failures}")
    sys.exit(1)
print("すべて成功")
