"""Jev vs rule-based baseline — quote sanity gate eval (100 cases).

Ground truth labels: 1 = plausible/OK, 0 = suspicious.
Rule baseline: code known + price>0 + |move| <= 20% -> OK.
Jev: noul probability; threshold 0.5 -> OK.

Metrics: accuracy, false-accept (bad passed), false-reject (good blocked),
Jev calibration (does P=0.9x mean ~90% true?).
"""
import json
import random
import time

import jev_gate

KNOWN = set(jev_gate._NAME_MAP)
LAST = {  # last known prices (from quotes.json 09-24)
    "371": 1.585, "855": 4.22, "968": 1.975, "3800": 0.75, "763": 22.6,
    "2382": 65.0, "1211": 80.35, "9888": 88.55, "9988": 109.8, "6030": 25.32,
    "388": 395.8, "700": 441.0, "9880": 79.05, "6680": 15.38, "2522": 5.26,
    "2587": 0.725,
}


def cases():
    """(label, code, price, last, note) — 100 cases."""
    C = []
    # 1) valid quotes, small moves (40)
    for code, last in list(LAST.items())[:40]:
        for i, d in enumerate((0.001, 0.005, 0.012, 0.03, 0.08, 0.15, 0.19, 0.0)):
            if len(C) >= 40:
                break
            C.append((1, code, round(last * (1 + d), 3), last, f"move {d:.1%}"))
    # 2) typo: missing decimal point (8)
    C += [(0, "9888", 8855, 88.55, "typo x100"),
          (0, "763", 226, 22.6, "typo x10"),
          (0, "1211", 8035, 80.35, "typo x100"),
          (0, "388", 3958, 395.8, "typo x10"),
          (0, "2382", 650, 65.0, "typo x10"),
          (0, "968", 197.5, 1.975, "typo x100"),
          (0, "700", 4410, 441.0, "typo x10"),
          (0, "6030", 25.32, 253.2, "typo /10")]
    # 3) scale errors 10x/100x (8)
    C += [(0, "9988", 1098.0, 109.8, "x10"),
          (0, "2522", 0.0526, 5.26, "x0.01"),
          (0, "2587", 7.25, 0.725, "x10"),
          (0, "6680", 153.8, 15.38, "x10"),
          (0, "9880", 790.5, 79.05, "x10"),
          (0, "855", 0.0422, 4.22, "x0.01"),
          (0, "371", 0.01585, 1.585, "x0.01"),
          (0, "3800", 7.5, 0.75, "x10")]
    # 4) big moves >20% — suspicious (10)
    C += [(0, "9888", 62.0, 88.55, "-30%"),
          (0, "1211", 112.0, 80.35, "+39%"),
          (0, "2382", 45.0, 65.0, "-31%"),
          (0, "388", 550.0, 395.8, "+39%"),
          (0, "763", 30.0, 22.6, "+33%"),
          (0, "700", 350.0, 441.0, "-21%"),
          (0, "6680", 11.0, 15.38, "-28%"),
          (0, "9880", 100.0, 79.05, "+26%"),
          (0, "6030", 18.0, 25.32, "-29%"),
          (0, "9988", 140.0, 109.8, "+27%")]
    # 5) boundary ~20% (6)
    C += [(1, "9888", 88.55 * 1.199, 88.55, "+19.9% edge"),
          (1, "763", 22.6 * 0.801, 22.6, "-19.9% edge"),
          (0, "388", 395.8 * 1.201, 395.8, "+20.1% edge"),
          (0, "1211", 80.35 * 0.799, 80.35, "-20.1% edge"),
          (1, "2587", 0.725 * 1.19, 0.725, "+19% small-cap"),
          (1, "3800", 0.75 * 0.81, 0.75, "-19% small-cap")]
    # 6) unknown code / garbage (7)
    C += [(0, "99999", 10.0, None, "unknown code"),
          (0, "ABC", 10.0, None, "non-numeric code"),
          (0, "1211", "abc", None, "non-numeric price"),
          (0, "1211", -5.0, 80.35, "negative price"),
          (0, "1211", 0.0, 80.35, "zero price"),
          (0, "9888", None, 88.55, "missing price"),
          (1, "600089", 18.11, 18.11, "SH code unchanged")]
    # 7) small-cap legit volatility (7)
    C += [(1, "2587", 0.725 * 1.25, 0.725, "small-cap +25% ok"),
          (1, "2587", 0.725 * 0.78, 0.725, "small-cap -22% ok"),
          (1, "3800", 0.75 * 1.22, 0.75, "small-cap +22% ok"),
          (1, "968", 1.975 * 1.21, 1.975, "small-cap +21% ok"),
          (1, "371", 1.585 * 1.23, 1.585, "small-cap +23% ok"),
          (1, "855", 4.22 * 0.79, 4.22, "small-cap -21% ok"),
          (1, "2522", 5.26 * 1.2, 5.26, "small-cap +20% ok")]
    # 8) alias codes (7)
    C += [(1, "0371", 1.585, 1.585, "alias leading zero"),
          (1, "371.HK", 1.585, 1.585, "alias .HK"),
          (1, "HK.371", 1.585, 1.585, "alias HK."),
          (1, "600089.SS", 18.11, 18.11, "alias .SS"),
          (1, "00700", 441.0, 441.0, "alias leading zeros"),
          (1, "9888", 88.55, 88.55, "unchanged"),
          (1, "9988", 109.8, 109.8, "unchanged")]
    # 9) stable large caps unchanged-ish (7)
    C += [(1, "700", 441.5, 441.0, "+0.1%"),
          (1, "388", 396.0, 395.8, "+0.05%"),
          (1, "1211", 80.0, 80.35, "-0.4%"),
          (1, "6030", 25.5, 25.32, "+0.7%"),
          (1, "9880", 79.1, 79.05, "+0.06%"),
          (1, "6680", 15.4, 15.38, "+0.1%"),
          (1, "2382", 65.2, 65.0, "+0.3%")]
    random.seed(42)
    random.shuffle(C)
    return C


