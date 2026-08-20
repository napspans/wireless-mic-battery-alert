"""表示文字列の翻訳。

対象は画面に出る文字列だけで、`logger` に渡す診断メッセージは含めない。
ログは解析用であり、読むのは開発者と PO に限られる。

内部で持つのは常に安定キー（`builtin:chime` や `dark` など）で、翻訳するのは
表示の直前に限る。以前は Combobox の値そのものが日本語文字列で、それが dict の
キーも兼ねていたため、言語を変えると設定の読み書きが壊れる構造だった。
"""

import locale
import logging

logger = logging.getLogger(__name__)

# アプリ名は訳さない。言語を変えるたびにタスクバーやトレイでの見え方が
# 変わると、同じアプリだと分からなくなる。EXE のファイル名とも揃えてある。
APP_NAME = "Wireless Mic Battery Alert"

DEFAULT_LANGUAGE = "ja"
FALLBACK_LANGUAGE = "en"

# 表示順。設定画面の言語プルダウンもこの順で並ぶ。
LANGUAGES = ["ja", "en", "ko", "zh", "fr"]

# 言語名は常にその言語自身で表記する。読めない言語の名前を訳しても選べない。
LANGUAGE_LABELS = {
    "ja": "日本語",
    "en": "English",
    "ko": "한국어",
    "zh": "简体中文",
    "fr": "Français",
}

# Tk はフォントのフォールバック連鎖を持たないため、言語ごとに候補を順に試す。
# 先頭から、その環境に実在する最初のファミリを採用する。
FONT_CANDIDATES = {
    "ja": ["Yu Gothic UI", "Meiryo UI", "MS UI Gothic", "Segoe UI"],
    "en": ["Segoe UI Variable Text", "Segoe UI", "Yu Gothic UI"],
    "fr": ["Segoe UI Variable Text", "Segoe UI", "Yu Gothic UI"],
    "ko": ["Malgun Gothic", "Segoe UI", "Yu Gothic UI"],
    "zh": ["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"],
}

