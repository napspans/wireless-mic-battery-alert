# Windows Build Guide

このリポジトリの最終成果物は Windows ネイティブ環境で生成した `.exe` を基準にする。  
Linux / WSL 上で生成した `dist/` や `build/` は最終成果物として扱わない。

## 前提環境

- Windows 上で `python` コマンドが使えること
- `python -m pip` が使えること
- このリポジトリを Windows パスで開いていること
- `requirements-lock.txt` は参照用のバージョン記録ファイルであり、実行時インストールは `requirements.txt` を使うこと

## 実行方法

リポジトリ直下で次を実行する。

```bat
build_windows.bat
```

補助スクリプトが内部で実行する内容は次のとおり。

```bat
python --version
python -m pip install -r requirements.txt
python -m PyInstaller --noconfirm --clean build.spec
```

## ログと確認箇所

- 実行ログ: `build\windows\build.txt`
- 生成される EXE: `dist\WirelessMicBatteryAlert\WirelessMicBatteryAlert.exe`
- 同梱 assets: `dist\WirelessMicBatteryAlert\_internal\assets\`

## 成功確認ポイント

- `build\windows\build.txt` の末尾に `RESULT=SUCCESS` がある
- `dist\WirelessMicBatteryAlert\WirelessMicBatteryAlert.exe` が存在する
- `dist\WirelessMicBatteryAlert\_internal\assets\alert_chime.wav` が存在する
- `dist\WirelessMicBatteryAlert\_internal\assets\alert_error.wav` が存在する
- `dist\WirelessMicBatteryAlert\_internal\assets\alert_marimba.wav` が存在する
- `dist\WirelessMicBatteryAlert\_internal\assets\notify_04.wav` が存在する
- `dist\WirelessMicBatteryAlert\_internal\assets\notify_11.wav` が存在する
- `build\windows\build.txt` にビルド失敗を示す `RESULT=FAILED` がない

## 補足

- `requirements-lock.txt` は今回のビルド環境で解決された依存バージョンの記録として参照する
- Windows 側で既に `build.txt` により Step 35 成功が確認できている場合も、再ビルド時は同じ確認箇所を使う
