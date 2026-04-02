# Hotfix Step 30: builtin:notify_11 GUI対応 + 破損パス自動補正

## 目的

実機テストで発生した `FileNotFoundError: 音声ファイルが見つかりません: builtin:notify_11` を修正する。

**原因**: `_PAUSE_COMBO_TO_PATH` に `builtin:notify_11` のエントリがないため、設定画面起動時に
`monitor_stop_sound_path` / `monitor_resume_sound_path` の値が「カスタム...」として扱われ、
`_auto_save()` により `"custom:builtin:notify_11"` として config に書き戻される。
以降、notifier が `custom:` を除去して `"builtin:notify_11"` を得るが、これはファイルパスでないため
`os.path.exists()` が失敗し FileNotFoundError になる。

## 作業対象ファイル

- `wireless-mic-battery-alert-eng/gui.py`

## 変更仕様

### 1. `_PAUSE_SOUND_OPTIONS` に `"内蔵: Notify 11"` を追加

`"内蔵: Notify 04"` の直後に挿入すること（`"内蔵: Notify 04"` と `"内蔵: Chime"` の間）。

### 2. `_PAUSE_COMBO_TO_PATH` に `"内蔵: Notify 11": "builtin:notify_11"` を追加

`"内蔵: Notify 04": "builtin:notify_04"` の直後に挿入すること。

### 3. `_init_monitor_stop_sound_ui` / `_init_monitor_resume_sound_ui` に破損パスの自動補正を追加

両メソッドの冒頭で、config から取得した path が `"custom:builtin:"` で始まる場合、
`"custom:"` プレフィックスを除去した値が `_PAUSE_PATH_TO_COMBO` に存在するかチェックし、
存在する場合は除去後の値（`builtin:xxx`）を `path` として使用する（config への書き戻しは不要）。

## インターフェース制約

変更なし。既存の `_PAUSE_PATH_TO_COMBO`（`_PAUSE_COMBO_TO_PATH` の逆引き）は Python の dict 内包表記で
自動生成されているため、`_PAUSE_COMBO_TO_PATH` に追加するだけで `_PAUSE_PATH_TO_COMBO` にも自動反映される。

## 完了条件

- [ ] 新規インストール時（config.json なし）に起動し、タスクトレイから監視停止・再開を行ってもエラーが出ない
- [ ] 設定画面の「監視停止サウンド」「監視再開サウンド」のコンボボックスが「内蔵: Notify 11」と表示される
- [ ] 既存の破損 config（`custom:builtin:notify_11` が保存済み）でも「内蔵: Notify 11」として正しく表示され、エラーが出ない
- [ ] 既存の他のサウンド設定（`builtin:notify_04`、`builtin:chime` 等）が引き続き正常に動作する

## 動作確認手順

1. `config.json` を削除（またはバックアップ）してから `python main.py` を起動
2. 設定画面を開き、「通知設定」タブ → 「監視停止サウンド」「監視再開サウンド」が「内蔵: Notify 11」と表示されることを確認
3. タスクトレイから「監視停止」→「監視再開」を行い、例外が出ないことを確認
4. 次に `config.json` の `monitor_stop_sound_path` / `monitor_resume_sound_path` の値を手動で `"custom:builtin:notify_11"` に書き換えて再起動
5. 手順 2・3 を再実施し、正常に動作することを確認

## 注意事項

- `_PAUSE_PATH_TO_COMBO` は `_PAUSE_COMBO_TO_PATH` から自動生成されているため、`_PAUSE_COMBO_TO_PATH` のみを編集すれば十分
- `_PAUSE_SOUND_OPTIONS` は Combobox の `values` に使用しているリストのため、`_PAUSE_COMBO_TO_PATH` に追加したエントリと順序・文字列を一致させること
- 変更は `gui.py` のみ。`notifier.py`、`settings.py` は変更不要
