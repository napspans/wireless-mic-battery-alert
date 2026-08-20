"""配色とフォントの一元管理。

## 配色を sv_ttk に合わせる理由

sv_ttk（Sun Valley）は画像スプライトで描かれるテーマで、チェックボックスの
インジケータやスライダーのトラフは PNG に焼き込まれている。スプライトは
sv_ttk 自身の背景色（dark: #1c1c1c / light: #fafafa）の上に置かれる前提で
描かれており、それ以外の色の上に載せると矩形の縁が浮いて見える。`ttk.Style`
で背景色を指定しても画像要素には効かない。

以前はカードを独自色（dark: #2c2c2e）で塗っていたため、この縁が見えていた。
そこで **地の色を sv_ttk と完全に一致させ**、カードの区切りは塗り分けではなく
1px のボーダーで付ける。`bg` と `surface` が同値なのは意図的で、どこに
ウィジェットを置いてもスプライトが馴染むことを保証している。

## 名前付きフォントを使う理由

言語ごとに使えるフォントが違う（韓国語に Meiryo UI を当てると豆腐になる）。
フォントを名前で参照しておけば、言語切替時にファミリを差し替えるだけで
全ウィジェットに波及する。option DB へも名前1語で渡せるため、タプルの
文字列変換に悩まされることもない。
"""

import tkinter as tk
import tkinter.font as tkfont
import tkinter.ttk as ttk

import sv_ttk

import i18n

try:
    import winreg
    _WINREG_AVAILABLE = True
except ImportError:
    _WINREG_AVAILABLE = False

COLORS = {
    "light": {
        # sv_ttk light の -bg と同値。カードもページも同じ地の色に置く。
        "bg": "#fafafa",
        "surface": "#fafafa",
        "border": "#e0e0e0",
        "label": "#1c1c1c",
        "secondary_label": "#616161",
        "accent": "#005fb8",
        "success": "#0f7b0f",
        "warning": "#9d5d00",
    },
    "dark": {
        # sv_ttk dark の -bg と同値。
        "bg": "#1c1c1c",
        "surface": "#1c1c1c",
        "border": "#333333",
        "label": "#fafafa",
        "secondary_label": "#a0a0a0",
        "accent": "#57c8ff",
        "success": "#6ccb5f",
        "warning": "#fdb022",
    },
}

# 選択中の項目の色は sv_ttk の -selbg / -selfg に揃える。
_SELECTION_BG = "#2f60d8"
_SELECTION_FG = "#ffffff"

# 値はフォントそのものではなく、名前付きフォントの「名前」。
FONTS = {
    "title": "AppTitle",
    "headline": "AppHeadline",
    "body": "AppBody",
    "caption": "AppCaption",
}

_FONT_SPECS = {
    "AppTitle": (13, "bold"),
    "AppHeadline": (11, "bold"),
    "AppBody": (10, "normal"),
    "AppCaption": (9, "normal"),
}

_FALLBACK_FAMILY = "Segoe UI"

# チェックボックスの文言の折り返し幅。設定値の列に収まる範囲。
CHECK_WRAP = 320

# `tkinter.font.Font` は破棄時に `font delete` を呼ぶ。名前付きフォントを
# 作って参照を手放すと、その場でフォントごと消えて Tk の既定フォント
# （ＭＳ Ｐゴシック）に戻ってしまう。`init_fonts()` は生成した Font の
# `delete_font` を False にしてこれを止めている。参照を保持する方式では、
# 2回目に `nametofont()` の戻り値で置き換えた時点で生成元が回収され、
# 同じ現象が起きた。

# sv_ttk が持ち込む名前付きフォント。sv.tcl はテーマ適用時にウィジェットを
# 走査して `-font SunValleyBodyFont` を **ウィジェット自身に** 書き込む。
# ウィジェット側の指定はスタイルより強いため、`style.configure` で AppBody を
# 指定しても Combobox・Entry・Spinbox には届かない。
#
# 実体は "Segoe UI Variable Text" で CJK の字を持たないため、日本語・韓国語・
# 中国語では Tk の既定フォント（ＭＳ Ｐゴシック等）へ落ち、ラベルだけ正しく
# 入力欄だけ別のフォント、という食い違いが起きる。名前付きフォント側を
# 差し替えることで、sv_ttk が触る全ウィジェットにまとめて効かせる。
_SV_FONT_NAMES = [
    "SunValleyCaptionFont",
    "SunValleyBodyFont",
    "SunValleyBodyStrongFont",
    "SunValleyBodyLargeFont",
    "SunValleySubtitleFont",
    "SunValleyTitleFont",
    "SunValleyTitleLargeFont",
    "SunValleyDisplayFont",
]

