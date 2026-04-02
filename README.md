# wireless-mic-battery-alert

[English README](./README.en.md)

ワイヤレスマイクの電池切れや接続異常の兆候を、無音状態の監視によって検知し、ユーザーへ通知する Windows アプリケーションです。

## 概要

- ワイヤレスマイク入力を監視し、一定時間の無音を検知すると通知します
- 通知音、停止音、再開音、しきい値、監視時間などを設定できます
- Windows 向け `.exe` 配布を前提にしています

## 主な機能

- 入力デバイス選択
- 無音しきい値と継続時間の設定
- 通知音の変更
- 一時停止音、監視停止音、監視再開音の設定
- タスクトレイ常駐
- Windows 用 EXE ビルド

## ディレクトリ構成

```text
wireless-mic-battery-alert/
├── requirements.md
├── wireless-mic-battery-alert-PL/
│   ├── design/
│   └── tasks/
└── wireless-mic-battery-alert-eng/
    ├── assets/
    ├── main.py
    ├── gui.py
    ├── monitor.py
    ├── notifier.py
    ├── settings.py
    ├── tray.py
    ├── build.spec
    ├── build_windows.bat
    └── BUILD_WINDOWS.md
```

## 開発環境

- Python
- tkinter / ttk / sv_ttk
- sounddevice
- numpy
- matplotlib
- pygame
- pystray
- Pillow
- PyInstaller

依存パッケージの導入:

```bash
pip install -r wireless-mic-battery-alert-eng/requirements.txt
```

## 実行方法

開発環境で実行する場合:

```bash
cd wireless-mic-battery-alert-eng
python main.py
```

## Windows ビルド

Windows ネイティブ環境でのビルドを前提にしています。  
Linux / WSL 上で生成した成果物は最終配布物として扱いません。

詳細:

- [wireless-mic-battery-alert-eng/BUILD_WINDOWS.md](./wireless-mic-battery-alert-eng/BUILD_WINDOWS.md)

Windows での基本コマンド:

```bat
cd wireless-mic-battery-alert-eng
build_windows.bat
```

## 補足

- `wireless-mic-battery-alert-PL/` には設計、進行管理、レビュー用ドキュメントが含まれます
- `wireless-mic-battery-alert-eng/` には実装本体が含まれます
- `requirements-lock.txt` はビルド環境記録用です
