import pystray
from PIL import Image, ImageDraw

import appicon
import i18n
from i18n import t

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

_ICON_CACHE: dict[str, Image.Image] = {}


def _create_icon_image(state: str = "idle") -> Image.Image:
    """状態色のトレイアイコン。図形はアプリアイコンと共通のマイクを使う。

    トレイは状態を色で示すので、電池のバッジは重ねない。
    """
    top, bottom = _ICON_GRADIENTS.get(state, _ICON_GRADIENTS["idle"])
    size = _SIZE * appicon.SUPERSAMPLE

    canvas = appicon.rounded_background(size, top, bottom)
    appicon.draw_microphone(ImageDraw.Draw(canvas), size)
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

        # ラベルは全て呼び出し時に評価する。文字列で固定すると、言語を
        # 切り替えてもメニューだけ元の言語のまま取り残される。
        items = [
            pystray.MenuItem(lambda item: t("tray.open_settings"),
                             lambda icon, item: self._on_open_settings(), default=True),
            pystray.MenuItem(
                lambda item: t("button.monitor_stop") if self._is_monitoring()
                else t("button.monitor_start"),
                lambda icon, item: self._on_toggle_monitor(),
            ),
        ]
        if on_open_config_location is not None:
            items.append(
                pystray.MenuItem(
                    lambda item: t("tray.open_config_location"),
                    lambda icon, item: self._on_open_config_location(),
                )
            )
        if on_open_log is not None:
            items.append(
                pystray.MenuItem(
                    lambda item: t("tray.open_log"),
                    lambda icon, item: self._on_open_log(),
                )
            )
        items += [
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda item: t("tray.quit"),
                             lambda icon, item: self._on_quit()),
        ]

        self._icon = pystray.Icon(
            name="mic_battery_alert",
            icon=get_icon_image("idle"),
            title=i18n.APP_NAME,
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

    def refresh_language(self) -> None:
        """言語切替をトレイのメニューに反映する。

        ラベルは呼び出し時に訳されるが、Windows は開くまで再評価しない。
        ツールチップはアプリ名（訳さない）なので入れ直す必要はない。
        """
        try:
            self._icon.update_menu()
        except Exception:
            # トレイがまだ動いていない場合は次に開いたときに反映される。
            pass
