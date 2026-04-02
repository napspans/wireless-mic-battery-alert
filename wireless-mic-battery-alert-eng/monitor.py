import threading
import time

import numpy as np
import sounddevice as sd


def list_input_devices() -> list[dict]:
    devices = sd.query_devices()
    hostapis = sd.query_hostapis()
    default_devices = sd.default.device
    default_input_index = None
    if default_devices is not None:
        default_input_index = default_devices[0]
        if default_input_index == -1:
            default_input_index = None

    wasapi_index = next(
        (i for i, hostapi in enumerate(hostapis) if "WASAPI" in hostapi["name"]),
        None,
    )

    result = []
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] <= 0:
            continue
        if wasapi_index is not None and dev["hostapi"] != wasapi_index:
            continue

        is_default = i == default_input_index
        name = dev["name"]
        if is_default:
            name = f"{name}（既定）"
        result.append({"index": i, "name": name, "is_default": is_default})
    return result


class AudioMonitor:
    _SAMPLERATE = 44100
    _CHANNELS = 1
    _BLOCKSIZE = 1024
    _BUFFER_SIZE = 44100  # 直近1秒分
    _DB_BUFFER_SIZE = 200  # 直近200サンプル分
    _WARMUP_SEC = 3  # 起動直後のウォームアップ期間（秒）

    def __init__(
        self,
        config: dict,
        on_alert: callable,
        on_snoozed: callable = None,
        on_snooze_resume: callable = None,
    ):
        self._config = config
        self._on_alert = on_alert
        self._on_snoozed = on_snoozed
        self._on_snooze_resume = on_snooze_resume

        self._waveform_buf = np.zeros(self._BUFFER_SIZE, dtype=np.float32)
        self._buf_lock = threading.Lock()

        self._db_buf = np.full(self._DB_BUFFER_SIZE, -120.0, dtype=np.float32)
        self._db_lock = threading.Lock()

        self._is_silent = False
        self._silent_since: float | None = None
        self._silence_lock = threading.Lock()

        self._warmup_start: float | None = None

        self._auto_snooze_count = 0
        self._snoozed = False
        self._resume_start: float | None = None

        self._stream: sd.InputStream | None = None
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        block = indata[:, 0].copy()

        with self._buf_lock:
            self._waveform_buf = np.roll(self._waveform_buf, -frames)
            self._waveform_buf[-frames:] = block

        rms = np.sqrt(np.mean(block ** 2))
        db = 20 * np.log10(rms + 1e-10)

        with self._db_lock:
            self._db_buf = np.roll(self._db_buf, -1)
            self._db_buf[-1] = db

        threshold = self._config.get("silence_threshold_db", -80.0)
        with self._silence_lock:
            self._is_silent = db < threshold

    def _monitor_loop(self):
        silence_start: float | None = None
        last_alert: float | None = None

        while not self._stop_event.is_set():
            now = time.monotonic()
            silence_duration_sec = self._config.get("silence_duration_sec", 5)
            alert_interval_sec = self._config.get("alert_interval_sec", 30)

            with self._silence_lock:
                is_silent = self._is_silent

            if is_silent:
                if silence_start is None:
                    silence_start = now
                self._resume_start = None
                elapsed = now - silence_start
                if elapsed >= silence_duration_sec:
                    if self._warmup_start is None or (now - self._warmup_start) < self._WARMUP_SEC:
                        pass  # ウォームアップ中はアラートをスキップ
                    elif not self._snoozed and (last_alert is None or (now - last_alert) >= alert_interval_sec):
                        last_alert = now
                        self._on_alert()
                        self._auto_snooze_count += 1
                        auto_snooze_enabled = self._config.get("auto_snooze_enabled", True)
                        snooze_limit = self._config.get("auto_snooze_alert_count", 2)
                        if auto_snooze_enabled and self._auto_snooze_count >= snooze_limit:
                            self._snoozed = True
                            if self._on_snoozed:
                                self._on_snoozed()
            else:
                silence_start = None
                # 音声検出時の自動復帰処理
                resume_sec = self._config.get("auto_snooze_resume_sec", 3)
                if self._resume_start is None:
                    self._resume_start = now
                if self._snoozed and (now - self._resume_start) >= resume_sec:
                    self._snoozed = False
                    self._auto_snooze_count = 0
                    self._resume_start = None
                    if self._on_snooze_resume:
                        self._on_snooze_resume()

            self._stop_event.wait(0.1)

    @property
    def is_running(self) -> bool:
        return self._stream is not None

    @property
    def is_snoozed(self) -> bool:
        return self._snoozed

    def start(self) -> None:
        self._stop_event.clear()
        self._auto_snooze_count = 0
        self._snoozed = False
        self._resume_start = None
        self._warmup_start = time.monotonic()

        device = self._config.get("device_index", None)
        device_info = sd.query_devices(device, kind="input")
        self._SAMPLERATE = int(device_info["default_samplerate"])
        self._CHANNELS = max(1, min(2, int(device_info["max_input_channels"])))
        self._BUFFER_SIZE = self._SAMPLERATE

        with self._buf_lock:
            self._waveform_buf = np.zeros(self._BUFFER_SIZE, dtype=np.float32)

        self._stream = sd.InputStream(
            device=device,
            channels=self._CHANNELS,
            samplerate=self._SAMPLERATE,
            blocksize=self._BLOCKSIZE,
            callback=self._audio_callback,
        )
        self._stream.start()

        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True
        )
        self._monitor_thread.start()

    def stop(self) -> None:
        self._stop_event.set()

        if self._monitor_thread is not None:
            self._monitor_thread.join()
            self._monitor_thread = None

        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def get_waveform(self) -> np.ndarray:
        with self._buf_lock:
            return self._waveform_buf.copy()

    def get_db_history(self) -> np.ndarray:
        with self._db_lock:
            return self._db_buf.copy()
