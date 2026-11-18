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

## 2026-11-19: real fix, Chinese (`data/bench/real.omniroute.zh.jsonl`)

OmniRoute (MIT) fixed 295 wrong-sense machine translations in its zh-CN locale file
(pull request 19308). Cases hold the file as it was before the fix: 196 windows of up to 20
neighbouring keys, 3,846 strings, 295 labelled wrong. Usage in code was found for 86% of keys.

| reviewer sees | precision | recall | flagged but not in the fix |
|---|---:|---:|---:|
| source + translation (`pair`) | 0.565 | 0.736 | 167 / 3,551 |
| source + translation + code (`code`) | 0.506 | 0.756 | 218 / 3,551 |

Against these labels the gate (0.9 / 0.7) fails on precision. The labels are the weak part:

- The fix only swept strings of 30 characters or fewer and left "legitimate alternative
  wordings" alone, so `ok` means "not touched", not "verified correct".
- I read 14 random extra flags per mode. Without code: 11 real errors the fix missed (audit as
  审核, rate limits as 费率, Duplicate as 重复, a translated identifier, omitted content), 2
  debatable, 1 caused by a placeholder English source. With code: 9 real, 3 debatable, 2 caused
  by placeholder English. If those shares held, precision would be about 0.9 without code and
  about 0.8 with code, but 14 items cannot carry that claim.
- About a quarter of the fix is glossary alignment (供应商 to 提供者) and leftover English, which
  the reviewer is told not to flag as wrong sense. Those count as misses here.

Code context did not help on this set: the wrong senses are blatant in a known domain, and
code mode adds flags where the English source itself is a placeholder generated from the key
name (`Template Load Hint`) while the code passes arguments the string never uses.

What is needed before any precision claim: a sample of flags judged by a native speaker.

## 2026-11-19: field audit, Japanese (unreviewed file)

The same repository's `ja.json` has never been fixed. On 100 windows (2,000 strings), code
mode flagged 108 strings (5.4%). All 108 are listed in
[audit-omniroute-ja-sample.md](audit-omniroute-ja-sample.md). Examples: terminal as 端子,
DEF (default) as 守備, Health as 健康, the API path chat/completions as チャット/補完,
Never as 決してしない, and values that are the key name itself (`Flow Spawn`).

My reading of 30 random flags: about 20 real errors, 6 debatable, 4 style remarks the reviewer
was told not to make (されました versus 済み, 空の versus 空). Not yet judged by a native speaker.

## 2026-11-19: blind 0-100 scoring by a second model (Opus 5.5)

`services/score`: the scorer sees English, translation and code, never the reviewer's findings
or the labels, and rates every string from 0 (fine) to 100 (clearly wrong). One run.

Known truth (`injected.ja.jsonl`, 276 strings, 56 wrong):

| threshold | flagged | precision | recall |
|---:|---:|---:|---:|
| 41 | 56 | 1.000 | 1.000 |
| 61 | 54 | 1.000 | 0.964 |
| 81 | 48 | 1.000 | 0.857 |

AUROC 1.0: the lowest score of a wrong string is 50, the highest score of a correct one is 40.
This set is easy, so it shows the scale is used consistently, not that the scorer is perfect.

Japanese field audit (the same 2,000 OmniRoute strings):

| | 0-20 | 21-40 | 41-60 | 61-80 | 81-100 |
|---|---:|---:|---:|---:|---:|
| 108 strings the reviewer flagged | 0 | 0 | 30 | 45 | 33 |
| 1,892 strings it did not flag | 1,376 | 324 | 91 | 28 | 73 |

- No reviewer flag was scored as fine. 78 of 108 (72%) are rated wrong (61 or more); the other
  30 are rated "unnatural but the meaning survives", which matches the style remarks seen by hand.
- The scorer rates 101 unflagged strings at 61 or more. Most are not sense errors but values
  that were never translated: the key's own name (`accountId` for Account ID), the English left
  as it is, or a translation of a placeholder English string (`Mcp Card Description`). These
  are detectable without a model.

Limits: the scorer and the reviewer are models from the same family, so agreement between them
is weaker evidence than a native speaker's judgment. No human has judged these strings.

## 2026-11-19: second scorer from another vendor (Codex, gpt-6-astra, high effort)

Known truth (`injected.ja.jsonl`): Codex and Opus 5.5 each rate the same 54 of 56 wrong strings
at 61 or more, with no correct string above 40. Agreement 100%, both AUROC 1.0.

Japanese field audit: Codex scored 68 of the 100 cases (1,360 strings) before the account hit
its usage limit; the other 32 cases are not scored yet (the run resumes where it stopped).

| on the 1,360 strings both scored | count |
|---|---:|
| both rate it wrong (61+) | 70 |
| only Opus rates it wrong | 29 |
| only Codex rates it wrong | 26 |
| neither | 1,235 |

Agreement on wrong / not wrong 96.0%, Cohen's kappa 0.70, Spearman correlation of the scores
0.78, median score difference 5 points (90th percentile 18).

- Of the 55 disputed strings, 27 are rated at least "unnatural" by both: the two agree that
  something is off and differ on how bad it is (55 against 70). 21 are real disagreements,
  where one scorer says fine (20 or less).
- Of the reviewer's findings in this part: 43 confirmed by both, 15 disputed, 8 unnatural, 0 fine.
- 57 of the 70 confirmed errors need a model; 13 are also caught by the deterministic rules.
- Half of the rule hits (16 of 31) are disputed: one scorer accepts a camelCase identifier such
  as `accountId` as the label for "Account ID". A rule decides this the same way every time.

Security note: the first Codex runs used the default tool set under a read-only sandbox, which
turned out to allow reading local files. All acting tools are disabled now and
`services/llm_codex/eval_isolation.py` checks it. The notes Codex returned in those runs were
scanned: 1,360 notes, longest 42 characters, none with paths, keys or other foreign content.

## 2026-11-19: the command end to end

`l10n_lint.py check` on three sections of OmniRoute's `ja.json` (346 strings, 19 model calls,
Claude scorer, code context): 34 fail, 45 warn, 267 ok. A second run made 0 calls (cache).
Failures include NPM as 故宮, Anthropic as 人間的, About as 約について, running as 走っている.

Scoring prompt version 2 (adds a `fix` field) on the known-truth benchmark, default Claude
model: precision 1.0, recall 0.964, no false alarms (`scripts/eval.sh`).
