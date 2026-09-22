"""Auto-fetch latest quotes (sina hq API) and push into the app.

Covers HK (rt_hkXXXXX) + A-shares (sz/sh). Run:
  python3 fetch_quotes.py        # one-shot
  python3 fetch_quotes.py 30     # loop every 30s
"""
import json
import os
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
API = "http://localhost:8502/quote"

STOCKS = {
    "371": "rt_hk00371", "855": "rt_hk00855", "968": "rt_hk00968",
    "9888": "rt_hk09888", "9988": "rt_hk09988", "700": "rt_hk00700",
    "3800": "rt_hk03800", "2382": "rt_hk02382", "763": "rt_hk00763",
    "1211": "rt_hk01211", "6680": "rt_hk06680", "9880": "rt_hk09880",
    "2230": "sz002230", "600089": "sh600089",
}


def _key():
    with open(os.path.join(BASE, "data", "api_key.txt")) as f:
        return f.read().strip()


def fetch():
    codes = ",".join(STOCKS.values())
    req = urllib.request.Request(
        f"https://hq.sinajs.cn/list={codes}",
        headers={"Referer": "https://finance.sina.com.cn"},
    )
    raw = urllib.request.urlopen(req, timeout=15).read().decode("gbk", "ignore")
    quotes = {}
    for line in raw.splitlines():
        if "=" not in line:
            continue
        var, payload = line.split("=", 1)
        sym = var.replace("var hq_str_", "").replace("rt_", "").strip()
        fields = payload.strip('";\n').split(",")
        if len(fields) < 10:
            continue
        try:
            price = float(fields[9]) if sym.startswith("hk") else float(fields[3])
        except (ValueError, IndexError):
            continue
        if price > 0:
            for code, s in STOCKS.items():
                if s.replace("rt_", "") == sym:
                    quotes[code] = price
    return quotes


def push(quotes):
    body = json.dumps({"quotes": quotes}).encode()
    req = urllib.request.Request(
        API, data=body, method="POST",
        headers={"Content-Type": "application/json", "x-api-key": _key()},
    )
    return json.loads(urllib.request.urlopen(req, timeout=10).read())


if __name__ == "__main__":
    interval = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    while True:
        try:
            q = fetch()
            r = push(q)
            print(time.strftime("%H:%M:%S"), "fetched", len(q),
                  "pushed", r.get("updated"), flush=True)
        except Exception as e:
            print(time.strftime("%H:%M:%S"), "ERR", e, flush=True)
        if not interval:
            break
        time.sleep(interval)
