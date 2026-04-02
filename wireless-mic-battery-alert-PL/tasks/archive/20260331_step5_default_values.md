# Step 5 修正指示: `_test_play_sound` の `alert_volume` フォールバック修正

## 目的

Step 5 で見落とした1箇所を修正する。

## 作業対象ファイル

- `wireless-mic-battery-alert-eng/gui.py`

## 修正内容

`gui.py:286` の `_test_play_sound` 内のフォールバック値を `80` から `50` に変更する。

```python
# 変更前
volume = self._config.get("alert_volume", 80)

# 変更後
volume = self._config.get("alert_volume", 50)
```

## 完了条件

- [ ] `gui.py` の `_test_play_sound` 内 `alert_volume` フォールバックが `50` であること
- [ ] `python3 -m py_compile gui.py` で構文エラーがないこと

## 注意事項

- この1行のみ変更する
- 完了後、`tasks/step_report.md` を作成して報告すること
