# Step 1: PyInstaller .spec ファイルの作成

## 目的
Windows向け `.exe` として配布できるよう、PyInstallerのビルド設定ファイル（`build.spec`）を作成する。
アセットファイルや外部テーマライブラリを正しくバンドルし、追加インストール不要で動作する実行ファイルを生成できる状態にする。

## 作業対象ファイル
- `wireless-mic-battery-alert-eng/requirements.txt`（pyinstaller 追加）
- `wireless-mic-battery-alert-eng/build.spec`（新規作成）

## 変更仕様

### requirements.txt
- `pyinstaller` を末尾に追加する

### build.spec
以下の設定を含む `.spec` ファイルを作成する:

**datas（バンドル対象）:**
- `assets/` ディレクトリ（WAVファイル3本）を実行ファイル内の `assets/` に含める
- `sv-ttk` のテーマファイル（`.tcl` および関連ファイル）を含める
  - `sv-ttk` のインストール先は `sv_ttk` パッケージディレクトリ。`sv_ttk` の `__file__` から辿るか、`collect_data_files('sv_ttk')` を使って取得する

**hiddenimports（自動検出されない依存）:**
- `pystray._win32`（Windowsトレイバックエンド）
- `sounddevice`
- `pygame`
- `PIL._tkinter_finder`
- その他、実際にビルド・実行して不足があれば追加する

**ビルドモード:**
- `--onedir`（ワンディレクトリ形式）を採用する
  - `onefile` はアンチウイルスソフトによる誤検知リスクが高いため避ける

**エントリーポイント:**
- `main.py`

**その他:**
- コンソールウィンドウは非表示にする（`console=False`）
- アプリ名は `WirelessMicBatteryAlert` とする

## インターフェース制約
なし（build.specの内部構造はEngに委ねる）

## 完了条件
- [ ] `requirements.txt` に `pyinstaller` が追加されている
- [ ] `build.spec` が作成されており、上記のdatas・hiddenimportsが設定されている
- [ ] `pyinstaller build.spec` コマンドでビルドが完了する（エラーなし）
  - ビルドはWindowsのPythonから実行すること（WSL上のLinux Pythonでは Windows exe を生成できない）
  - WSL内から `pyinstaller.exe build.spec` または Windows側のターミナルで実行する
- [ ] `dist/WirelessMicBatteryAlert/WirelessMicBatteryAlert.exe` が生成されている

## 注意事項
- ビルド環境はWindows Python（WSL外）を使用すること
- `sv-ttk` のデータファイル取得に `collect_data_files` が使えない場合は、手動でパスを指定してよい
- ビルド成功後、`dist/` と `build/` は `.gitignore` 相当として扱い、リポジトリには含めない
