"""Tk を1本のスレッドに閉じ込める。

以前は設定画面を開くたびに新しいスレッドで `tk.Tk()` を作り、閉じたら
捨てていた。画面が1つしかないうちはそれで動いたが、トレイのポップアップと
設定画面が同時に存在すると、Tcl インタプリタが複数のスレッドにまたがる。
tkinter はこの状況に弱く、sv_ttk のように既定ルートを暗黙に参照する
ライブラリも混乱する。

そこで隠したルートを1つだけ常駐させ、画面は全てその `Toplevel` として作る。
他のスレッド（トレイ・監視・無操作巡回）からは `call()` で処理を渡し、
UI スレッド側で順に実行する。`root.after()` を他スレッドから呼ぶのは
tkinter の保証外なので、キューを UI スレッドから取りに行く形にしている。
"""

import logging
import queue
import threading
import tkinter as tk

logger = logging.getLogger(__name__)


class UIHost:
    # キューを見に行く間隔。クリックへの反応として体感できない程度に短くする。
    _POLL_MS = 30

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._ready = threading.Event()
        self._root: tk.Tk | None = None
        self._thread: threading.Thread | None = None

    @property
    def root(self) -> tk.Tk:
        """UI スレッドからのみ触ること。"""
        return self._root

    def start(self) -> None:
        # 終了は os._exit で行うため、daemon にしておいて差し支えない。
        self._thread = threading.Thread(target=self._run, name="ui", daemon=True)
        self._thread.start()
        self._ready.wait()

    def is_ui_thread(self) -> bool:
        return threading.current_thread() is self._thread

    def call(self, fn) -> None:
        """UI スレッドで `fn()` を実行するよう予約する。どのスレッドからでも呼べる。"""
        self._queue.put(fn)

    def _run(self) -> None:
        self._root = tk.Tk()
        # ルートは画面を持たない。見える画面は全て Toplevel として作る。
        self._root.withdraw()
        self._ready.set()
        self._root.after(self._POLL_MS, self._drain)
        self._root.mainloop()

    def _drain(self) -> None:
        while True:
            try:
                fn = self._queue.get_nowait()
            except queue.Empty:
                break
            try:
                fn()
            except Exception:
                logger.exception("UI 処理に失敗しました")
        self._root.after(self._POLL_MS, self._drain)
