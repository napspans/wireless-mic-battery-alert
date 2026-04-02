# Step 13: matplotlibログ抑制 + 終了時SystemExitエラー解消

## 目的
実機テストで確認された2つのログ問題を修正する。
- 問題1: 起動時にmatplotlibのDEBUGログが大量出力される
- 問題4: 終了時にpystrayがSystemExitをエラーとして記録する

## 作業対象ファイル
- `wireless-mic-battery-alert-eng/main.py`

## 変更仕様

### 問題1: matplotlibログ抑制
`logging.basicConfig(...)` の直後に、matplotlibロガーのレベルをWARNINGに設定する。
これにより、matplotlib（font_manager等）のDEBUGログがルートロガーに流れなくなる。

### 問題4: SystemExit → os._exit
`App._quit()` 内の `sys.exit(0)` を `os._exit(0)` に変更する。
`sys.exit()` はSystemExit例外を送出するため、pystrayのコールバックスレッドがこれをエラーとして捕捉してしまう。
`os._exit(0)` はプロセスを即時終了し、例外を送出しない。
`import os` は `main.py` の先頭に既に存在することを確認した上で変更すること。

## インターフェース制約
なし（内部実装の変更のみ）

## 完了条件
- [ ] `python main.py` 起動時にmatplotlibのDEBUGログが出力されない
- [ ] アプリ終了時のログに `ERROR pystray._base` の SystemExit エラーが出力されない
- [ ] 既存の動作（監視・通知・トレイアイコン）に影響がない

## 注意事項
- `import os` が既に存在する場合は追加不要
- basicConfigの変更はせず、matplotlibロガーのみを対象にすること
