# Step 6: ロギング設定の追加

## 目的

エントリポイントである `main.py` にロギング設定を追加し、`gui.py` や `notifier.py` が出力するログが確実に記録されるようにする。

## 作業対象ファイル

- `wireless-mic-battery-alert-eng/main.py`

## 現状の問題点

`main.py` は `gui.py` / `notifier.py` が使用する `logging` モジュールの設定（`basicConfig` 等）を行っていない。
そのため、警告・エラーログがデフォルトの `lastResort` ハンドラ（WARNING以上のみ stderr 出力）に委ねられており、DEBUG/INFO ログは捨てられる。

## 実装内容

`if __name__ == "__main__":` ブロックの直前に、以下のロギング設定を追加する。

```python
import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
```

ただし `import logging` はファイル先頭にまとめること（既存の `import` 群に追加）。
`basicConfig` の呼び出しは `if __name__ == "__main__":` ブロック内の `App().run()` より前に記述する。

### 変更後の `if __name__ == "__main__":` ブロック（イメージ）

```python
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    App().run()
```

## 完了条件

- [ ] `main.py` の先頭 import 群に `import logging` が追加されていること
- [ ] `if __name__ == "__main__":` ブロック内で `logging.basicConfig(...)` が `App().run()` より前に呼ばれていること
- [ ] `python3 -m py_compile main.py` で構文エラーがないこと

## 注意事項

- `App` クラス本体は変更しない
- `wireless-mic-battery-alert-eng/` 配下のファイルのみ編集する
- 完了後、`tasks/step_report.md` を作成して報告すること
