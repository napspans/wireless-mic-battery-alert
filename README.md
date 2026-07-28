# wireless-mic-battery-alert

[English README](./README.en.md)

ワイヤレスマイクの電池切れや接続異常を、受信機からの信号途絶によって検知し、ユーザーへ通知する Windows アプリケーションです。

## 概要

- ワイヤレスマイクの受信機を監視し、送信機からの信号が途絶えると通知します
- 通知音、一時停止音、監視停止音、監視再開音を設定できます
- Windows 向け `.exe` 配布を前提にしています

## 検出方式

送信機の電源が切れると、受信機は **完全なデジタル無音**（値が厳密に 0 のサンプル）を出力します。一方、送信機が生きている限りゼロサンプルは現れません。本アプリはこの差を判定に使います。

実測値（BOYA mini / WASAPI 経由 / 各 10 秒）:

| 状態 | ゼロサンプルの割合 | 非ゼロの最小値 |
|---|---|---|
| 送信機ON | 0.0000%（480,000 サンプル中 0 個） | 2.9e-14 |
| 送信機OFF | 100.00% | 存在しない |

音量レベルに依存しないため、しきい値の調整が不要で、環境の静かさにも左右されません。

### 音量しきい値を使わない理由

Windows 11 の **Voice Clarity**（キャプチャ経路に挿入される AI ノイズ抑制の APO）が有効な環境では、暗騒音が抑制されて **送信機が生きていても静かな部屋では -100 dB 以下**まで落ちます。「電池切れ時のノイズ」と「電池がある状態の環境音」の差が消えるため、どこにしきい値を置いても両者を区別できません。信号途絶による判定はこの影響を受けません。

## 主な機能

- 入力デバイス選択（WASAPI）
- 信号途絶による電池切れ検知
- アラート間隔の設定
- 通知音の変更（内蔵音 5 種 / 任意の WAV ファイル）
- 一時停止音、監視停止音、監視再開音の設定
- アラート後の監視自動一時停止と、信号復帰時の自動再開
- 現在の入力レベル（dB / ゼロ率）のライブ表示
- タスクトレイ常駐
- Windows 用 EXE ビルド

## 設定項目

| 項目 | 説明 |
|---|---|
| 入力デバイス | 監視するワイヤレスマイクの受信機 |
| アラート間隔 (秒) | 信号途絶が続く間、アラートを繰り返す間隔 |
| 全体音量 | 通知音の音量（0〜100） |
| 通知音 | 電池切れ検知時に鳴らす音 |
| 一時停止サウンド | 自動一時停止した際に鳴らす音 |
| 監視停止 / 監視再開サウンド | 手動で監視を切り替えた際に鳴らす音 |
| 自動一時停止 | 指定回数アラートを鳴らしたら監視を一時停止する |
| 一時停止までのアラート回数 | 既定は 1 回 |
| テーマ | system / light / dark |

設定は変更すると自動保存されます。画面下部に保存時刻が表示されます。

信号途絶と復帰の判定にはそれぞれ 1 秒の猶予があり、無線の瞬断や電源投入直後のリンク確立中に誤って反応しません。この値は設定項目ではなく内部定数です。

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

## スクリーンショット

![アプリ画面](./docs/images/app-screenshot.png)

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
