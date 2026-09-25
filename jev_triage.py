"""Jev ledger-upload triage — classify an uploaded xlsx before applying.

Questions (noul/choice):
- valid_full: is this a structurally complete ledger (real block format,
  prices parse, no missing critical cells)?
- direction_issue: does any pair look direction-ambiguous (e.g. the same two
  codes appear with swapped roles, or stored P/L contradicts entry prices)?
- action: replace / merge / reject / ask-human

Usage: python3 jev_triage.py <xlsx> [--live <xlsx>]
"""
import argparse
import sys

import jev_gate
import pairs as P


def summarize(path):
    """Structural summary of the file for the Jev state."""
    pairs_ = P.load_pairs(path)
    lines = [f"Uploaded file: {path.split('/')[-1]}", f"Sheet: first worksheet",
             f"Open (H) pairs: {len(pairs_)}"]
    for p in pairs_:
        lines.append(
            f"- {p['date']} BUY {p['code1']} @{p['p1']} x{p['qty_buy']} / "
            f"SELL {p['code2']} @{p['p2']} x{p['qty_sell']}"
            f"{' (stored P/L ' + str(p['pair_pl_stored']) + ')' if p['pair_pl_stored'] is not None else ''}"
        )
    return "\n".join(lines)


def triage(path):
    state = summarize(path)
    state += (
        "\n\nThe app tracks ONLY the open (H) pairs above. Closed/TRADE blocks are ignored. "
        "This file may be a full replacement of the whole ledger, a partial working copy, "
        "or contain direction-ambiguous pairs. Evaluate structure and consistency."
    )
    questions = {
        "valid_full": {
            "type": "noul",
            "question": "Is this a structurally complete, usable ledger file?",
            "instructions": (
                "Answer 1 if the file parses into a plausible pair list: every open pair has "
                "a date, two stock codes, two entry prices, and positive quantities; dates are "
                "valid; prices are in sane ranges (HK stocks, 0.01-2000 HKD, 600089 is an "
                "SH stock ~18 CNY). Answer 0 if anything critical is missing (e.g. zero open "
                "pairs, unparseable prices, codes without prices)."
            ),
        },
        "direction_issue": {
            "type": "noul",
            "question": "Does any pair have an ambiguous or suspect direction?",
            "instructions": (
                "Answer 1 if: the same two codes appear as open pairs on the same or nearby "
                "dates with swapped buy/sell roles, OR a stored P/L is positive while both "
                "entry legs suggest heavy loss, OR the buy/sell quantity proportions seem "
                "inverted relative to the entry prices. Otherwise answer 0."
            ),
        },
        "action": {
            "type": "choice",
            "question": "What should the operator do with this file?",
            "instructions": (
                "Choose exactly one: "
                "'replace' = full valid ledger, apply as-is; "
                "'merge' = looks partial or has useful new pairs but should be merged with "
                "the existing live ledger; "
                "'reject' = broken/empty/unparseable, do not apply; "
                "'ask-human' = ambiguous direction or partial status needs the user's call."
            ),
            "criteria": {
                "replace": "full valid ledger, apply as-is",
                "merge": "partial or has new pairs worth merging with live",
                "reject": "broken, empty, unparseable",
                "ask-human": "ambiguous direction or partial status needs the user's call",
            },
        },
    }
    return jev_gate.ask(state, questions)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("xlsx")
    a = ap.parse_args()
    import json
    res = triage(a.xlsx)
    print(json.dumps(res, indent=2, ensure_ascii=False))
    ans = res["answers"]
    for name, q in ans.items():
        if q["type"] == "noul":
            print(f"{name}: P(true) = {q['noul']:.3f}")
        elif q["type"] == "choice":
            print(f"{name}: {q['choice']}")


if __name__ == "__main__":
    main()