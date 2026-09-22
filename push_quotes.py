#!/usr/bin/env python3
"""Push quotes to the app: local API (tunnel version) + repo quotes.json (Cloud version).

Usage:
  python3 push_quotes.py '{"371": 1.55, "9888": 90.0}'
  python3 push_quotes.py 371 1.55 9888 90.0
"""
import json
import os
import subprocess
import sys
import urllib.request

BASE = os.path.dirname(os.path.abspath(__file__))
QUOTES_FILE = os.path.join(BASE, "data", "quotes.json")


def main():
    if len(sys.argv) == 2 and sys.argv[1].lstrip().startswith("{"):
        new = json.loads(sys.argv[1])
    else:
        args = sys.argv[1:]
        new = {args[i]: float(args[i + 1]) for i in range(0, len(args), 2)}
    if not new:
        print("no quotes given"); sys.exit(1)

    cur = {}
    if os.path.exists(QUOTES_FILE):
        with open(QUOTES_FILE, "r", encoding="utf-8") as f:
            cur = json.load(f)
    cur.update(new)

    # 1) local API -> tunnel-hosted app
    with open(os.path.join(BASE, "data", "api_key.txt")) as f:
        key = f.read().strip()
    req = urllib.request.Request(
        "http://localhost:8502/quote",
        data=json.dumps({"quotes": new}).encode(),
        headers={"Content-Type": "application/json", "x-api-key": key},
        method="POST",
    )
    print("local API:", json.loads(urllib.request.urlopen(req, timeout=10).read()))

    # 2) repo quotes.json -> Streamlit Cloud app
    with open(QUOTES_FILE, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=2)
    subprocess.run(["git", "add", "data/quotes.json"], cwd=BASE, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "📈 Update quotes.json"], cwd=BASE, check=True)

    cred = subprocess.run(
        ["/mnt/c/Windows/System32/cmd.exe", "/c", "cd /d C:\\ && git credential fill"],
        input="protocol=https\nhost=github.com\n\n",
        capture_output=True, text=True, cwd="/mnt/c", timeout=30,
    )
    token = [l.split("=", 1)[1] for l in cred.stdout.splitlines()
             if l.startswith("password=")][0].strip()
    helper = f"!f() {{ echo username=chuckchanchi-cpu; echo password={token}; }}; f"
    subprocess.run(
        ["git", "-c", f"credential.helper={helper}", "push", "origin", "main"],
        cwd=BASE, check=True, timeout=60,
    )
    print("✅ quotes.json committed & pushed (cloud app will pick it up within 15s)")


if __name__ == "__main__":
    main()