_TRANSLATIONS = {
    "ja": {
        # ── アプリ ──
        "window.settings": "設定",

        # ── タブ ──
        "tab.monitor": "監視設定",
        "tab.notify": "通知設定",
        "tab.detail": "詳細設定",

        # ── 監視設定 ──
        "section.device": "デバイスと検知パラメータ",
        "label.input_device": "入力デバイス",
        "label.alert_interval": "アラート間隔 (秒)",
        "device.none": "（デバイスなし）",
        "device.default_suffix": "{name}（既定）",

        # ── 通知設定 ──
        "section.alert": "アラートと通知",
        "label.volume": "全体音量 (0-100)",
        "label.alert_sound": "通知音",
        "section.pause_sound": "一時停止サウンド",
        "label.pause_sound": "一時停止サウンド",
        "section.stop_sound": "監視停止サウンド",
        "label.stop_sound": "監視停止サウンド",
        "section.resume_sound": "監視再開サウンド",
        "label.resume_sound": "監視再開サウンド",
        "label.sound_file": "サウンドファイル",
        "check.enable": "有効にする",
        "button.test_play": "テスト再生",
        "button.browse": "参照",

        # ── 通知音の選択肢 ──
        "sound.builtin:chime": "内蔵: Chime",
        "sound.builtin:error": "内蔵: Error",
        "sound.builtin:marimba": "内蔵: Marimba",
        "sound.builtin:notify_04": "内蔵: Notify 04",
        "sound.builtin:notify_11": "内蔵: Notify 11",
        "sound.custom": "カスタム...",

        # ── 詳細設定 ──
        "section.auto_pause": "監視の自動一時停止",
        "label.auto_pause": "自動一時停止",
        "check.auto_pause": "アラート後に監視を一時停止する",
        "label.auto_pause_count": "一時停止までのアラート回数",
        "hint.auto_resume": "信号が戻ると自動的に監視を再開します",
        "section.sleep": "スリープ連動",
        "label.idle_suspend": "無操作で自動停止",
        "check.idle_suspend": "PC の無操作が続いたら監視を止める",
        "label.idle_suspend_sec": "無操作と判定するまで（秒）",
        "hint.idle_suspend_sec": "Windows のスリープ設定より短くしてください",
        "label.mic_share": "他アプリ使用中は継続",
        "check.mic_share": "他のアプリがマイクを使用中は監視を続ける",
        "hint.mic_share": "マイクを開いたままだと Windows がスリープしません",
        "section.app": "アプリ設定",
        "label.theme": "テーマ",
        "label.language": "言語",
        "label.version": "バージョン",
        "version.line": "v{version}（{date} 更新）",
        "theme.system": "システムに合わせる",
        "theme.light": "ライト",
        "theme.dark": "ダーク",

        # ── 波形とステータス ──
        "button.zoom_in": "ズーム表示",
        "button.zoom_out": "全体表示",
        "button.monitor_start": "監視 開始",
        "button.monitor_stop": "監視 停止",
        "status.stopped": "○ 停止中",
        "status.idle_suspended": "⏸ 自動停止中（PC 無操作）",
        "status.paused": "⏸ 一時停止中",
        "status.monitoring": "● 監視中",
        "status.levels": "   {db} dB / ゼロ率 {ratio}%",

        # ── 保存表示 ──
        "save.saving": "保存中…",
        "save.saved": "✓ {time} に保存しました",

        # ── ファイル選択ダイアログ ──
        "dialog.select_alert_sound": "通知音ファイルを選択",
        "dialog.select_pause_sound": "一時停止サウンドファイルを選択",
        "dialog.select_stop_sound": "監視停止サウンドファイルを選択",
        "dialog.select_resume_sound": "監視再開サウンドファイルを選択",
        "filetype.wav": "WAV ファイル",
        "filetype.all": "すべてのファイル",

        # ── エラーダイアログ ──
        "error.device_title": "入力デバイスエラー",
        "error.device_body": (
            "入力デバイスを開始できませんでした。\n\n"
            "{error}\n\n"
            "設定画面を開くので、入力デバイスを再選択してください。"
        ),

        # ── トレイメニュー ──
        "tray.open_settings": "設定を開く",
        "tray.open_config_location": "設定ファイルの場所を開く",
        "tray.open_log": "ログを開く",
        "tray.quit": "終了",
    },
    "en": {
        "window.settings": "Settings",

        "tab.monitor": "Monitoring",
        "tab.notify": "Notifications",
        "tab.detail": "Advanced",

        "section.device": "Device and detection",
        "label.input_device": "Input device",
        "label.alert_interval": "Alert interval (sec)",
        "device.none": "(no device)",
        "device.default_suffix": "{name} (default)",

        "section.alert": "Alerts and notifications",
        "label.volume": "Master volume (0-100)",
        "label.alert_sound": "Alert sound",
        "section.pause_sound": "Pause sound",
        "label.pause_sound": "Pause sound",
        "section.stop_sound": "Monitoring stop sound",
        "label.stop_sound": "Monitoring stop sound",
        "section.resume_sound": "Monitoring resume sound",
        "label.resume_sound": "Monitoring resume sound",
        "label.sound_file": "Sound file",
        "check.enable": "Enable",
        "button.test_play": "Test",
        "button.browse": "Browse",

        "sound.builtin:chime": "Built-in: Chime",
        "sound.builtin:error": "Built-in: Error",
        "sound.builtin:marimba": "Built-in: Marimba",
        "sound.builtin:notify_04": "Built-in: Notify 04",
        "sound.builtin:notify_11": "Built-in: Notify 11",
        "sound.custom": "Custom...",

        "section.auto_pause": "Automatic pause",
        "label.auto_pause": "Auto pause",
        "check.auto_pause": "Pause monitoring after an alert",
        "label.auto_pause_count": "Alerts before pausing",
        "hint.auto_resume": "Monitoring resumes automatically when the signal returns",
        "section.sleep": "Sleep behaviour",
        "label.idle_suspend": "Stop when idle",
        "check.idle_suspend": "Stop monitoring while the PC is idle",
        "label.idle_suspend_sec": "Idle threshold (sec)",
        "hint.idle_suspend_sec": "Keep this shorter than the Windows sleep timeout",
        "label.mic_share": "Keep running for other apps",
        "check.mic_share": "Keep monitoring while another app uses the microphone",
        "hint.mic_share": "Windows will not sleep while the microphone stays open",
        "section.app": "Application",
        "label.theme": "Theme",
        "label.language": "Language",
        "label.version": "Version",
        "version.line": "v{version} (updated {date})",
        "theme.system": "Match system",
        "theme.light": "Light",
        "theme.dark": "Dark",

        "button.zoom_in": "Zoom in",
        "button.zoom_out": "Zoom out",
        "button.monitor_start": "Start",
        "button.monitor_stop": "Stop",
        "status.stopped": "○ Stopped",
        "status.idle_suspended": "⏸ Auto-stopped (PC idle)",
        "status.paused": "⏸ Paused",
        "status.monitoring": "● Monitoring",
        "status.levels": "   {db} dB / silence {ratio}%",

        "save.saving": "Saving…",
        "save.saved": "✓ Saved at {time}",

        "dialog.select_alert_sound": "Select an alert sound file",
        "dialog.select_pause_sound": "Select a pause sound file",
        "dialog.select_stop_sound": "Select a monitoring stop sound file",
        "dialog.select_resume_sound": "Select a monitoring resume sound file",
        "filetype.wav": "WAV files",
        "filetype.all": "All files",

        "error.device_title": "Input device error",
        "error.device_body": (
            "The input device could not be started.\n\n"
            "{error}\n\n"
            "The settings window will open. Please select the input device again."
        ),

        "tray.open_settings": "Open settings",
        "tray.open_config_location": "Show config file location",
        "tray.open_log": "Open log",
        "tray.quit": "Quit",
    },
    "ko": {
        "window.settings": "설정",

        "tab.monitor": "모니터링",
        "tab.notify": "알림",
        "tab.detail": "고급",

        "section.device": "장치 및 감지",
        "label.input_device": "입력 장치",
        "label.alert_interval": "알림 간격 (초)",
        "device.none": "(장치 없음)",
        "device.default_suffix": "{name} (기본값)",

        "section.alert": "경고 및 알림",
        "label.volume": "전체 음량 (0-100)",
        "label.alert_sound": "알림음",
        "section.pause_sound": "일시정지 사운드",
        "label.pause_sound": "일시정지 사운드",
        "section.stop_sound": "모니터링 중지 사운드",
        "label.stop_sound": "모니터링 중지 사운드",
        "section.resume_sound": "모니터링 재개 사운드",
        "label.resume_sound": "모니터링 재개 사운드",
        "label.sound_file": "사운드 파일",
        "check.enable": "사용",
        "button.test_play": "테스트 재생",
        "button.browse": "찾아보기",

        "sound.builtin:chime": "기본 제공: Chime",
        "sound.builtin:error": "기본 제공: Error",
        "sound.builtin:marimba": "기본 제공: Marimba",
        "sound.builtin:notify_04": "기본 제공: Notify 04",
        "sound.builtin:notify_11": "기본 제공: Notify 11",
        "sound.custom": "사용자 지정...",

        "section.auto_pause": "자동 일시정지",
        "label.auto_pause": "자동 일시정지",
        "check.auto_pause": "경고 후 모니터링을 일시정지",
        "label.auto_pause_count": "일시정지까지의 경고 횟수",
        "hint.auto_resume": "신호가 돌아오면 자동으로 모니터링을 재개합니다",
        "section.sleep": "절전 연동",
        "label.idle_suspend": "유휴 시 자동 중지",
        "check.idle_suspend": "PC가 유휴 상태이면 모니터링을 중지",
        "label.idle_suspend_sec": "유휴로 판정할 시간 (초)",
        "hint.idle_suspend_sec": "Windows 절전 설정보다 짧게 지정하세요",
        "label.mic_share": "다른 앱 사용 중 계속",
        "check.mic_share": "다른 앱이 마이크를 사용 중이면 모니터링을 계속",
        "hint.mic_share": "마이크가 열려 있으면 Windows가 절전 모드로 전환되지 않습니다",
        "section.app": "앱 설정",
        "label.theme": "테마",
        "label.language": "언어",
        "label.version": "버전",
        "version.line": "v{version} ({date} 업데이트)",
        "theme.system": "시스템 설정",
        "theme.light": "라이트",
        "theme.dark": "다크",

        "button.zoom_in": "확대 표시",
        "button.zoom_out": "전체 표시",
        "button.monitor_start": "모니터링 시작",
        "button.monitor_stop": "모니터링 중지",
        "status.stopped": "○ 중지됨",
        "status.idle_suspended": "⏸ 자동 중지 (PC 유휴)",
        "status.paused": "⏸ 일시정지",
        "status.monitoring": "● 모니터링 중",
        "status.levels": "   {db} dB / 무음률 {ratio}%",

        "save.saving": "저장 중…",
        "save.saved": "✓ {time}에 저장했습니다",

        "dialog.select_alert_sound": "알림음 파일 선택",
        "dialog.select_pause_sound": "일시정지 사운드 파일 선택",
        "dialog.select_stop_sound": "모니터링 중지 사운드 파일 선택",
        "dialog.select_resume_sound": "모니터링 재개 사운드 파일 선택",
        "filetype.wav": "WAV 파일",
        "filetype.all": "모든 파일",

        "error.device_title": "입력 장치 오류",
        "error.device_body": (
            "입력 장치를 시작할 수 없습니다.\n\n"
            "{error}\n\n"
            "설정 창을 엽니다. 입력 장치를 다시 선택해 주세요."
        ),

        "tray.open_settings": "설정 열기",
        "tray.open_config_location": "설정 파일 위치 열기",
        "tray.open_log": "로그 열기",
        "tray.quit": "종료",
    },
    "zh": {
        "window.settings": "设置",

        "tab.monitor": "监控",
        "tab.notify": "通知",
        "tab.detail": "高级",

        "section.device": "设备与检测",
        "label.input_device": "输入设备",
        "label.alert_interval": "警告间隔（秒）",
        "device.none": "（无设备）",
        "device.default_suffix": "{name}（默认）",

        "section.alert": "警告与通知",
        "label.volume": "总音量 (0-100)",
        "label.alert_sound": "提示音",
        "section.pause_sound": "暂停提示音",
        "label.pause_sound": "暂停提示音",
        "section.stop_sound": "停止监控提示音",
        "label.stop_sound": "停止监控提示音",
        "section.resume_sound": "恢复监控提示音",
        "label.resume_sound": "恢复监控提示音",
        "label.sound_file": "声音文件",
        "check.enable": "启用",
        "button.test_play": "试听",
        "button.browse": "浏览",

        "sound.builtin:chime": "内置: Chime",
        "sound.builtin:error": "内置: Error",
        "sound.builtin:marimba": "内置: Marimba",
        "sound.builtin:notify_04": "内置: Notify 04",
        "sound.builtin:notify_11": "内置: Notify 11",
        "sound.custom": "自定义...",

        "section.auto_pause": "自动暂停",
        "label.auto_pause": "自动暂停",
        "check.auto_pause": "警告后暂停监控",
        "label.auto_pause_count": "暂停前的警告次数",
        "hint.auto_resume": "信号恢复后将自动继续监控",
        "section.sleep": "睡眠联动",
        "label.idle_suspend": "空闲时自动停止",
        "check.idle_suspend": "电脑持续空闲时停止监控",
        "label.idle_suspend_sec": "判定为空闲的时间（秒）",
        "hint.idle_suspend_sec": "请设置为短于 Windows 的睡眠时间",
        "label.mic_share": "其他应用使用时继续",
        "check.mic_share": "其他应用使用麦克风时继续监控",
        "hint.mic_share": "麦克风保持打开时 Windows 不会进入睡眠",
        "section.app": "应用设置",
        "label.theme": "主题",
        "label.language": "语言",
        "label.version": "版本",
        "version.line": "v{version}（{date} 更新）",
        "theme.system": "跟随系统",
        "theme.light": "浅色",
        "theme.dark": "深色",

        "button.zoom_in": "放大显示",
        "button.zoom_out": "全部显示",
        "button.monitor_start": "开始监控",
        "button.monitor_stop": "停止监控",
        "status.stopped": "○ 已停止",
        "status.idle_suspended": "⏸ 自动停止（电脑空闲）",
        "status.paused": "⏸ 已暂停",
        "status.monitoring": "● 监控中",
        "status.levels": "   {db} dB / 静音率 {ratio}%",

        "save.saving": "正在保存…",
        "save.saved": "✓ 已于 {time} 保存",

        "dialog.select_alert_sound": "选择提示音文件",
        "dialog.select_pause_sound": "选择暂停提示音文件",
        "dialog.select_stop_sound": "选择停止监控提示音文件",
        "dialog.select_resume_sound": "选择恢复监控提示音文件",
        "filetype.wav": "WAV 文件",
        "filetype.all": "所有文件",

        "error.device_title": "输入设备错误",
        "error.device_body": (
            "无法启动输入设备。\n\n"
            "{error}\n\n"
            "将打开设置窗口，请重新选择输入设备。"
        ),

        "tray.open_settings": "打开设置",
        "tray.open_config_location": "打开配置文件位置",
        "tray.open_log": "打开日志",
        "tray.quit": "退出",
    },
    "fr": {
        "window.settings": "Paramètres",

        "tab.monitor": "Surveillance",
        "tab.notify": "Notifications",
        "tab.detail": "Avancé",

        "section.device": "Périphérique et détection",
        "label.input_device": "Périphérique d'entrée",
        "label.alert_interval": "Intervalle d'alerte (s)",
        "device.none": "(aucun périphérique)",
        "device.default_suffix": "{name} (par défaut)",

        "section.alert": "Alertes et notifications",
        "label.volume": "Volume général (0-100)",
        "label.alert_sound": "Son d'alerte",
        "section.pause_sound": "Son de pause",
        "label.pause_sound": "Son de pause",
        "section.stop_sound": "Son d'arrêt de surveillance",
        "label.stop_sound": "Son d'arrêt de surveillance",
        "section.resume_sound": "Son de reprise de surveillance",
        "label.resume_sound": "Son de reprise de surveillance",
        "label.sound_file": "Fichier son",
        "check.enable": "Activer",
        "button.test_play": "Tester",
        "button.browse": "Parcourir",

        "sound.builtin:chime": "Intégré : Chime",
        "sound.builtin:error": "Intégré : Error",
        "sound.builtin:marimba": "Intégré : Marimba",
        "sound.builtin:notify_04": "Intégré : Notify 04",
        "sound.builtin:notify_11": "Intégré : Notify 11",
        "sound.custom": "Personnalisé...",

        "section.auto_pause": "Pause automatique",
        "label.auto_pause": "Pause automatique",
        "check.auto_pause": "Mettre la surveillance en pause après une alerte",
        "label.auto_pause_count": "Alertes avant la pause",
        "hint.auto_resume": "La surveillance reprend dès que le signal revient",
        "section.sleep": "Mise en veille",
        "label.idle_suspend": "Arrêt en cas d'inactivité",
        "check.idle_suspend": "Arrêter la surveillance quand le PC est inactif",
        "label.idle_suspend_sec": "Seuil d'inactivité (s)",
        "hint.idle_suspend_sec": "Gardez cette valeur inférieure au délai de veille de Windows",
        "label.mic_share": "Continuer pour les autres applis",
        "check.mic_share": "Continuer la surveillance si une autre appli utilise le micro",
        "hint.mic_share": "Windows ne se met pas en veille tant que le micro reste ouvert",
        "section.app": "Application",
        "label.theme": "Thème",
        "label.language": "Langue",
        "label.version": "Version",
        "version.line": "v{version} (màj {date})",
        "theme.system": "Suivre le système",
        "theme.light": "Clair",
        "theme.dark": "Sombre",

        "button.zoom_in": "Zoom avant",
        "button.zoom_out": "Vue globale",
        "button.monitor_start": "Démarrer",
        "button.monitor_stop": "Arrêter",
        "status.stopped": "○ Arrêté",
        "status.idle_suspended": "⏸ Arrêt auto (PC inactif)",
        "status.paused": "⏸ En pause",
        "status.monitoring": "● Surveillance",
        "status.levels": "   {db} dB / silence {ratio} %",

        "save.saving": "Enregistrement…",
        "save.saved": "✓ Enregistré à {time}",

        "dialog.select_alert_sound": "Choisir un fichier de son d'alerte",
        "dialog.select_pause_sound": "Choisir un fichier de son de pause",
        "dialog.select_stop_sound": "Choisir un fichier de son d'arrêt",
        "dialog.select_resume_sound": "Choisir un fichier de son de reprise",
        "filetype.wav": "Fichiers WAV",
        "filetype.all": "Tous les fichiers",

        "error.device_title": "Erreur de périphérique d'entrée",
        "error.device_body": (
            "Impossible de démarrer le périphérique d'entrée.\n\n"
            "{error}\n\n"
            "La fenêtre des paramètres va s'ouvrir. Sélectionnez à nouveau le périphérique."
        ),

        "tray.open_settings": "Ouvrir les paramètres",
        "tray.open_config_location": "Ouvrir l'emplacement du fichier de configuration",
        "tray.open_log": "Ouvrir le journal",
        "tray.quit": "Quitter",
    },
}

