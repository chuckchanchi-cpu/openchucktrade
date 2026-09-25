"""Jev (TypeSafe) decision gate — quote sanity checks for OpenChuckTrade.

Jev is a decision-only model ("System One"): no chat, just calibrated
probabilities over typed questions. Via OpenRouter's /api/alpha/decisions.

Question types: noul (boolean), choice, score.
Response: answers.<name>.<type> = P(true) for noul.

Cost: ~$0.000014 per call — effectively free at eval scale.
"""
import json
import os
import tomllib
import urllib.request

OPENROUTER_URL = "https://openrouter.ai/api/alpha/decisions"
MODEL = "jev-latest"  # resolves to typesafe/jev-1.13-<date>

_NAME_MAP = {
    "371": "北控水務", "855": "中國水務", "968": "信義光能", "3800": "協鑫科技",
    "763": "中興通訊", "2382": "舜宇光學", "1211": "比亞迪", "9888": "百度",
    "9988": "阿里巴巴", "6030": "中信証券", "388": "港交所", "700": "騰訊",
    "1918": "融創中國", "2007": "碧桂園", "9880": "優必選", "600089": "特變電工",
    "2230": "科大訊飛", "6680": "金力永磁", "31": "—", "2522": "—", "2587": "—",
}


def _key():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, ".streamlit", "secrets.toml"), "rb") as f:
        return tomllib.load(f)["openrouter"]["api_key"]


def ask(state, questions, timeout=30):
    """One Jev decisions call. questions = {name: {type, question, instructions}}."""
    body = json.dumps({"model": MODEL, "state": state, "questions": questions}).encode()
    req = urllib.request.Request(
        OPENROUTER_URL, data=body, method="POST",
        headers={"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def quote_ok(code, price, last_price, known_codes=None):
    """Jev noul gate: is this quote plausible? Returns (prob_true, raw)."""
    known_codes = known_codes or set(_NAME_MAP)
    state = (
        f"HK stock quote check.\n"
        f"Code: {code} ({_NAME_MAP.get(code, 'unknown')}).\n"
        f"New quote price: {price}.\n"
        f"Last known price for {code}: {last_price}."
    )
    instr = (
        "A quote is PLAUSIBLE only if ALL of: "
        "(1) the code is a real stock code in the known list; "
        "(2) the price is a positive number in a sane range for this stock; "
        "(3) the price is not drastically different from the last known price "
        "(moves >20% in one quote are suspicious UNLESS the stock is a small-cap "
        "under ~5 HKD, where bigger moves are normal); "
        "(4) no obvious typo like a missing decimal point (e.g. 88.55 vs 8855) "
        "or a 10x/100x scale error. "
        "HARD RULES: if the price is not a number (it may literally be the string "
        "'abc' or '?'), answer 0. If the code is not in the known list, answer 0. "
        "Answer 0 means NOT plausible, answer 1 means plausible."
    )
    res = ask(
        state,
        {"plausible": {"type": "noul", "question": "Is this quote plausible?",
                       "instructions": instr}},
    )
    return res["answers"]["plausible"]["noul"], res


if __name__ == "__main__":
    import sys
    code, price, last = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    p, raw = quote_ok(code, price, last)
    print(f"P(plausible) = {p:.3f}  (model {raw['model']}, cost ${raw['usage']['cost']:.8f})")