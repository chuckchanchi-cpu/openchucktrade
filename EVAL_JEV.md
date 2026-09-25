# Jev vs Rule-Based — Quote Sanity Gate (2026-09-26)

First real eval of [Jev](https://openrouter.ai) (typesafe/jev-1.13, decision-only
model) against a 10-line rule baseline, on 100 labelled quote-sanity cases.

## Setup
- Task: given `code price` + last known price → plausible? (boolean)
- Jev via OpenRouter `/api/alpha/decisions` (noul type = P(true))
- 100 cases: valid moves / typos (8855) / 10x-100x scale errors / >20% moves /
  boundary ±20% / small-cap high-vol / unknown codes / non-numeric & missing
  prices / code aliases (0371, 371.HK, HK.371, 600089.SS)
- Rule baseline: known code + numeric price > 0 + |Δ| ≤ 20%
- Cost: ~$0.000014/call → **100 calls ≈ $0.0014**

## Results (threshold 0.5)
| | accuracy | false-accept (bad passed) | false-reject (good blocked) |
|---|---|---|---|
| Rule | 94% | 0 | 6 |
| Jev v1 | 93% | 3 | 4 |
| Jev v2 (hard rules in prompt) | 93% | **0** | 7 |

- v1 blind spots: accepted `abc` price (P=0.57) and a *missing* price (P=0.61) —
  fixed by explicit HARD RULES in the instructions ("if price is not a number,
  answer 0").
- Jev understands small-cap volatility better than the rule (accepted some >20%
  moves for sub-5 HKD stocks), but still over-rejects (fr=7 vs rule 6) and is
  wary of SH code 600089 and `.SS` aliases.
- Calibration: P≤0.2 buckets well calibrated (actual ≈ 6–12%);
  0.4–0.6 overconfident (actual 75–100% vs stated 40–60%).

## Verdict
For this hard-checks task, a 10-line rule ties/beats Jev. Jev is not magic on
well-defined checks — its value should be on **fuzzy decisions with criteria**,
not type checks.

## Next candidates
1. **Ledger-upload triage**: when a new xlsx arrives → classify full-replacement
   vs partial working copy; flag direction ambiguities (e.g. the 09-23
   9888/9880 flip saga).
2. Pair-level exit/hold read (needs price history context).