_current_language = DEFAULT_LANGUAGE
_listeners: list = []


def available_languages() -> list:
    return list(LANGUAGES)


def get_language() -> str:
    return _current_language


def set_language(language: str) -> None:
    """表示言語を切り替え、登録済みのリスナーへ通知する。"""
    global _current_language
    if language not in _TRANSLATIONS:
        logger.warning("未対応の言語が指定されました: %s", language)
        language = FALLBACK_LANGUAGE
    if language == _current_language:
        return
    _current_language = language
    for listener in list(_listeners):
        try:
            listener(language)
        except Exception:
            logger.exception("言語変更の通知に失敗しました")


def add_listener(callback) -> None:
    """言語が変わったときに呼ばれる関数を登録する。"""
    _listeners.append(callback)


def remove_listener(callback) -> None:
    if callback in _listeners:
        _listeners.remove(callback)


def t(key: str, **kwargs) -> str:
    """キーを現在の言語に訳す。

    翻訳漏れで画面が落ちるより、英語なりキーなりが出たまま動くほうがよい。
    未知のキーも書式引数の不足も例外にしない。
    """
    text = _TRANSLATIONS.get(_current_language, {}).get(key)
    if text is None:
        text = _TRANSLATIONS[FALLBACK_LANGUAGE].get(key)
    if text is None:
        logger.warning("翻訳が見つかりません: %s", key)
        return key
    if not kwargs:
        return text
    try:
        return text.format(**kwargs)
    except (KeyError, IndexError):
        logger.warning("翻訳の書式指定が不正です: %s", key)
        return text


def settings_window_title() -> str:
    """設定ウィンドウのタイトル。アプリ名は訳さず、種別だけ訳す。"""
    return f"{APP_NAME} - {t('window.settings')}"


def font_families(language: str = None) -> list:
    """その言語で優先したいフォントファミリを優先順に返す。"""
    return list(FONT_CANDIDATES.get(language or _current_language,
                                    FONT_CANDIDATES[FALLBACK_LANGUAGE]))


def detect_system_language() -> str:
    """OS のロケールから初期表示言語を推定する。

    中国語は簡体字のみ用意しているため、繁体字ロケールもここへ寄せる。
    翻訳がないよりは読める字が出るほうがよい。
    """
    try:
        tag = locale.getdefaultlocale()[0] or ""
    except (ValueError, TypeError):
        tag = ""
    prefix = tag.replace("-", "_").split("_")[0].lower()
    if prefix in _TRANSLATIONS:
        return prefix
    return FALLBACK_LANGUAGE
