"""アイコンの描画。

トレイアイコン（状態ごとに色が変わる）とアプリアイコン（ウィンドウと EXE）で
同じマイクの図形を使うため、描画の部品をここに集める。

アプリアイコンだけは電池のバッジを重ねる。トレイは状態を色で示すので図形は
マイクだけでよいが、タスクバーや EXE のアイコンは色に意味を持たせられない。
何をするアプリかは形で伝える必要がある。

`python appicon.py` で `assets/app.ico` を作り直せる。PyInstaller は
ビルド時に実体の .ico を要求するため、生成物はリポジトリに置いてある。
"""

import os

from PIL import Image, ImageDraw

# 一度大きく描いて縮小することで、PIL に無いアンチエイリアスを補う。
SUPERSAMPLE = 4

_WHITE = (255, 255, 255, 255)

# アプリアイコンの地色。トレイの状態色（緑・赤・橙など）とは別系統にして、
# 「状態」ではなく「アプリそのもの」を指していることが分かるようにする。
APP_GRADIENT = ("#6366F1", "#4338CA")

# 電池バッジの残量表示。電池切れを知らせるアプリなので、残量は赤で少なく。
_BATTERY_LOW = (251, 113, 133, 255)

# バッジの下敷き。地色より暗くしてマイクと分離する。
_BADGE_BACKDROP = (49, 46, 129, 255)

# Windows がタスクバー・エクスプローラ・Alt+Tab で使うサイズ。
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]

# 構図。調整しやすいよう定数にしてある。
MIC_SCALE = 0.82
MIC_DX = 0.09
MIC_DY = 0.08
BADGE_D = 0.40
BADGE_MARGIN = 0.03
# これ未満のサイズでは電池バッジを描かない。
BADGE_MIN_SIZE = 32


def hex_to_rgb(value: str) -> tuple:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def vertical_gradient(size: int, top: str, bottom: str) -> Image.Image:
    top_rgb = hex_to_rgb(top)
    bottom_rgb = hex_to_rgb(bottom)
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


def rounded_background(size: int, top: str, bottom: str) -> Image.Image:
    """角丸の四角にグラデーションを敷いた下地を返す。"""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=round(size * 0.28), fill=255
    )
    canvas.paste(vertical_gradient(size, top, bottom), (0, 0), mask)
    return canvas


def draw_microphone(draw: ImageDraw.ImageDraw, size: int, scale: float = 1.0,
                    dx: float = 0.0, dy: float = 0.0, color=_WHITE) -> None:
    """マイクを描く。

    `scale` と `dx` / `dy` は、電池バッジの居場所を空けるために使う。
    座標は仮想的な一辺 `s` の中で決め、最後に平行移動する。
    """
    s = size * scale
    ox = (size - s) / 2 + dx
    oy = (size - s) / 2 + dy
    center_x = ox + s / 2
    stroke = max(1, round(s * 0.055))

    # 本体（カプセル）
    capsule_w = s * 0.26
    capsule_top = oy + s * 0.19
    capsule_h = s * 0.38
    draw.rounded_rectangle(
        [
            center_x - capsule_w / 2,
            capsule_top,
            center_x + capsule_w / 2,
            capsule_top + capsule_h,
        ],
        # 半径が幅のちょうど半分だと、PIL 内部の「完全な丸」判定が浮動小数の
        # 誤差で転び、幅が負の矩形を描こうとして例外になる。半分より確実に
        # 大きくしておけば判定側で幅の半分に丸められる。見た目は変わらない。
        radius=capsule_w / 2 + 0.5,
        fill=color,
    )

    # 受け（下半円のアーチ）
    arch_w = s * 0.46
    arch_top = oy + s * 0.40
    arch_bottom = oy + s * 0.70
    draw.arc(
        [center_x - arch_w / 2, arch_top, center_x + arch_w / 2, arch_bottom],
        start=0,
        end=180,
        fill=color,
        width=stroke,
    )

    # 支柱と台座
    draw.line(
        [center_x, arch_bottom - stroke / 2, center_x, oy + s * 0.83],
        fill=color,
        width=stroke,
    )
    draw.line(
        [center_x - s * 0.14, oy + s * 0.83, center_x + s * 0.14, oy + s * 0.83],
        fill=color,
        width=stroke,
    )


