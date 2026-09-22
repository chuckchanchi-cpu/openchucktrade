"""OpenChuckTrade — pair data loader.

Parses Record_Sept-22.xlsx trade blocks into open pairs for the monitor app.

Pair concept (per Chuck):
- Stock 1 (buy leg, kept in wallet): bought at P1, now at N1 -> leg = (N1 - P1) * qty_buy
- Stock 2 (sell leg, sold to fund the buy): sold at P2, now at N2 -> leg = (P2 - N2) * qty_sell
- Pair P/L = buy leg + sell leg. Profitable pair = BOTH legs positive.
"""
import os
import re

import openpyxl

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "Record_Sept-22.xlsx")

NAME_MAP = {
    "371": "北控水務", "855": "中國水務", "968": "信義光能", "3800": "協鑫科技",
    "763": "中興通訊", "2382": "舜宇光學", "1211": "比亞迪", "9888": "百度",
    "9988": "阿里巴巴", "6030": "中信証券", "388": "港交所", "700": "騰訊",
    "1918": "融創中國", "2007": "碧桂園", "9880": "優必選", "600089": "特變電工",
    "2230": "羚邦集團", "6680": "金風科技", "1725": "—", "31": "—", "2522": "—", "2587": "—",
}

CODE_RE = re.compile(r"^(\d{3,6})(\.0)?$")
NAMED_RE = re.compile(r"^(\d{3,6})\s+(BAIDU|Baidu|Bidu)", re.I)
MONEY_RE = re.compile(r"^-?\$ ?([\d,]+\.?\d*)$")
NUM_RE = re.compile(r"^-?\d[\d,]*\.?\d*$")


def _money(v):
    neg = v.startswith("-")
    m = re.search(r"[\d,]+\.?\d*", v)
    return -float(m.group(0).replace(",", "")) if neg else float(m.group(0).replace(",", ""))


