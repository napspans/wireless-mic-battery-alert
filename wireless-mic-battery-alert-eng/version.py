"""アプリのバージョン情報。

GUI の表示とリリース管理の単一の出どころ。バージョンを上げるときは
APP_VERSION と APP_UPDATED を必ず同時に更新する。

アプリ名は言語ごとに変わるため、ここでは持たない（`i18n` の `app.name`）。
"""

from i18n import t

APP_VERSION = "2.3.0"
# 最終バージョン更新日 (YYYY-MM-DD)
APP_UPDATED = "2026-08-21"


def version_line() -> str:
    """GUI 表示用の1行文字列を返す。"""
    return t("version.line", version=APP_VERSION, date=APP_UPDATED)
