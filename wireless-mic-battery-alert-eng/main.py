import logging
import subprocess
import sys
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox

import activity
import settings
from monitor import AudioMonitor
from notifier import Notifier
from tray import TrayIcon
from gui import SettingsGUI

logger = logging.getLogger(__name__)

class App:
    _ALERT_DISPLAY_SEC = 5.0
    # 無操作判定の巡回間隔。しきい値は分単位なので細かく見る必要はない。
    _IDLE_POLL_SEC = 5.0
    # 通知音がこの秒数鳴らなければ、オーディオ出力デバイスを手放す。
    _MIXER_IDLE_SEC = 20.0

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
        # 監視の開始／停止はトレイ・GUI・無操作巡回の3系統から呼ばれる。
        # AudioMonitor.stop() はスレッド join を伴うため、重なると壊れる。
        self._monitor_lock = threading.RLock()
        # ユーザーが監視を望んでいるか。手動停止したのに無操作解除で勝手に
        # 復活しないよう、自動制御はこれが True のときだけ働く。
        self._monitor_desired = False
        # 無操作により自動停止中か。手動停止と区別するために持つ。
        self._suspended = False

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
            try:
                item = self._sound_queue.get(timeout=self._MIXER_IDLE_SEC)
            except queue.Empty:
                # 鳴らす予定がない間は出力デバイスを手放す。
                self._notifier.release()
                continue
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
        if not device_changed:
            return
        with self._monitor_lock:
            # 自動停止中は意図的に閉じている。ここで開き直すと電源要求が復活する。
            # 次の再開時に新しいデバイスで開かれるため何もしなくてよい。
            if not self._monitor.is_running:
                return
            self._monitor.stop()
            try:
                self._monitor.start()
            except Exception as exc:
                self._on_stream_error(str(exc))

    def _open_config_location(self) -> None:
        """設定ファイルをエクスプローラーで選択状態にして開く。"""
        config_path = settings.get_config_path()
        try:
            if os.path.exists(config_path):
                subprocess.Popen(["explorer", f"/select,{config_path}"])
            else:
                # 一度も保存していない場合はファイルが無いので、置き場所を開く。
                os.startfile(settings.get_app_dir())
        except Exception:
            logger.exception("設定ファイルの場所を開けませんでした: %s", config_path)

    def _run_gui(self):
        gui = SettingsGUI(
            self._monitor,
            self._config,
            on_config_save=self._on_config_save,
            on_toggle_monitor=self._toggle_monitor,
            is_suspended=self._is_suspended,
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
        """トレイ・GUI からの手動トグル。ユーザーの意図を更新する。"""
        sound = None
        with self._monitor_lock:
            if self._monitor.is_running or self._suspended:
                # 自動停止中はストリームが既に閉じているので停止処理は要らない。
                if self._monitor.is_running:
                    self._monitor.stop()
                self._suspended = False
                self._monitor_desired = False
                if self._config.get("monitor_stop_sound_enabled", True):
                    sound = self._config.get("monitor_stop_sound_path", "builtin:marimba")
            else:
                try:
                    self._monitor.start()
                except Exception as exc:
                    self._on_stream_error(str(exc))
                    return
                self._monitor_desired = True
                if self._config.get("monitor_resume_sound_enabled", True):
                    sound = self._config.get("monitor_resume_sound_path", "builtin:notify_11")

        if sound is not None:
            self._play(sound)

    def _suspend_monitor(self) -> None:
        """無操作を検知してキャプチャストリームを閉じる。

        開いたままだと USB オーディオドライバが SYSTEM 電源要求を立て続け、
        Windows がスリープに入らない。手動停止と区別するため通知音は鳴らさない。
        """
        with self._monitor_lock:
            if self._suspended or not self._monitor.is_running:
                return
            self._monitor.stop()
            self._suspended = True
        logger.info("PC が無操作のため監視を自動停止しました")

    def _resume_monitor(self) -> None:
        with self._monitor_lock:
            if not self._suspended:
                return
            try:
                # 一時停止していたなら、その状態のまま再開する
                self._monitor.start(preserve_state=True)
            except Exception:
                # スリープ復帰直後はデバイスが戻りきっていないことがある。
                # ダイアログを出さず、次の巡回で開き直す。
                logger.warning(
                    "監視の自動再開に失敗しました。次の巡回で再試行します", exc_info=True
                )
                return
            self._suspended = False
        logger.info("操作を検知したため監視を自動再開しました")

    def _evaluate_idle_suspend(self) -> None:
        if not self._monitor_desired:
            return
        if not self._config.get("idle_suspend_enabled", True):
            self._resume_monitor()
            return

        mic_shared = (
            self._config.get("mic_share_monitor_enabled", True)
            and activity.other_app_using_mic()
        )
        if activity.should_suspend(
            activity.get_idle_seconds(),
            self._config.get("idle_suspend_sec", 180),
            mic_shared,
        ):
            self._suspend_monitor()
        else:
            self._resume_monitor()

    def _idle_suspend_loop(self) -> None:
        while not self._quit_event.is_set():
            try:
                self._evaluate_idle_suspend()
            except Exception:
                logger.exception("無操作判定に失敗しました")
            self._quit_event.wait(self._IDLE_POLL_SEC)

    def _is_monitoring(self) -> bool:
        # 自動停止中も「監視する意図はある」ため、停止側のラベルを出す。
        return self._monitor.is_running or self._suspended

    def _is_suspended(self) -> bool:
        return self._suspended

    def _quit(self):
        self._monitor.stop()
        self._tray.stop()
        self._quit_event.set()
        os._exit(0)

    def _state_polling_loop(self):
        while not self._quit_event.is_set():
            if self._suspended:
                state = "suspended"
            elif not self._monitor.is_running:
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
            on_open_config_location=self._open_config_location,
        )

        try:
            self._monitor.start()
            self._monitor_desired = True
        except Exception as exc:
            self._on_stream_error(str(exc))
        self._tray.start()

        threading.Thread(target=self._sound_worker, daemon=True).start()
        threading.Thread(target=self._state_polling_loop, daemon=True).start()
        threading.Thread(target=self._idle_suspend_loop, daemon=True).start()

        self._quit_event.wait()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    logging.getLogger("matplotlib").setLevel(logging.WARNING)
    App().run()
