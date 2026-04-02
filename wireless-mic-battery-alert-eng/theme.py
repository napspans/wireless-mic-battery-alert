import tkinter.ttk as ttk

import sv_ttk

try:
    import winreg
    _WINREG_AVAILABLE = True
except ImportError:
    _WINREG_AVAILABLE = False

COLORS = {
    "light": {
        "bg": "#f5f5f7",
        "surface": "#ffffff",
        "border": "#d1d1d6",
        "label": "#1c1c1e",
        "secondary_label": "#6e6e73",
        "accent": "#0071e3",
        "success": "#34c759",
        "warning": "#ff9f0a",
    },
    "dark": {
        "bg": "#1c1c1e",
        "surface": "#2c2c2e",
        "border": "#38383a",
        "label": "#f2f2f7",
        "secondary_label": "#98989d",
        "accent": "#0071e3",
        "success": "#34c759",
        "warning": "#ff9f0a",
    },
}

FONTS = {
    "title": ("Meiryo UI", 13, "bold"),
    "headline": ("Meiryo UI", 11, "bold"),
    "body": ("Meiryo UI", 10),
    "caption": ("Meiryo UI", 9),
}


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


def apply_theme(root, theme: str) -> None:
    if theme == "system":
        theme = get_system_theme()
    sv_ttk.set_theme(theme)
    colors = get_colors(theme)
    style = ttk.Style()
    style.configure(".", font=FONTS["body"])
    style.configure("TFrame", background=colors["bg"])
    style.configure("TNotebook", background=colors["bg"])
    style.configure("TLabel", font=FONTS["body"])
    style.configure("TButton", font=FONTS["body"], padding=(12, 4))
    style.configure("TSpinbox", font=FONTS["body"])
    style.configure("TCombobox", font=FONTS["body"])
    style.configure("TCheckbutton", font=FONTS["body"])
    style.configure("TNotebook.Tab", font=FONTS["body"], padding=(12, 6))
    style.configure("TSeparator", background=colors["border"])
    root.option_add("*TCombobox*Listbox.font", FONTS["body"])
