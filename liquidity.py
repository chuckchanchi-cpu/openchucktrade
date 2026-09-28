"""HK stock-market liquidity squeeze tracker — data fetcher.

Sources (all free / keyless):
  L1 Price of liquidity : HKMA daily page (O/N + 1M HIBOR, Base Rate, TWI) + Yahoo (USDHKD)
  L2 Quantity of liquidity : HKMA daily page (Aggregate Balance, Discount Window, forecast)
  L3 Market depth / flows : eastmoney kamt (Stock Connect south/north net buy)
  L4 Cross-asset stress : Yahoo ^HSI (close, %chg, 52w position)
"""
import json
import re
import urllib.request
import datetime as dt

import yfinance as yf

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
HKMA_URL = ("https://www.hkma.gov.hk/eng/data-publications-and-research/"
            "data-and-statistics/daily-monetary-statistics/")
KAMT_URL = ("https://push2his.eastmoney.com/api/qt/kamt.kline/get?"
            "fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56&klt=101&lmt=6"
            "&ut=b2884a393a59ad64002292a3e90d46a5")


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "ignore")


def _flat_text(html):
    """Crude HTML -> '|'-separated text (values sit right after labels)."""
    t = re.sub(r"<script.*?</script>", " ", html, flags=re.S)
    t = re.sub(r"<[^>]+>", "|", t)
    t = re.sub(r"\|+", "|", t)
    t = re.sub(r"\s+", " ", t)
    return t


def _num_after(text, label, offset=0):
    """Find `label` then the first number token after it (skip CN parenthetical)."""
    i = text.find(label)
    if i < 0:
        return None
    seg = text[i + len(label): i + len(label) + 160]
    m = re.search(r"[+\-]?\s?([\d,]+\.?\d*)", seg)
    return float(m.group(1).replace(",", "")) if m else None


def fetch_hkma():
    """L1/L2: HIBOR, Base Rate, TWI, Aggregate Balance, Discount Window."""
    text = _flat_text(_get(HKMA_URL))
    m = re.search(r"(\d{2}:\d{2}),?\s*(\d{2}/\d{2}/\d{4})", text)
    asof = m.group(2) if m else _today()
    # Discount Window Reversal may have tags between '-' and digits
    dw_rev = _num_after(text, "Discount Window Reversal")
    seg = text[text.find("Discount Window Reversal"): text.find("Discount Window Reversal") + 120]
    if re.search(r"-\s*\|?\s*\d", seg):
        dw_rev = -abs(dw_rev or 0)
    return {
        "asof": asof,
        "hibor_on": _num_after(text, "Today's Overnight HIBOR"),
        "hibor_1m": _num_after(text, "1-Month HIBOR Fixing"),
        "base_rate": _num_after(text, "Base Rate"),
        "twi": _num_after(text, "TWI"),
        "ab_open": _num_after(text, "Opening Aggregate Balance"),
        "ab_close": _num_after(text, "Closing Aggregate Balance"),
        "dw_today": _num_after(text, "Discount Window Today"),
        "dw_reversal": dw_rev,
        "usdhkd_offer": _num_after(text, "Offer Rate"),
        "usdhkd_bid": _num_after(text, "Bid Rate"),
    }


def _today():
    return dt.date.today().isoformat()


def fetch_usdhkd():
    h = yf.Ticker("HKD=X").history(period="5d")
    if h.empty:
        return None
    return float(h["Close"].iloc[-1])


def fetch_hsi():
    h = yf.Ticker("^HSI").history(period="1y")
    closes = h["Close"].dropna()
    if len(closes) < 3:
        return None
    last, prev = float(closes.iloc[-1]), float(closes.iloc[-2])
    hi, lo = float(closes.max()), float(closes.min())
    return {
        "close": last,
        "chg_pct": (last / prev - 1) * 100 if prev else 0.0,
        "hi52": hi,
        "lo52": lo,
        "pos52": (last - lo) / (hi - lo) if hi > lo else 0.5,
    }


def fetch_connect():
    """L3: Stock Connect net buy (元). s2n = southbound total, n2s = northbound total.
    Row format: "date,f52,f53,f54" where f54 = 当日成交净买额 (元)."""
    try:
        d = json.loads(_get(KAMT_URL))
        out = {"south": [], "north": []}
        for key, target in (("s2n", "south"), ("n2s", "north")):
            for row in d.get("data", {}).get(key, []) or []:
                p = row.split(",")
                if len(p) >= 4:
                    out[target].append({"date": p[0], "net_buy": float(p[3])})
        return out
    except Exception:
        return {"south": [], "north": []}


def snapshot():
    """Full snapshot dict for one day."""
    hkma = fetch_hkma()
    usdhkd = fetch_usdhkd()
    hsi = fetch_hsi()
    conn = fetch_connect()

    south = conn["south"][-1] if conn["south"] else None
    south_3d = sum(r["net_buy"] for r in conn["south"][-3:]) if len(conn["south"]) >= 3 else None
    north = conn["north"][-1] if conn["north"] else None

    # ---- squeeze gauge ----
    score, flags = 0, []
    if usdhkd:
        band_pos = (7.85 - usdhkd) / 0.10  # 1.0 = strong side, 0 = weak side
        if band_pos < 0.05:
            score += 35; flags.append("USDHKD 貼死弱方 7.85（兌換保證觸發邊緣）")
        elif band_pos < 0.20:
            score += 20; flags.append("USDHKD 偏弱方（港元資金外流壓力）")
    if hkma.get("hibor_on") and hkma.get("base_rate"):
        spread = hkma["hibor_on"] - hkma["base_rate"]
        if spread > 0.5:
            score += 35; flags.append(f"O/N HIBOR 高過 Base Rate {spread:.2f}pt（銀行缺水）")
        elif spread > 0:
            score += 25; flags.append("O/N HIBOR 高過 Base Rate")
    if hkma.get("ab_close") is not None:
        if hkma["ab_close"] < 50000:
            score += 25; flags.append(f"Aggregate Balance 得 {hkma['ab_close']/1000:.0f}bn（歷史低位區）")
        elif hkma["ab_close"] < 100000:
            score += 15; flags.append(f"Aggregate Balance {hkma['ab_close']/1000:.0f}bn（偏低）")
    if hkma.get("dw_today") and hkma["dw_today"] > 0:
        score += 10; flags.append("貼現窗有拆借（銀行要問金管局攞錢）")
    if south_3d is not None and south_3d < 0:
        score += 15; flags.append("南向資金連續3日淨流出")
    elif south and south["net_buy"] < 0:
        score += 10; flags.append("南向資金單日淨流出")
    if hsi:
        if hsi["pos52"] < 0.10:
            score += 15; flags.append("恒指喺52週低位附近")
        elif hsi["pos52"] < 0.25:
            score += 10; flags.append("恒指偏近52週低位")

    return {
        "ts": dt.datetime.now().isoformat(timespec="seconds"),
        "hkma": hkma,
        "usdhkd": usdhkd,
        "band_pos": (7.85 - usdhkd) / 0.10 if usdhkd else None,
        "hsi": hsi,
        "connect": {"south": south, "north": north, "south_3d": south_3d},
        "gauge": min(score, 100),
        "flags": flags,
    }


def gauge_label(score):
    if score >= 70:
        return "🔴 擠壓中（Squeeze）"
    if score >= 50:
        return "🟠 明顯收緊"
    if score >= 25:
        return "🟡 輕微收緊"
    return "🟢 流動性正常"


if __name__ == "__main__":
    s = snapshot()
    print(json.dumps(s, ensure_ascii=False, indent=1))