# sv_ttk 本来のファミリ。ラテン系の言語に戻したときに復元するため控えておく。
_sv_original_families: dict = {}


def get_system_theme() -> str:
    if not _WINREG_AVAILABLE:
        return "light"
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        winreg.CloseKey(key)
        return "light" if value == 1 else "dark"
    except OSError:
        return "light"


def get_colors(theme: str) -> dict:
    return COLORS["dark"] if theme == "dark" else COLORS["light"]


def resolve_theme(theme: str) -> str:
    return get_system_theme() if theme == "system" else theme


def pick_font_family(root, language: str = None) -> str:
    """その言語の候補のうち、この環境に実在する最初のファミリを返す。

    Tk はフォールバック連鎖を持たないため、存在しないファミリを指定すると
    黙って既定フォントに落ちる。候補を自前で順に確かめる。
    """
    try:
        installed = {name.lower() for name in tkfont.families(root)}
    except tk.TclError:
        return _FALLBACK_FAMILY
    for family in i18n.font_families(language):
        if family.lower() in installed:
            return family
    return _FALLBACK_FAMILY


def init_fonts(root, language: str = None) -> str:
    """名前付きフォントを用意（または更新）し、採用したファミリを返す。

    ウィジェット生成より前に呼ぶこと。生成時に名前が未定義だと Tk が既定
    フォントに落ち、あとから定義しても遡って適用されない。
    """
    family = pick_font_family(root, language)
    for name, (size, weight) in _FONT_SPECS.items():
        try:
            font = tkfont.nametofont(name, root=root)
        except tk.TclError:
            font = tkfont.Font(root=root, name=name, family=family, size=size,
                               weight=weight, exists=False)
        # 名前付きフォントはインタプリタと寿命を共にすべきもの。Python 側の
        # 参照が切れても消させない（下の注記を参照）。
        font.delete_font = False
        font.configure(family=family, size=size, weight=weight)
    _apply_family_to_sv_fonts(root, family)
    return family


def _apply_family_to_sv_fonts(root, family: str) -> None:
    """sv_ttk 側の名前付きフォントにも同じファミリを行き渡らせる。

    sv_ttk のテーマを当てる前は、これらのフォントがまだ存在しない。その場合は
    何もせず、`apply_theme()` が `set_theme()` の後に呼び直すのに任せる。

    サイズは sv_ttk のもの（ピクセル指定）をそのまま残す。ウィジェットの
    寸法がそれ前提で組まれているため、ここで変えると余白が崩れる。
    """
    for name in _SV_FONT_NAMES:
        try:
            current = root.tk.call("font", "configure", name, "-family")
        except tk.TclError:
            continue
        original = _sv_original_families.setdefault(name, str(current))

        if family.startswith("Segoe UI Variable"):
            # ラテン系に戻ったので sv_ttk 本来の指定へ復帰する。太さは
            # ファミリ名（"... Semibold"）が担っているため normal に戻す。
            new_family, weight = original, "normal"
        else:
            # sv_ttk は太さをファミリ名で表している。日本語などのフォントには
            # 対応するファミリが無いので、weight で代用する。
            new_family = family
            weight = "bold" if "Semibold" in original else "normal"
        try:
            root.tk.call("font", "configure", name,
                         "-family", new_family, "-weight", weight)
        except tk.TclError:
            pass


def init_options(root, theme: str) -> None:
    """option DB 経由でしか色を渡せないウィジェットの既定値を入れる。

    Combobox のポップダウンは ttk ではなく素の Tk Listbox なので、テーマの
    配色が一切効かない。option DB はウィジェット生成時にしか読まれないため、
    生成より前に呼ぶ必要がある。生成後の追随は `style_popdown()` で行う。
    """
    colors = get_colors(resolve_theme(theme))
    root.option_add("*TCombobox*Listbox.font", FONTS["body"])
    root.option_add("*TCombobox*Listbox.background", colors["surface"])
    root.option_add("*TCombobox*Listbox.foreground", colors["label"])
    root.option_add("*TCombobox*Listbox.selectBackground", _SELECTION_BG)
    root.option_add("*TCombobox*Listbox.selectForeground", _SELECTION_FG)
    root.option_add("*TCombobox*Listbox.borderWidth", 0)
    root.option_add("*TCombobox*Listbox.highlightThickness", 0)


