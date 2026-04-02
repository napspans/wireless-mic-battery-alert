# Step 21: アセット追加 + notifier.py + settings.py 変更

## 目的

ステータスサウンド機能（一時停止・再開・停止サウンド）に必要なサウンドアセットを追加し、
`notifier.py` と `settings.py` に必要な定義を追加する。

## 作業対象ファイル

- `wireless-mic-battery-alert-eng/assets/notify_04.wav`（新規作成）
- `wireless-mic-battery-alert-eng/assets/notify_11.wav`（新規作成）
- `wireless-mic-battery-alert-eng/notifier.py`
- `wireless-mic-battery-alert-eng/settings.py`

## 変更仕様

### アセット変換（wav生成）

以下のコマンドで mp3 → wav に変換し、`assets/` に配置する：

```
ffmpeg -i "/home/napspans/workspace/ClaudeCodeTest/docs/wireless-mic-battery-alert/po-data/新しい通知メッセージ-04.mp3" -ar 44100 -ac 1 wireless-mic-battery-alert-eng/assets/notify_04.wav
ffmpeg -i "/home/napspans/workspace/ClaudeCodeTest/docs/wireless-mic-battery-alert/po-data/新しい通知メッセージ-11.mp3" -ar 44100 -ac 1 wireless-mic-battery-alert-eng/assets/notify_11.wav
```

### notifier.py

`_BUILTIN_MAP` に2エントリを追加する：

```
"builtin:notify_04" → assets/notify_04.wav
"builtin:notify_11" → assets/notify_11.wav
```

### settings.py

`DEFAULT_CONFIG` に以下の2キーを追加する：

```
"pause_sound_enabled": True
"pause_sound_path": "builtin:notify_04"
```

再開・停止サウンドはユーザー設定不要のため config キーを設けない。

## インターフェース制約

なし

## 完了条件

- [ ] `assets/notify_04.wav` と `assets/notify_11.wav` が生成されている
- [ ] `notifier.py` の `_BUILTIN_MAP` に `builtin:notify_04` と `builtin:notify_11` が追加されている
- [ ] `settings.py` の `DEFAULT_CONFIG` に `pause_sound_enabled` と `pause_sound_path` が追加されている
- [ ] `python3 -m py_compile notifier.py settings.py` でエラーがないこと

## 注意事項

- `ClaudeCodeTest/` への書き込み・編集は禁止（読み取りのみ）
- ffmpeg が使えない場合は代替手段（pydub 等）を使ってよい
