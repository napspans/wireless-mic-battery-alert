"""Windows からユーザー操作とマイク使用状況を問い合わせる。

常駐監視のためにキャプチャストリームを開いたままにすると、USB オーディオ
ドライバが Windows に SYSTEM 電源要求を立て続け、スリープに入らなくなる
(Issue #1)。ストリームを閉じてよいタイミングを判断する材料をここで集める。

アプリ自身は SetThreadExecutionState を呼んでいないため、電源要求は
powercfg /requests にプロセスではなく [DRIVER] USB Audio Device として現れる。
つまりプロセス側から要求を取り下げる手段はなく、ストリームを閉じるしかない。
"""

import ctypes
import logging
import os
import sys
from ctypes import wintypes

logger = logging.getLogger(__name__)

_IS_WINDOWS = sys.platform == "win32"

# GetTickCount は DWORD を返し、約49.7日で一周する。
_DWORD_WRAP = 1 << 32


_MAX_PATH = 260
_TH32CS_SNAPPROCESS = 0x00000002


class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("dwTime", wintypes.DWORD),
    ]


class _PROCESSENTRY32(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_char * _MAX_PATH),
    ]


if _IS_WINDOWS:
    import winreg

    _user32 = ctypes.windll.user32
    _kernel32 = ctypes.windll.kernel32
    _user32.GetLastInputInfo.argtypes = [ctypes.POINTER(_LASTINPUTINFO)]
    _user32.GetLastInputInfo.restype = wintypes.BOOL
    # 既定の restype は符号付き int のため、約24.8日を超えると負値になる。
    _kernel32.GetTickCount.restype = wintypes.DWORD
    _kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    _kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    _kernel32.Process32First.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32)]
    _kernel32.Process32First.restype = wintypes.BOOL
    _kernel32.Process32Next.argtypes = [wintypes.HANDLE, ctypes.POINTER(_PROCESSENTRY32)]
    _kernel32.Process32Next.restype = wintypes.BOOL
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

_INVALID_HANDLE = ctypes.c_void_p(-1).value


def running_process_names() -> set[str]:
    """実行中プロセスの実行ファイル名（小文字）を返す。取得失敗時は空集合。"""
    names: set[str] = set()
    if not _IS_WINDOWS:
        return names

    snapshot = _kernel32.CreateToolhelp32Snapshot(_TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == _INVALID_HANDLE:
        return names
    try:
        entry = _PROCESSENTRY32()
        entry.dwSize = ctypes.sizeof(entry)
        ok = _kernel32.Process32First(snapshot, ctypes.byref(entry))
        while ok:
            names.add(entry.szExeFile.decode("mbcs", "ignore").lower())
            ok = _kernel32.Process32Next(snapshot, ctypes.byref(entry))
    except OSError:
        logger.debug("プロセス一覧の取得に失敗しました", exc_info=True)
    finally:
        _kernel32.CloseHandle(snapshot)
    return names


def get_idle_seconds() -> float:
    """最後のキーボード／マウス操作からの経過秒数を返す。

    取得に失敗した場合は 0.0（＝操作直後）を返す。判定できないときに
    監視を止めてしまうより、続ける側に倒す。
    """
    if not _IS_WINDOWS:
        return 0.0

    info = _LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    try:
        if not _user32.GetLastInputInfo(ctypes.byref(info)):
            return 0.0
        # DWORD 同士の差を 32bit で丸めることで、周回をまたいでも正しい値になる。
        elapsed_ms = (_kernel32.GetTickCount() - info.dwTime) % _DWORD_WRAP
    except OSError:
        logger.debug("GetLastInputInfo に失敗しました", exc_info=True)
        return 0.0
    return elapsed_ms / 1000.0


# 各アプリのマイク使用状況。LastUsedTimeStop == 0 が「使用中」を意味する。
_MIC_CONSENT_KEY = (
    r"SOFTWARE\Microsoft\Windows\CurrentVersion"
    r"\CapabilityAccessManager\ConsentStore\microphone"
)
# ストアアプリ以外はこのサブキー配下に、パス区切りを # に置換した名前で並ぶ。
_NONPACKAGED = "NonPackaged"


def _self_executable_path() -> str:
    return os.path.normcase(os.path.abspath(sys.executable))


def _key_name_to_path(name: str) -> str:
    return os.path.normcase(name.replace("#", "\\"))


def _is_in_use(key) -> bool:
    try:
        stop, _ = winreg.QueryValueEx(key, "LastUsedTimeStop")
    except OSError:
        return False
    return stop == 0


def _subkey_names(key) -> list[str]:
    names = []
    index = 0
    while True:
        try:
            names.append(winreg.EnumKey(key, index))
        except OSError:
            break
        index += 1
    return names


def _is_live_entry(exe_path: str, running: set[str]) -> bool:
    """ConsentStore の「使用中」が現に生きているアプリのものかを確かめる。

    アプリが停止時刻を書かずに終了すると LastUsedTimeStop は 0 のまま残る。
    実測では、アンインストール済みの旧バージョンの Discord が3件、数年前の
    開始時刻のまま「使用中」として残っていた。これを信じると常に「他アプリ
    使用中」となり、監視が一度も止まらずスリープ阻害が解消しない。

    実体が消えていないこと、同名のプロセスが動いていることの両方を求める。
    """
    if not os.path.exists(exe_path):
        return False
    return os.path.basename(exe_path).lower() in running


def other_app_using_mic() -> bool:
    """自分以外のアプリが現にマイクを使用中かを返す。

    判定できない場合は False（＝他アプリは使っていない）を返す。ここで True に
    倒すと監視が止まらなくなり、スリープ阻害の解消という目的を果たせない。
    誤って False にしても、無操作時に監視を止めるという本来の動作になるだけで
    実害がない。曖昧なときは False に倒す。

    ストアアプリ側は実行ファイルのパスが分からず生存確認ができないため対象外と
    する。想定する用途（Discord・OBS・Zoom 等）はいずれも Win32 アプリで、
    NonPackaged 配下に現れる。

    スクリプト実行時は sys.executable が python.exe になるため、他の Python 製
    アプリも自分と見なされる。配布形態は EXE なので実運用では問題にならない。
    """
    if not _IS_WINDOWS:
        return False

    self_path = _self_executable_path()
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _MIC_CONSENT_KEY + "\\" + _NONPACKAGED
        ) as nonpackaged:
            names = _subkey_names(nonpackaged)
            if not names:
                return False

            running = running_process_names()
            for name in names:
                exe_path = _key_name_to_path(name)
                if exe_path == self_path:
                    # 自分がマイクを開いているのは当然なので数えない。除外しないと
                    # 「他アプリ使用中」が常に真になり、永久に閉じない。
                    continue
                try:
                    with winreg.OpenKey(nonpackaged, name) as sub:
                        if not _is_in_use(sub):
                            continue
                except OSError:
                    continue
                if _is_live_entry(exe_path, running):
                    return True
    except OSError:
        logger.debug("ConsentStore を読み取れませんでした", exc_info=True)
    return False


def should_suspend(idle_sec: float, threshold_sec: float, mic_shared: bool) -> bool:
    """キャプチャストリームを閉じてよいかを判定する。"""
    if threshold_sec <= 0:
        return False
    if mic_shared:
        # 他アプリが既にマイクを掴んでいる間は、そちら由来で電源要求が立つ。
        # こちらが閉じてもスリープしないので、監視を続けた方が得になる。
        return False
    return idle_sec >= threshold_sec
