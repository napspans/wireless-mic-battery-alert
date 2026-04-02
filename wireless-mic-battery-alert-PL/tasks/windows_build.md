# Windows最終ビルド手順

## 目的

Windows ネイティブ環境で最終 `.exe` を生成し、Step 35 を完了させる。

## 前提

- Windows 上で `python` が実行できる
- このワークスペースを Windows から参照できる
- PowerShell が使える

## 実行方法

1. PowerShell を開く
2. すでに次の場所まで移動できている前提で進める

```powershell
cd \\wsl.localhost\Ubuntu\home\napspans\workspace\wireless-mic-battery-alert
```

3. PL ディレクトリの `tasks` へ移動する

```powershell
cd .\wireless-mic-battery-alert-PL\tasks
```

4. `windows_build.ps1` を実行する

```powershell
powershell -ExecutionPolicy Bypass -File .\windows_build.ps1
```

このスクリプトは、UNC 配下の `dist/` を直接上書きせず、Windows ローカルの
`$env:USERPROFILE\wireless-mic-battery-alert-build\`
配下へビルド出力します。

## 実行内容

- `python -m pip install -r requirements.txt`
- `python -m PyInstaller build.spec --noconfirm --clean --distpath <Windowsローカル> --workpath <Windowsローカル>`
- `<Windowsローカル>\dist\WirelessMicBatteryAlert\WirelessMicBatteryAlert.exe` の存在確認
- `<Windowsローカル>\dist\WirelessMicBatteryAlert\_internal\assets` 同梱確認

## 確認ポイント

- `%USERPROFILE%\wireless-mic-battery-alert-build\dist\WirelessMicBatteryAlert\WirelessMicBatteryAlert.exe` が存在する
- `%USERPROFILE%\wireless-mic-battery-alert-build\dist\WirelessMicBatteryAlert\_internal\assets` に builtin 音声ファイルが入っている
- ビルド中に致命エラーが出ていない

## 想定する実行例

```powershell
PS C:\Users\napsp> cd \\wsl.localhost\Ubuntu\home\napspans\workspace\wireless-mic-battery-alert
PS Microsoft.PowerShell.Core\FileSystem::\\wsl.localhost\Ubuntu\home\napspans\workspace\wireless-mic-battery-alert> cd .\wireless-mic-battery-alert-PL\tasks
PS Microsoft.PowerShell.Core\FileSystem::\\wsl.localhost\Ubuntu\home\napspans\workspace\wireless-mic-battery-alert\wireless-mic-battery-alert-PL\tasks> powershell -ExecutionPolicy Bypass -File .\windows_build.ps1
```

## 次

ビルド成功後、Step 35 の報告に以下を載せる。

- 実行したコマンド
- EXE の生成パス
- 同梱 assets の確認結果
- ビルドログ上の警告・エラー要約