def _parse_blocks(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["Sheet1"]
    rows = list(ws.iter_rows(values_only=True))
    blocks, cur = [], None
    for r in rows:
        vals = ["" if c is None else str(c).strip() for c in r]
        if vals[0] == "Sell":
            if cur:
                blocks.append(cur)
            cur = []
        if cur is not None:
            cur.append(vals)
    if cur:
        blocks.append(cur)
    return blocks


def _extract_pair(block):
    p = {
        "date": None, "code1": None, "code2": None, "p1": None, "p2": None,
        "now1": None, "now2": None, "qty_stock": None, "qty_earn": None,
        "buy_leg_stored": None, "sell_leg_stored": None, "pair_pl_stored": None,
        "status": None,
    }
    # date + codes from the first 3 rows, cols 0-1 (stock 1 = sell column, stock 2 = buy column)
    for vals in block[:3]:
        for v in vals:
            m = re.match(r"^(\d{4}-\d{2}-\d{2})", v)
            if m and p["date"] is None:
                p["date"] = m.group(1)
        for v in vals[:2]:
            m = CODE_RE.match(v)
            nm = NAMED_RE.match(v)
            if m and p["code1"] is None:
                p["code1"] = m.group(1)
            elif m and p["code2"] is None and m.group(1) != p["code1"]:
                p["code2"] = m.group(1)
            elif nm:
                c = nm.group(1)
                if p["code1"] is None:
                    p["code1"] = c
                elif p["code2"] is None and c != p["code1"]:
                    p["code2"] = c
    # normalise 60089 -> 600089 (typo seen in the sheet)
    if p["code1"] == "60089":
        p["code1"] = "600089"
    if p["code2"] == "60089":
        p["code2"] = "600089"
    # "$ price" row: two money values + qty + "Stock"
    dollar_rows = []
    for vals in block:
        ms = [_money(v) for v in vals if MONEY_RE.match(v)]
        if len(ms) == 2 and "Stock" in vals:
            dollar_rows.append((vals, ms))
    if dollar_rows:
        vals, ms = dollar_rows[-1]
        p["now1"], p["now2"] = ms
        q = vals[vals.index("Stock") - 1].replace(",", "")
        if NUM_RE.match(q):
            p["qty_stock"] = float(q)
        idx = block.index(vals)
        if idx > 0:
            prev = block[idx - 1]
            if NUM_RE.match(prev[0]) and NUM_RE.match(prev[1]):
                p["p1"] = float(prev[0].replace(",", ""))
                p["p2"] = float(prev[1].replace(",", ""))
    # earn row: leg values + status
    for vals in block:
        if "Earn" in vals:
            q = vals[vals.index("Earn") - 1].replace(",", "")
            if NUM_RE.match(q):
                p["qty_earn"] = float(q)
            fmts = [_money(v) for v in vals if MONEY_RE.match(v)]
            if len(fmts) >= 2:
                p["buy_leg_stored"], p["pair_pl_stored"] = fmts[-2], fmts[-1]
            elif len(fmts) == 1:
                p["buy_leg_stored"] = fmts[0]
            p["status"] = "H" if "H" in vals else ("TRADE" if "TRADE" in vals else "?")
            break
    return p


def _implied_qty(leg_raw, diff):
    """Back out the qty the sheet used for a leg: qty = |leg / price_diff|."""
    if leg_raw is None or diff is None or abs(diff) < 1e-9:
        return None
    q = abs(leg_raw / diff)
    return round(q, 4) if q > 0 else None


def load_pairs(path=None):
    """Return list of open (H) pairs with resolved leg quantities.

    qty_buy / qty_sell are derived from the stored P/L when possible (so the
    app reproduces the sheet exactly), falling back to the listed Stock/Earn
    quantities.
    """
    path = path or DATA_FILE
    pairs = []
    for block in _parse_blocks(path):
        p = _extract_pair(block)
        if p["status"] != "H":
            continue
        if not (p["code1"] and p["code2"] and p["p1"] is not None and p["p2"] is not None):
            continue
        if p["now1"] is None or p["now2"] is None:
            continue
        d1 = p["now1"] - p["p1"]
        d2 = p["p2"] - p["now2"]
        qb = _implied_qty(p["buy_leg_stored"], d1)
        qs = _implied_qty(
            p["pair_pl_stored"] - p["buy_leg_stored"] if p["pair_pl_stored"] is not None else None, d2
        )
        # prefer the listed qty when it matches the implied one
        for listed, implied in ((p["qty_stock"], qb), (p["qty_earn"], qb)):
            if implied is not None and listed is not None and abs(listed - implied) / implied < 0.05:
                qb = listed
                break
        for listed, implied in ((p["qty_stock"], qs), (p["qty_earn"], qs)):
            if implied is not None and listed is not None and abs(listed - implied) / implied < 0.05:
                qs = listed
                break
        p["qty_buy"] = qb if qb is not None else (p["qty_stock"] or 0)
        p["qty_sell"] = qs if qs is not None else (p["qty_earn"] or 0)
        p["name1"] = NAME_MAP.get(p["code1"], "")
        p["name2"] = NAME_MAP.get(p["code2"], "")
        pairs.append(p)
    return pairs


def unique_stocks(pairs):
    """All distinct stock codes across pairs, with their reference (sheet) price."""
    out = {}
    for p in pairs:
        if p["code1"] not in out:
            out[p["code1"]] = {"code": p["code1"], "name": p["name1"], "ref": p["now1"], "pairs": 0}
        if p["code2"] not in out:
            out[p["code2"]] = {"code": p["code2"], "name": p["name2"], "ref": p["now2"], "pairs": 0}
        out[p["code1"]]["pairs"] += 1
        out[p["code2"]]["pairs"] += 1
    return out


def pair_pl(p, prices):
    """Live P/L for a pair given a {code: price} map."""
    n1 = prices.get(p["code1"], p["now1"])
    n2 = prices.get(p["code2"], p["now2"])
    buy_leg = (n1 - p["p1"]) * p["qty_buy"]
    sell_leg = (p["p2"] - n2) * p["qty_sell"]
    return buy_leg, sell_leg, buy_leg + sell_leg