def norm(c):
    c = str(c).strip().upper().replace(".HK", "").replace(".SS", "").replace(".SZ", "")
    for pfx in ("HK.", "SH.", "SZ."):
        if c.startswith(pfx):
            c = c[len(pfx):]
    if c.isdigit() and len(c) >= 4 and c.startswith("0"):
        c = c.lstrip("0")
    return c


def rule_gate(code, price, last):
    if price is None or last is None:
        return 0
    try:
        price = float(price)
    except (TypeError, ValueError):
        return 0
    if price <= 0:
        return 0
    if norm(code) not in KNOWN:
        return 0
    if abs(price - last) / last > 0.20:
        return 0
    return 1


def main():
    cs = cases()
    print(f"total cases: {len(cs)}  (pos={sum(1 for c in cs if c[0])}, neg={sum(1 for c in cs if not c[0])})")
    # rule baseline
    r_acc = r_fa = r_fr = 0
    for label, code, price, last, note in cs:
        pred = rule_gate(code, price, last)
        r_acc += pred == label
        r_fa += pred == 1 and label == 0
        r_fr += pred == 0 and label == 1
    n = len(cs)
    print(f"\nRULE BASELINE: acc={r_acc/n:.1%}  false-accept={r_fa}  false-reject={r_fr}")
    # jev
    j_acc = j_fa = j_fr = 0
    buckets = {}
    for label, code, price, last, note in cs:
        try:
            p, raw = jev_gate.quote_ok(code, price if price is not None else "?", last if last is not None else "?")
        except Exception as e:
            print("ERR", code, price, e)
            continue
        pred = 1 if p >= 0.5 else 0
        j_acc += pred == label
        j_fa += pred == 1 and label == 0
        j_fr += pred == 0 and label == 1
        b = round(p * 10) / 10
        buckets.setdefault(b, [0, 0])
        buckets[b][0] += 1
        buckets[b][1] += label
        time.sleep(0.05)
    print(f"\nJEV (thr=0.5): acc={j_acc/n:.1%}  false-accept={j_fa}  false-reject={j_fr}")
    print("\ncalibration (bucket: n, P(true)):")
    for b in sorted(buckets):
        cnt, tru = buckets[b]
        if cnt:
            print(f"  P~{b:.1f}: n={cnt:3d}  actual={tru/cnt:.0%}")


if __name__ == "__main__":
    main()