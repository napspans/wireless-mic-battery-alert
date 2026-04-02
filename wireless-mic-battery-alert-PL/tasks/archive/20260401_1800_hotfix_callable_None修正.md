# Hotfix: callable | None 型アノテーション修正

## 目的

Python 3.11 実機テスト時に以下のエラーが発生した。原因は `callable | None` という型アノテーションで、`callable` は組み込み関数であり `|` 演算子を使用できない。

```
TypeError: unsupported operand type(s) for |: 'builtin_function_or_method' and 'NoneType'
```

## 作業対象ファイル

- `wireless-mic-battery-alert-eng/gui.py`

## 変更仕様

`SettingsGUI.__init__()` の `on_toggle_monitor` 引数から型アノテーションを除去する。

変更前:
```
on_toggle_monitor: callable | None = None,
```

変更後:
```
on_toggle_monitor=None,
```

## 完了条件

- [ ] `python main.py` が起動エラーなく実行できる

## 注意事項

- 変更はこの1箇所のみ。他の `callable` アノテーション（`on_config_save: callable` 等）は現状維持でよい
