"""デバイス番号が再列挙でずれても、正しい受信機を選び直せることを確認する。

実測でこうなっていた:
  config.json の device_index = 9  → 「スピーカー (Realtek(R) Audio)」入力ch 0
  実際の受信機                     → index 12 (WASAPI)
番号だけを信じると、別のデバイスを黙って監視し続けることになる。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import monitor

failures = []


def check(name, cond, detail=""):
    print(f"{'PASS' if cond else 'FAIL'}  {name}{'  ' + detail if detail else ''}")
    if not cond:
        failures.append(name)


BOYA = "マイク (BOYA mini)"
OTHER = "CABLE Output (VB-Audio Point)"


def fake_list(devices):
    monitor.list_input_devices = lambda: devices


def dev(index, raw, default=False):
    return {"index": index, "name": raw + ("（既定）" if default else ""),
            "raw_name": raw, "is_default": default}


# 受信機が 9 番から 12 番へ移り、9 番は一覧から消えた状況
fake_list([dev(12, BOYA, default=True)])

check("保存名で正しい番号に解決できる",
      monitor.resolve_input_device(9, BOYA) == 12)
check("古い番号だけでも既定へ退避する",
      monitor.resolve_input_device(9, None) == 12)
check("番号が現在も有効ならそのまま使う",
      monitor.resolve_input_device(12, None) == 12)

# 受信機と別デバイスが両方いる状況で、名前が優先されること
fake_list([dev(3, OTHER), dev(12, BOYA, default=True)])
check("名前が番号より優先される",
      monitor.resolve_input_device(3, BOYA) == 12, "番号3・名前BOYA")
check("別デバイスを選んでいれば尊重する",
      monitor.resolve_input_device(None, OTHER) == 3)
check("名前が見つからなければ既定へ退避する",
      monitor.resolve_input_device(None, "存在しないマイク") == 12)

# 何も選べない場合
fake_list([])
check("候補ゼロなら None", monitor.resolve_input_device(9, BOYA) is None)

# 既定が無い一覧では先頭を使う
fake_list([dev(6, OTHER)])
check("既定が無ければ先頭を使う", monitor.resolve_input_device(None, None) == 6)

print()
if failures:
    print(f"{len(failures)} 件失敗: {failures}")
    sys.exit(1)
print("すべて成功")
