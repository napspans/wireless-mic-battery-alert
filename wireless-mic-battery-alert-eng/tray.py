import pystray
from PIL import Image, ImageDraw

# 状態ごとの背景グラデーション (上, 下)。
_ICON_GRADIENTS = {
    "idle": ("#94A3B8", "#64748B"),
    "monitoring": ("#34D399", "#059669"),
    "alert": ("#FB7185", "#E11D48"),
    "paused": ("#FBBF24", "#D97706"),
    # 自動停止。監視する意図は残っているので、停止中とは別の色で示す。
    "suspended": ("#7DD3FC", "#0284C7"),
}

_SIZE = 64
# 一度大きく描いて縮小することで、PIL に無いアンチエイリアスを補う。
_SUPERSAMPLE = 4

_ICON_CACHE: dict[str, Image.Image] = {}


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _vertical_gradient(size: int, top: str, bottom: str) -> Image.Image:
    top_rgb = _hex_to_rgb(top)
    bottom_rgb = _hex_to_rgb(bottom)
    column = Image.new("RGB", (1, size))
    for y in range(size):
        ratio = y / (size - 1)
        column.putpixel(
            (0, y),
            tuple(
                round(a + (b - a) * ratio)
                for a, b in zip(top_rgb, bottom_rgb)
            ),
        )
    return column.resize((size, size))


def _draw_microphone(draw: ImageDraw.ImageDraw, size: int) -> None:
    white = (255, 255, 255, 255)
    center_x = size / 2
    stroke = max(1, round(size * 0.055))

    # 本体（カプセル）
    capsule_w = size * 0.26
    capsule_top = size * 0.19
    capsule_h = size * 0.38
    draw.rounded_rectangle(
        [
            center_x - capsule_w / 2,
            capsule_top,
            center_x + capsule_w / 2,
            capsule_top + capsule_h,
        ],
        radius=capsule_w / 2,
        fill=white,
    )

    # 受け（下半円のアーチ）
    arch_w = size * 0.46
    arch_top = size * 0.40
    arch_bottom = size * 0.70
    draw.arc(
        [center_x - arch_w / 2, arch_top, center_x + arch_w / 2, arch_bottom],
        start=0,
        end=180,
        fill=white,
        width=stroke,
    )

    # 支柱と台座
    draw.line(
        [center_x, arch_bottom - stroke / 2, center_x, size * 0.83],
        fill=white,
        width=stroke,
    )
    draw.line(
        [center_x - size * 0.14, size * 0.83, center_x + size * 0.14, size * 0.83],
        fill=white,
        width=stroke,
    )


def _create_icon_image(state: str = "idle") -> Image.Image:
    top, bottom = _ICON_GRADIENTS.get(state, _ICON_GRADIENTS["idle"])
    size = _SIZE * _SUPERSAMPLE

    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=round(size * 0.28), fill=255
    )
    canvas.paste(_vertical_gradient(size, top, bottom), (0, 0), mask)

    _draw_microphone(ImageDraw.Draw(canvas), size)
    return canvas.resize((_SIZE, _SIZE), Image.LANCZOS)


def get_icon_image(state: str = "idle") -> Image.Image:
    """状態に対応するアイコンを返す。

    状態表示は0.5秒ごとに更新されるため、そのつど描き直すと無駄が大きい。
    状態は数種類しかないのでキャッシュする。
    """
    if state not in _ICON_CACHE:
        _ICON_CACHE[state] = _create_icon_image(state)
    return _ICON_CACHE[state]


class TrayIcon:
    def __init__(self, on_open_settings: callable, on_quit: callable,
                 on_toggle_monitor: callable, is_monitoring: callable,
                 on_open_config_location: callable = None,
                 on_open_log: callable = None):
        self._on_open_settings = on_open_settings
        self._on_quit = on_quit
        self._on_toggle_monitor = on_toggle_monitor
        self._is_monitoring = is_monitoring
        self._on_open_config_location = on_open_config_location
        self._on_open_log = on_open_log
        self._state = "idle"

        items = [
            pystray.MenuItem("設定を開く", lambda icon, item: self._on_open_settings(), default=True),
            pystray.MenuItem(
                lambda item: "監視 停止" if self._is_monitoring() else "監視 開始",
                lambda icon, item: self._on_toggle_monitor(),
            ),
        ]
        if on_open_config_location is not None:
            items.append(
                pystray.MenuItem(
                    "設定ファイルの場所を開く",
                    lambda icon, item: self._on_open_config_location(),
                )
            )
        if on_open_log is not None:
            items.append(
                pystray.MenuItem(
                    "ログを開く",
                    lambda icon, item: self._on_open_log(),
                )
            )
        items += [
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("終了", lambda icon, item: self._on_quit()),
        ]

        self._icon = pystray.Icon(
            name="mic_battery_alert",
            icon=get_icon_image("idle"),
            title="マイク電池切れ警告",
            menu=pystray.Menu(*items),
        )

    def start(self) -> None:
        self._icon.run_detached()

    def stop(self) -> None:
        self._icon.stop()

    def update_state(self, state: str) -> None:
        if state == self._state:
            return
        self._state = state
        self._icon.icon = get_icon_image(state)