def style_popdown(combobox, theme: str) -> None:
    """既に作られている Combobox のポップダウンに配色を反映する。

    option DB は生成時にしか読まれないため、テーマや言語を切り替えたあとは
    実体を直接叩くしかない。Tk の内部ウィジェット名を引いて configure する。
    """
    colors = get_colors(resolve_theme(theme))
    try:
        popdown = combobox.tk.eval(f"ttk::combobox::PopdownWindow {combobox}")
        combobox.tk.call(
            f"{popdown}.f.l", "configure",
            "-font", FONTS["body"],
            "-background", colors["surface"],
            "-foreground", colors["label"],
            "-selectbackground", _SELECTION_BG,
            "-selectforeground", _SELECTION_FG,
            "-borderwidth", 0,
            "-highlightthickness", 0,
        )
        combobox.tk.call(
            f"{popdown}.f", "configure",
            "-background", colors["border"],
            "-borderwidth", 1,
        )
    except tk.TclError:
        # ポップダウンが未生成の状況では option DB の既定に任せる。
        pass


# `-font` を自前で持つ ttk ウィジェット。
_FONT_BEARING_CLASSES = {"TCombobox", "TEntry", "TSpinbox"}


def _iter_widgets(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _iter_widgets(child)


def apply_widget_fonts(root) -> None:
    """入力系ウィジェットに本文フォントを直接指定する。

    ttk の Combobox / Entry / Spinbox は自前の `-font` を持ち、既定は Tk の
    `TkTextFont`。ウィジェット側の指定はスタイルより強いため、
    `style.configure("TCombobox", font=...)` は届かない。

    さらに sv_ttk の `config_entry_font`（sv.tcl）が、生成時にテーマが
    sun-valley であれば `-font SunValleyBodyFont` を書き込んでくる。つまり
    どのフォントになるかは「ウィジェット生成」と「テーマ適用」の順序で
    変わる。どちらに転んでも `TkTextFont` も `SunValleyBodyFont` も日本語
    環境のファミリのままで、韓国語・中国語では字が出ない。

    順序に依存しないよう、テーマを当て終えたあとに明示的に上書きする。
    """
    for widget in _iter_widgets(root):
        if widget.winfo_class() not in _FONT_BEARING_CLASSES:
            continue
        try:
            widget.configure(font=FONTS["body"])
        except tk.TclError:
            pass


def apply_theme(root, theme: str, language: str = None) -> None:
    theme = resolve_theme(theme)
    sv_ttk.set_theme(theme)
    colors = get_colors(theme)
    init_fonts(root, language)
    init_options(root, theme)

    style = ttk.Style()
    style.configure(".", font=FONTS["body"])
    style.configure("TFrame", background=colors["bg"])
    style.configure("TNotebook", background=colors["bg"], borderwidth=0)
    # ttk.Label はページ地の上にしか置いていない（カード内は tk.Label）。
    style.configure("TLabel", font=FONTS["body"], background=colors["bg"])
    style.configure("TButton", font=FONTS["body"], padding=(12, 4))
    style.configure("TSpinbox", font=FONTS["body"])
    style.configure("TCombobox", font=FONTS["body"])
    style.configure("TEntry", font=FONTS["body"])
    # チェックボックスの文言も言語によっては1行に収まらない。ttk の
    # Checkbutton は `-wraplength` を持たないが、ラベル要素はスタイル経由の
    # 指定を受け付ける。収まる文には影響しない。
    style.configure("TCheckbutton", font=FONTS["body"], background=colors["bg"],
                    wraplength=CHECK_WRAP)
    style.configure("TNotebook.Tab", font=FONTS["body"], padding=(12, 6))
    style.configure("TSeparator", background=colors["border"])

    # スタイルでは届かないウィジェットを最後に揃える。sv_ttk のテーマ適用で
    # 書き換えられるため、必ず set_theme のあとに呼ぶこと。
    apply_widget_fonts(root)
