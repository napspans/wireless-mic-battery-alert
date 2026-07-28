import threading
import time

import numpy as np
import sounddevice as sd

# dB表示・計測の下限。無音時のRMSは0になりうるため、この値でクランプする。
DB_FLOOR = -160.0


def list_input_devices() -> list[dict]:
    devices = sd.query_devices()
    hostapis = sd.query_hostapis()

    # 既定入力デバイスは MME 等で登録されていることが多く、インデックスを
    # そのまま比較しても WASAPI 側とは一致しない。名前で突き合わせる。
    default_name = None
    default_devices = sd.default.device
    if default_devices is not None and default_devices[0] != -1:
        try:
            default_name = sd.query_devices(default_devices[0])["name"]
        except Exception:
            default_name = None

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

        is_default = default_name is not None and dev["name"] == default_name
        name = dev["name"]
        if is_default:
            name = f"{name}（既定）"
        result.append({"index": i, "name": name, "is_default": is_default})
    return result


def resolve_input_device(device_index: int | None) -> int | None:
    """未設定時に PortAudio 既定(MME等)へ落ちるのを防ぎ、一覧と同じ
    WASAPI デバイスを明示的に選ぶ。

    MME/DirectSound 経由では信号途絶時も 16bit の ±1LSB ディザが乗り、
    完全なデジタル無音にならないため、検出方式が成立しなくなる。
    """
    if device_index is not None:
        return device_index
    candidates = list_input_devices()
    if not candidates:
        return None
    default = next((d for d in candidates if d["is_default"]), None)
    return (default or candidates[0])["index"]


class AudioMonitor:
    _SAMPLERATE = 44100
    _CHANNELS = 1
    _BLOCKSIZE = 1024
    _DB_BUFFER_SIZE = 200  # 直近200サンプル分
    _WARMUP_SEC = 3  # 起動直後のウォームアップ期間（秒）
    # 無線の瞬断で鳴らさないための猶予。信号途絶は即座に判別できるので短くてよい。
    _SIGNAL_LOST_SEC = 1.0

    def __init__(
        self,
        config: dict,
        on_alert: callable,
        on_auto_pause: callable = None,
        on_auto_resume: callable = None,
    ):
        self._config = config
        self._on_alert = on_alert
        self._on_auto_pause = on_auto_pause
        self._on_auto_resume = on_auto_resume

        self._db_buf = np.full(self._DB_BUFFER_SIZE, DB_FLOOR, dtype=np.float32)
        self._db_lock = threading.Lock()

        self._is_silent = False
        self._last_db: float = DB_FLOOR
        self._zero_ratio: float = 0.0
        self._silence_lock = threading.Lock()

        self._warmup_start: float | None = None

        self._alert_count = 0
        self._paused = False

        self._stream: sd.InputStream | None = None
        self._monitor_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        block = indata[:, 0]

        rms = np.sqrt(np.mean(block ** 2))
        db = max(float(20 * np.log10(rms + 1e-12)), DB_FLOOR)

        with self._db_lock:
            self._db_buf = np.roll(self._db_buf, -1)
            self._db_buf[-1] = db

        # 送信機からの信号が途絶えると受信機はデジタル無音（厳密に0のサンプル）を
        # 出力する。マイクが生きている限りゼロサンプルは現れないため、音量レベルに
        # 依存せず誤検知しない判定材料になる。
        zero_ratio = float(np.count_nonzero(block == 0.0)) / len(block) if len(block) else 0.0
        lost = zero_ratio >= self._config.get("digital_silence_ratio", 0.5)

        with self._silence_lock:
            self._is_silent = lost
            self._last_db = db
            self._zero_ratio = zero_ratio

    def _monitor_loop(self):
        silence_start: float | None = None
        last_alert: float | None = None

        while not self._stop_event.is_set():
            now = time.monotonic()
            alert_interval_sec = self._config.get("alert_interval_sec", 30)

            with self._silence_lock:
                is_silent = self._is_silent

            if is_silent:
                if silence_start is None:
                    silence_start = now
                if now - silence_start >= self._SIGNAL_LOST_SEC:
                    if self._warmup_start is None or (now - self._warmup_start) < self._WARMUP_SEC:
                        pass  # ウォームアップ中はアラートをスキップ
                    elif not self._paused and (last_alert is None or (now - last_alert) >= alert_interval_sec):
                        last_alert = now
                        self._on_alert()
                        self._alert_count += 1
                        limit = self._config.get("auto_pause_alert_count", 1)
                        if self._config.get("auto_pause_enabled", True) and self._alert_count >= limit:
                            self._paused = True
                            if self._on_auto_pause:
                                self._on_auto_pause()
            else:
                silence_start = None
                # 信号が戻った時点で復帰する。信号途絶は瞬時に判別できるため
                # 復帰を遅らせる必要がない。
                if self._paused:
                    self._paused = False
                    self._alert_count = 0
                    if self._on_auto_resume:
                        self._on_auto_resume()

            self._stop_event.wait(0.1)

    @property
    def is_running(self) -> bool:
        return self._stream is not None

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def levels(self) -> tuple[float, float]:
        """直近ブロックの (dB, ゼロサンプル率) を返す。"""
        with self._silence_lock:
            return self._last_db, self._zero_ratio

    def start(self) -> None:
        self._stop_event.clear()
        self._alert_count = 0
        self._paused = False
        self._warmup_start = time.monotonic()

        with self._silence_lock:
            self._is_silent = False
            self._last_db = DB_FLOOR
            self._zero_ratio = 0.0

        device = resolve_input_device(self._config.get("device_index", None))
        device_info = sd.query_devices(device, kind="input")
        self._SAMPLERATE = int(device_info["default_samplerate"])
        self._CHANNELS = max(1, min(2, int(device_info["max_input_channels"])))

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

    def get_db_history(self) -> np.ndarray:
        with self._db_lock:
            return self._db_buf.copy()
