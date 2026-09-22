"""OpenChuckTrade Monitor — Streamlit app.

Manual price input -> live pair P/L -> profitable pair flags.
Chuck inputs the latest prices; fring1118/openD can bulk-paste prices too.
"""
import json
import os
import time
import urllib.request

import streamlit as st
from streamlit_autorefresh import st_autorefresh

import pairs as P

PRICE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "now_prices.json")
REMOTE_URL = ("https://raw.githubusercontent.com/chuckchanchi-cpu/"
              "openchucktrade/main/data/quotes.json")

st.set_page_config(page_title="OpenChuckTrade Monitor", page_icon="🦞", layout="wide")

# auto-refresh every 15s so openD-pushed quotes show up without manual reload
st_autorefresh(interval=15000, key="qrefresh")


def file_mtime():
    try:
        return os.path.getmtime(PRICE_FILE)
    except Exception:
        return 0


def load_saved_prices():
    try:
        with open(PRICE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_remote_prices():
    """quotes.json in the repo — the channel that reaches Streamlit Cloud."""
    try:
        with urllib.request.urlopen(REMOTE_URL, timeout=5) as r:
            return json.load(r)
    except Exception:
        return {}


def norm_code(c):
    """0371→371, 00700→700, 002230→2230, HK.0371/0371.HK/371.HK→371, 600089.SS→600089"""
    c = c.strip().upper().replace(".HK", "").replace(".SS", "").replace(".SZ", "")
    for pfx in ("HK.", "SH.", "SZ."):
        if c.startswith(pfx):
            c = c[len(pfx):]
    if c.isdigit() and len(c) >= 4 and c.startswith("0"):
        c = c.lstrip("0")
    return c


def save_prices(prices):
    with open(PRICE_FILE, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=2)


# ---------- load ----------
pair_list = P.load_pairs()
stocks = P.unique_stocks(pair_list)
auto_mode = st.session_state.get("auto_mode", True)
saved = load_saved_prices()
remote = load_remote_prices() if auto_mode else {}
# manual/bulk-applied prices override remote quotes for this session
manual = st.session_state.get("manual_prices", {})

# auto mode: follow pushed quotes — clear stale widget state when prices changed
mtime = file_mtime()
last_mtime = st.session_state.get("last_mtime", 0)
remote_sig = json.dumps(remote, sort_keys=True) if remote else ""
last_remote = st.session_state.get("last_remote", "")
if auto_mode and (mtime != last_mtime or (remote_sig and remote_sig != last_remote)):
    for k in [k for k in list(st.session_state) if k.startswith("px_")]:
        del st.session_state[k]
    st.session_state["last_mtime"] = mtime
    st.session_state["last_remote"] = remote_sig

# merge: manual (session) > pushed quotes (repo quotes.json) > local file > sheet reference
merged = {**saved, **remote, **manual}
prices = {}
for code, info in stocks.items():
    prices[code] = merged.get(code, info["ref"])

# ---------- header ----------
st.title("🦞 OpenChuckTrade — 對沖監察 / Pair Monitor")
st.caption("Input latest prices → live pair P/L → profitable pair flags (both legs green). "
           "Data source: `data/Record_Sept-22.xlsx` · status `H` (open) pairs only")

# ---------- stock price input ----------
c_toggle, c_note = st.columns([1, 3])
with c_toggle:
    auto_mode = st.toggle("🔄 自動跟 openD 報價", value=auto_mode, key="auto_mode")
with c_note:
    if auto_mode:
        note = (f"openD 報價自動更新中（每 15 秒）· 最後更新 "
                f"{time.strftime('%H:%M:%S', time.localtime(mtime)) if mtime else '—'}")
    else:
        note = "已暫停自動同步 — 而家用手動輸入"
    if manual:
        note += f"　⚠️ 手動覆蓋: {', '.join(sorted(manual))}"
    st.caption(note)
st.subheader("📈 最新價格輸入 / Latest prices")
cols = st.columns(4)
new_prices = {}
for i, (code, info) in enumerate(stocks.items()):
    with cols[i % 4]:
        label = f"{code} {info['name']}".strip()
        val = st.number_input(
            label, min_value=0.0, value=float(prices[code]), step=0.01,
            format="%.4f" if float(prices[code]) < 10 else "%.2f",
            key=f"px_{code}",
        )
        new_prices[code] = val

bulk = st.text_area(
    "批量貼上價格 (openD/fring1118 用) — 每行 `代碼 價格`，例如：`371 1.55`",
    height=70, placeholder="371 1.55\n9888 90.0\n700 444.8",
)
if st.button("📋 套用批量價格 / Apply bulk prices") and bulk.strip():
    n_applied = 0
    manual = dict(st.session_state.get("manual_prices", {}))
    for line in bulk.strip().splitlines():
        parts = line.replace(":", " ").split()
        if len(parts) >= 2:
            try:
                code, val = norm_code(parts[0]), float(parts[1])
            except ValueError:
                continue
            if code in new_prices:
                new_prices[code] = val
                manual[code] = val
                n_applied += 1
    if n_applied:
        st.session_state["manual_prices"] = manual
        # re-init price widgets from the merged prices so the applied values show
        for k in [k for k in list(st.session_state) if k.startswith("px_")]:
            del st.session_state[k]
        st.session_state["bulk_notice"] = f"已套用 {n_applied} 個價格（本 session 手動覆蓋，唔會被自動報價冚走）"
        st.rerun()
    else:
        st.warning("冇匹配到任何代碼 — 請檢查格式（每行 `代碼 價格`）")

notice = st.session_state.pop("bulk_notice", None)
if notice:
    st.success(notice)

if manual:
    if st.button("↩️ 清除手動覆蓋 / Clear manual overrides"):
        st.session_state.pop("manual_prices", None)
        for k in [k for k in list(st.session_state) if k.startswith("px_")]:
            del st.session_state[k]
        st.rerun()

prices = new_prices
save_prices(prices)

# ---------- compute ----------
rows = []
for p in pair_list:
    buy_leg, sell_leg, total = P.pair_pl(p, prices)
    rows.append((p, buy_leg, sell_leg, total))

rows.sort(key=lambda r: r[3], reverse=True)
profitable = [r for r in rows if r[1] > 0 and r[2] > 0]
total_pl = sum(r[3] for r in rows)

# ---------- summary ----------
m1, m2, m3, m4 = st.columns(4)
m1.metric("對數 / Pairs", len(rows))
m2.metric("✅ 有利可圖 / Profitable", len(profitable))
m3.metric("總盈虧 / Total P/L", f"${total_pl:,.0f}")
m4.metric("更新時間 / Updated", f"{len(prices)} 個價格")

# ---------- profitable pairs ----------
if profitable:
    st.subheader(f"✅ 有利可圖配對 — BOTH LEGS POSITIVE ({len(profitable)})")
    for p, buy_leg, sell_leg, total in profitable:
        st.success(
            f"**{p['code1']} {p['name1']}** ↔ **{p['code2']} {p['name2']}**"
            f" ｜ 買腿 +${buy_leg:,.0f} ｜ 賣腿 +${sell_leg:,.0f} ｜ **配對 +${total:,.0f}**"
        )

# ---------- all pairs ----------
st.subheader("📊 全部配對 / All pairs")
for p, buy_leg, sell_leg, total in rows:
    flag = "✅" if buy_leg > 0 and sell_leg > 0 else ("⚠️" if total > 0 else "🔴")
    with st.expander(
        f"{flag} {p['code1']} {p['name1']} ↔ {p['code2']} {p['name2']} "
        f"｜ {p['date'] or '—'} ｜ 配對 ${total:,.0f}"
    ):
        c1, c2, c3, c4 = st.columns(4)
        c1.markdown(f"**買腿 Stock 1** (錢包)\n\n買入價 `{p['p1']:.4g}`\n\n數量 `{p['qty_buy']:.0f}`")
        c2.markdown(f"**賣腿 Stock 2** (賣出)\n\n賣出價 `{p['p2']:.4g}`\n\n數量 `{p['qty_sell']:.0f}`")
        c3.markdown(f"**最新價**\n\n`{p['code1']}` → {prices[p['code1']]:.4g}\n\n"
                    f"`{p['code2']}` → {prices[p['code2']]:.4g}")
        leg1 = f"+${buy_leg:,.0f}" if buy_leg >= 0 else f"-${-buy_leg:,.0f}"
        leg2 = f"+${sell_leg:,.0f}" if sell_leg >= 0 else f"-${-sell_leg:,.0f}"
        tot = f"+${total:,.0f}" if total >= 0 else f"-${-total:,.0f}"
        c4.markdown(
            f"**即時盈虧**\n\n買腿 `{leg1}` {'🟢' if buy_leg > 0 else '🔴'}\n\n"
            f"賣腿 `{leg2}` {'🟢' if sell_leg > 0 else '🔴'}\n\n"
            f"**配對 `{tot}`**"
        )

st.caption("💡 提示：價格同步去 `data/quotes.json`（GitHub repo，Streamlit Cloud 版本都讀到）＋本地 `data/now_prices.json`；股票代碼可對應 Yahoo Finance（如 9888.HK、600089.SS）俾 openD 攞價。")
