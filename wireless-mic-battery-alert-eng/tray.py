import pystray
from PIL import Image, ImageDraw

_ICON_COLORS = {
    "idle": "#808080",
    "monitoring": "#00CC44",
    "alert": "#FF2222",
    "snoozed": "#FFA500",
}


def _create_icon_image(state: str = "idle") -> Image.Image:
    color = _ICON_COLORS.get(state, _ICON_COLORS["idle"])
    img = Image.new("RGB", (64, 64), color="white")
    draw = ImageDraw.Draw(img)
    draw.ellipse([8, 8, 56, 56], fill=color)
    return img


class TrayIcon:
    def __init__(self, on_open_settings: callable, on_quit: callable,
                 on_toggle_monitor: callable, is_monitoring: callable):
        self._on_open_settings = on_open_settings
        self._on_quit = on_quit
        self._on_toggle_monitor = on_toggle_monitor
        self._is_monitoring = is_monitoring

        menu = pystray.Menu(
            pystray.MenuItem("設定を開く", lambda icon, item: self._on_open_settings(), default=True),
            pystray.MenuItem(
                lambda item: "監視 停止" if self._is_monitoring() else "監視 開始",
                lambda icon, item: self._on_toggle_monitor(),
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("終了", lambda icon, item: self._on_quit()),
        )
        self._icon = pystray.Icon(
            name="mic_battery_alert",
            icon=_create_icon_image("idle"),
            title="マイク電池切れ警告",
            menu=menu,
        )

    def start(self) -> None:
        self._icon.run_detached()

    def stop(self) -> None:
        self._icon.stop()

    def update_state(self, state: str) -> None:
        self._icon.icon = _create_icon_image(state)
