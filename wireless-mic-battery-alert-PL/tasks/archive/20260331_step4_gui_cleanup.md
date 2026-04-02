# Step 4: `gui.py` クリーンアップ

## 目的

`gui.py` から不要なインポートと削除済みの `builtin:default` に関連する残存エントリを除去し、
テスト再生時の音量引数を修正する。

## 作業対象ファイル

- `wireless-mic-battery-alert-eng/gui.py`

## 現状の問題点

1. `import settings` が未使用（`gui.py:10`）
2. `_SOUND_OPTIONS` に `"内蔵: Default"` が残存（`gui.py:16`）
   - Step 3 で `notifier.py` から `builtin:default` を削除済みのため不整合
3. `_COMBO_TO_PATH` に `"内蔵: Default": "builtin:default"` エントリが残存（`gui.py:21`）
   - 同上、削除が必要
4. `_test_play_sound` が `volume` を渡していない（`gui.py:292`）
   - Step 3 で `play_sound(sound_path, volume: int = 80)` に変更済みだが、テスト再生は設定の音量を無視してデフォルト値 80 を使っている

## 実装内容

### 1. `import settings` を削除する

```python
# 削除
import settings
```

### 2. `_SOUND_OPTIONS` から `"内蔵: Default"` を削除する

```python
# 変更前
_SOUND_OPTIONS = ["内蔵: Chime", "内蔵: Error", "内蔵: Marimba", "内蔵: Default", "カスタム..."]

# 変更後
_SOUND_OPTIONS = ["内蔵: Chime", "内蔵: Error", "内蔵: Marimba", "カスタム..."]
```

### 3. `_COMBO_TO_PATH` から `"内蔵: Default"` エントリを削除する

```python
# 変更前
_COMBO_TO_PATH = {
    "内蔵: Chime": "builtin:chime",
    "内蔵: Error": "builtin:error",
    "内蔵: Marimba": "builtin:marimba",
    "内蔵: Default": "builtin:default",
}

# 変更後
_COMBO_TO_PATH = {
    "内蔵: Chime": "builtin:chime",
    "内蔵: Error": "builtin:error",
    "内蔵: Marimba": "builtin:marimba",
}
```

### 4. `_test_play_sound` で `volume` を渡す

```python
# 変更前
def _test_play_sound(self):
    path = self._get_sound_path_value()

    def _play():
        try:
            from notifier import Notifier
            Notifier().play_sound(path)
        except Exception as e:
            logger.error("テスト再生に失敗しました: %s", e)

    threading.Thread(target=_play, daemon=True).start()

# 変更後
def _test_play_sound(self):
    path = self._get_sound_path_value()
    volume = self._config.get("alert_volume", 80)

    def _play():
        try:
            from notifier import Notifier
            Notifier().play_sound(path, volume)
        except Exception as e:
            logger.error("テスト再生に失敗しました: %s", e)

    threading.Thread(target=_play, daemon=True).start()
```

## 完了条件

- [ ] `gui.py` に `import settings` が存在しないこと
- [ ] `_SOUND_OPTIONS` に `"内蔵: Default"` が含まれていないこと
- [ ] `_COMBO_TO_PATH` に `"内蔵: Default"` キーが存在しないこと
- [ ] `_test_play_sound` で `volume` を `self._config.get("alert_volume", 80)` から取得して `play_sound` に渡していること

## 注意事項

- `tray.py`・`settings.py` は修正不要
- 動作を変えない（リファクタリングのみ）
- `wireless-mic-battery-alert-eng/` 配下のファイルのみ編集する
- 完了後、`tasks/step_report.md` を作成して報告すること
