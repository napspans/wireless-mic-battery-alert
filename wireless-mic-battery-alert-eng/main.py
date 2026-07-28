import logging
import sys
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox

import settings
from monitor import AudioMonitor
from notifier import Notifier
from tray import TrayIcon
from gui import SettingsGUI

logger = logging.getLogger(__name__)

class App:
    _ALERT_DISPLAY_SEC = 5.0

    def __init__(self):
        self._base_dir = settings.get_app_dir()
        self._config: dict = {}
        self._monitor: AudioMonitor = None
        self._tray: TrayIcon = None
        self._notifier: Notifier = None
        self._gui: SettingsGUI | None = None
        self._gui_lock = threading.Lock()
        self._gui_starting = False
        self._quit_event = threading.Event()
        self._last_alert_time: float = 0.0
        self._alert_lock = threading.Lock()
        self._sound_queue: queue.Queue = queue.Queue(maxsize=3)

    def _play(self, sound_path: str) -> None:
        """通知音を再生キューに積む。

        以前は再生ごとにスレッドを起こしていたため、アラート・一時停止・復帰が
        続けざまに起きると複数の音が同時に鳴って聞き分けられなかった。
        専用ワーカーで1つずつ順番に鳴らす。
        """
        if not sound_path.startswith("builtin:") and not sound_path.startswith("custom:"):
            sound_path = settings.resolve_app_path(sound_path)
        volume = self._config.get("alert_volume", 80)
        try:
            self._sound_queue.put_nowait((sound_path, volume))
        except queue.Full:
            # 状態が短時間に何度も変わった場合、古い音を鳴らし続けても意味がない
            logger.debug("通知音のキューが一杯のため破棄しました: %s", sound_path)

    def _sound_worker(self) -> None:
        while not self._quit_event.is_set():
            item = self._sound_queue.get()
            if item is None:
                break
            sound_path, volume = item
            try:
                self._notifier.play_sound(sound_path, volume)
            except Exception:
                logger.exception("通知音の再生に失敗しました: %s", sound_path)

    def _on_alert(self):
        with self._alert_lock:
            self._last_alert_time = time.monotonic()
        self._play(self._config.get("alert_sound_path", "builtin:error"))

    def _on_auto_pause(self):
        if not self._config.get("pause_sound_enabled", True):
            return
        self._play(self._config.get("pause_sound_path", "builtin:marimba"))

    def _on_auto_resume(self):
        if not self._config.get("pause_sound_enabled", True):
            return
        self._play(self._config.get("monitor_resume_sound_path", "builtin:notify_11"))

    def _on_config_save(self, new_config: dict):
        device_changed = new_config.get('device_index') != self._config.get('device_index')
        settings.save(new_config)
        self._config.update(new_config)
        if device_changed:
            self._monitor.stop()
            try:
                self._monitor.start()
            except Exception as exc:
                self._on_stream_error(str(exc))

    def _run_gui(self):
        gui = SettingsGUI(
            self._monitor,
            self._config,
            on_config_save=self._on_config_save,
            on_toggle_monitor=self._toggle_monitor,
        )
        with self._gui_lock:
            self._gui = gui
            self._gui_starting = False
        try:
            gui.run()
        finally:
            with self._gui_lock:
                self._gui = None

    def _open_settings(self):
        with self._gui_lock:
            if self._gui is not None:
                try:
                    self._gui._root.after(0, lambda: (self._gui._root.lift(), self._gui._root.focus_force()))
                    return
                except Exception:
                    self._gui = None
            if self._gui_starting:
                return
            self._gui_starting = True
            thread = threading.Thread(target=self._run_gui, daemon=False)

        thread.start()

    def _on_stream_error(self, error_message: str) -> None:
        logger.exception("Audio stream failed to start: %s", error_message)
        message = (
            "入力デバイスを開始できませんでした。\n\n"
            f"{error_message}\n\n"
            "設定画面を開くので、入力デバイスを再選択してください。"
        )

        with self._gui_lock:
            gui = self._gui

        if gui is not None:
            def show_dialog() -> None:
                try:
                    messagebox.showerror(
                        "入力デバイスエラー",
                        message,
                        parent=gui._root,
                    )
                finally:
                    self._open_settings()

            gui._root.after(0, show_dialog)
            return

        temp_root = tk.Tk()
        temp_root.withdraw()
        temp_root.attributes("-topmost", True)
        try:
            messagebox.showerror("入力デバイスエラー", message, parent=temp_root)
        finally:
            temp_root.destroy()

        self._open_settings()

    def _toggle_monitor(self):
        if self._monitor.is_running:
            self._monitor.stop()
            if self._config.get("monitor_stop_sound_enabled", True):
                self._play(self._config.get("monitor_stop_sound_path", "builtin:marimba"))
        else:
            try:
                self._monitor.start()
            except Exception as exc:
                self._on_stream_error(str(exc))
                return
            if self._config.get("monitor_resume_sound_enabled", True):
                self._play(self._config.get("monitor_resume_sound_path", "builtin:notify_11"))

    def _is_monitoring(self) -> bool:
        return self._monitor.is_running

    def _quit(self):
        self._monitor.stop()
        self._tray.stop()
        self._quit_event.set()
        os._exit(0)

    def _state_polling_loop(self):
        while not self._quit_event.is_set():
            if not self._monitor.is_running:
                state = "idle"
            elif self._monitor.is_paused:
                state = "paused"
            else:
                with self._alert_lock:
                    elapsed = time.monotonic() - self._last_alert_time
                if elapsed < self._ALERT_DISPLAY_SEC:
                    state = "alert"
                else:
                    state = "monitoring"
            self._tray.update_state(state)
            self._quit_event.wait(0.5)

    def run(self):
        self._config = settings.load()
        self._notifier = Notifier()
        self._monitor = AudioMonitor(
            self._config,
            on_alert=self._on_alert,
            on_auto_pause=self._on_auto_pause,
            on_auto_resume=self._on_auto_resume,
        )
        self._tray = TrayIcon(
            on_open_settings=self._open_settings,
            on_quit=self._quit,
            on_toggle_monitor=self._toggle_monitor,
            is_monitoring=self._is_monitoring,
        )

        try:
            self._monitor.start()
        except Exception as exc:
            self._on_stream_error(str(exc))
        self._tray.start()

        threading.Thread(target=self._sound_worker, daemon=True).start()
        threading.Thread(target=self._state_polling_loop, daemon=True).start()

        self._quit_event.wait()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    App().run()
