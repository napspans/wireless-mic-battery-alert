"""アプリのログ出力。

EXE は console=False でビルドするため標準出力の行き先がなく、そのままでは
記録がどこにも残らない。ファイルへ出す。

常駐して数秒ごとに巡回するアプリなので、素直に書くとログは際限なく増える。
次の3点で上限を設ける。

1. サイズで打ち切る（_MAX_BYTES × (_BACKUP_COUNT + 1) を超えない）
2. 直前と同じ内容の繰り返しを畳む
3. 既定は INFO。状態が変わったときだけ記録し、巡回のたびには書かない

音声コールバックは毎秒40回以上呼ばれる。ここからは絶対にログを出さないこと。
"""

import logging
import logging.handlers
import os
import sys

_LOG_DIR_NAME = "logs"
_LOG_FILE_NAME = "app.log"

# 1ファイル 512KB × 3世代。合計しても 1.5MB を超えない。
_MAX_BYTES = 512 * 1024
_BACKUP_COUNT = 2

# 自前のログ以外は警告以上だけ拾う。matplotlib や PIL は DEBUG が非常に多い。
_NOISY_LIBRARIES = ("matplotlib", "PIL", "comtypes", "numba", "asyncio")

_log_path: str | None = None


class _CollapseRepeats(logging.Filter):
    """直前と同じ内容の記録を畳む。

    再開の失敗のように巡回のたびに同じ失敗が続く場合、そのまま書くと同じ行で
    ログが埋まる。繰り返しは捨て、件数だけ次の行に添える。
    """

    def __init__(self) -> None:
        super().__init__()
        self._last: tuple | None = None
        self._skipped = 0

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            key = (record.name, record.levelno, record.getMessage())
        except Exception:
            return True

        if key == self._last:
            self._skipped += 1
            return False

        if self._skipped:
            record.msg = (
                f"{record.getMessage()}"
                f"（直前と同じ記録を {self._skipped} 件省略）"
            )
            record.args = ()
            self._skipped = 0

        self._last = key
        return True


def get_log_path() -> str | None:
    return _log_path


def setup(app_dir: str) -> str | None:
    """ファイルへのログ出力を用意し、ログファイルのパスを返す。

    書き込めない場所に置かれている可能性があるため、失敗してもアプリは
    起動させる。
    """
    global _log_path

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    log_dir = os.path.join(app_dir, _LOG_DIR_NAME)
    try:
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, _LOG_FILE_NAME)
        handler = logging.handlers.RotatingFileHandler(
            path,
            maxBytes=_MAX_BYTES,
            backupCount=_BACKUP_COUNT,
            encoding="utf-8",
        )
    except OSError:
        _log_path = None
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-7s %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        handler.addFilter(_CollapseRepeats())
        root.addHandler(handler)
        _log_path = path

    # スクリプト実行のときだけ画面にも出す。EXE では stderr が無い。
    if not getattr(sys, "frozen", False) and sys.stderr is not None:
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(levelname)-7s %(name)s: %(message)s"))
        root.addHandler(console)

    for name in _NOISY_LIBRARIES:
        logging.getLogger(name).setLevel(logging.WARNING)

    return _log_path


def set_debug(enabled: bool) -> None:
    """詳細ログの有無を切り替える。

    既定は INFO。設定で有効にしたときだけ DEBUG まで落とす。巡回ごとの
    記録が増えるため、常用は想定しない。
    """
    logging.getLogger().setLevel(logging.DEBUG if enabled else logging.INFO)
