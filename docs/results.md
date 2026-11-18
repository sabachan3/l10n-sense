# Results

## 2026-11-19: injected errors, Japanese (`data/bench/injected.ja.jsonl`)

15 hand-written mini apps, 45 cases, 276 strings, 56 of them carrying a wrong-sense translation
(for example Clear for notifications as 快晴, Leave for a call as 休暇). One run, best model
through the local Claude Code CLI.

| reviewer sees | precision | recall | false alarms |
|---|---:|---:|---:|
| source + translation (`pair`) | 0.981 | 0.946 | 1 / 220 |
| source + translation + code (`code`) | 1.000 | 1.000 | 0 / 220 |

Misses without code: Due as 未払い, Tip as チップ, Pick as 選ぶ. False alarm without code:
Check as 小切手入金 (correct for a cheque deposit, but only the code shows that).

What this does and does not show:

- Code context removed every miss and the false alarm.
- The set is too easy to rank reviewers: many injected errors are blatant, and key names such
  as `battery.charge` already give the sense away. Passing here is necessary, not sufficient.
- Next: cases mined from real fixes of machine-translated locale files, where the wrong strings
  are the ones that actually shipped.
