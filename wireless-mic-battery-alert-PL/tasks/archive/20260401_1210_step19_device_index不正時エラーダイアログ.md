# Step 19: device_index 不正時のエラーダイアログ表示

## 目的

保存済みの `device_index` が無効（デバイス追加・削除でインデックスがずれた場合など）のとき、
`monitor.start()` が例外を送出してアプリがクラッシュするのを防ぎ、
ユーザーにエラーを通知してデバイスを再選択できるよう促す。

## 作業対象ファイル

- `wireless-mic-battery-alert-eng/main.py`

## 変更仕様

### エラーハンドリングの対象箇所

`main.py` 内で `self._monitor.start()` を呼ぶ箇所は以下の3か所ある。
いずれも例外をキャッチして `_on_stream_error()` に回す：

1. `run()` — アプリ起動時の初回 `start()` 呼び出し
2. `_toggle_monitor()` — ユーザーが手動で「監視 開始」を押した時
3. `_on_config_save()` — デバイス変更後の再起動時

### _on_stream_error メソッドの追加

例外メッセージを受け取り、以下を行う：

1. `tkinter.messagebox.showerror` でエラー内容とデバイス再選択を促すメッセージを表示する
2. その後 `_open_settings()` を呼んで設定画面を開く

ダイアログ表示には `tkinter.Tk` の一時的なルートウィンドウが必要になる場合がある。
ただし `_run_gui()` が既に動作している場合は重複しないよう配慮すること。
実現方法（一時 Tk ルートを生成するか、スレッドで遅延呼び出しするか等）は Eng の判断に委ねる。

## インターフェース制約

```python
def _on_stream_error(self, error_message: str) -> None:
```

## 完了条件

- [ ] `run()` での `monitor.start()` が例外を送出した場合、アプリがクラッシュせず `_on_stream_error()` が呼ばれる
- [ ] `_toggle_monitor()` での `monitor.start()` が例外を送出した場合も同様に処理される
- [ ] `_on_config_save()` でのデバイス変更後の `monitor.start()` が例外を送出した場合も同様に処理される
- [ ] `_on_stream_error()` がエラーダイアログを表示する
- [ ] ダイアログ確認後に設定画面が開く

## 注意事項

- `run()` 内でのエラーは tray 起動前に発生する可能性がある（起動シーケンス: `monitor.start()` → `tray.start()`）。ダイアログが表示できる状態かを踏まえて実装すること
- `stop()` は `start()` が失敗した時点では呼ばれていないため、エラー時に `stop()` を呼ぶ必要はない（`_stream` が `None` のまま）
