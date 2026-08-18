"""アプリのバージョン情報。

GUI の表示とリリース管理の単一の出どころ。バージョンを上げるときは
APP_VERSION と APP_UPDATED を必ず同時に更新する。
"""

APP_NAME = "マイク電池切れ警告"
APP_VERSION = "2.1.1"
# 最終バージョン更新日 (YYYY-MM-DD)
APP_UPDATED = "2026-08-18"


def version_line() -> str:
    """GUI 表示用の1行文字列を返す。"""
    return f"v{APP_VERSION}（{APP_UPDATED} 更新）"