def draw_battery_badge(canvas: Image.Image, size: int, diameter: float = 0.44,
                       margin: float = 0.03) -> None:
    """右下に電池のバッジを重ねる。

    地色の上に白い電池を直に置くとマイクと繋がって見えるため、いったん
    地色を丸く抜いてから描く。小さいサイズでも2つの図形として分かれる。
    """
    draw = ImageDraw.Draw(canvas)

    badge_d = size * diameter
    cx = size - badge_d / 2 - size * margin
    cy = size - badge_d / 2 - size * margin

    # 切り欠き（地色より少し暗いリング）でマイクと分離する
    draw.ellipse(
        [cx - badge_d / 2, cy - badge_d / 2, cx + badge_d / 2, cy + badge_d / 2],
        fill=_BADGE_BACKDROP,
    )

    body_w = badge_d * 0.60
    body_h = badge_d * 0.36
    nub_w = badge_d * 0.07
    nub_h = body_h * 0.42
    stroke = max(1, round(size * 0.022))
    radius = body_h * 0.28

    left = cx - (body_w + nub_w) / 2
    top = cy - body_h / 2
    right = left + body_w
    bottom = top + body_h

    draw.rounded_rectangle([left, top, right, bottom], radius=radius,
                           outline=_WHITE, width=stroke)
    # ツメは元々小さく、角を丸めようとすると幅が足りず PIL が例外を投げる。
    nub_box = [right + stroke, cy - nub_h / 2, right + nub_w, cy + nub_h / 2]
    nub_radius = nub_w * 0.4
    if nub_box[2] - nub_box[0] > nub_radius * 2 + 2:
        draw.rounded_rectangle(nub_box, radius=nub_radius, fill=_WHITE)
    else:
        draw.rectangle(nub_box, fill=_WHITE)

    # 残量はわずか。電池切れを知らせるアプリなので満充電では意味が通らない。
    pad = stroke * 1.8
    level_w = (body_w - pad * 2) * 0.28
    draw.rectangle(
        [left + pad, top + pad, left + pad + level_w, bottom - pad],
        fill=_BATTERY_LOW,
    )


def create_app_icon(size: int = 256) -> Image.Image:
    """ウィンドウと EXE 用のアイコンを返す。

    小さいサイズでは電池バッジを省く。16px に2つの図形を詰めると、どちらも
    輪郭が潰れて「何かの染み」にしかならない。マイク1つに絞ったほうが、
    小さくても何のアイコンか分かる。
    """
    work = size * SUPERSAMPLE
    canvas = rounded_background(work, *APP_GRADIENT)
    if size >= BADGE_MIN_SIZE:
        # 電池バッジの居場所を空けるため、マイクは少し小さく左上寄りに置く。
        draw_microphone(ImageDraw.Draw(canvas), work, scale=MIC_SCALE,
                        dx=-work * MIC_DX, dy=-work * MIC_DY)
        draw_battery_badge(canvas, work, BADGE_D, BADGE_MARGIN)
    else:
        draw_microphone(ImageDraw.Draw(canvas), work)
    return canvas.resize((size, size), Image.LANCZOS)


def write_app_ico(path: str) -> str:
    """複数サイズを束ねた .ico を書き出す。

    Windows は表示場所ごとに違うサイズを引く。1枚だけ入れて縮小させると
    小さい表示がぼやけるため、必要なサイズをそれぞれ描いて収める。
    """
    images = [create_app_icon(s) for s in ICO_SIZES]
    largest = images[-1]
    largest.save(path, format="ICO",
                 sizes=[(s, s) for s in ICO_SIZES],
                 append_images=images[:-1])
    return path


if __name__ == "__main__":
    target = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "assets", "app.ico")
    print("wrote", write_app_ico(target))
