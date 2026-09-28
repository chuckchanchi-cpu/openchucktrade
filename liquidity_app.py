"""港股流動性擠壓追蹤器 — Streamlit app (5-layer framework, HK version).

Run: streamlit run liquidity_app.py --server.port 8504
"""
import json
import os
import datetime as dt

import streamlit as st
from streamlit_autorefresh import st_autorefresh

import liquidity

BASE = os.path.dirname(os.path.abspath(__file__))
HIST = os.path.join(BASE, "data", "hk_liquidity_history.json")


def load_hist():
    try:
        return json.load(open(HIST))
    except Exception:
        return []


def save_hist(snap):
    hist = load_hist()
    today = dt.date.today().isoformat()
    hist = [h for h in hist if h.get("date") != today]
    hist.append({"date": today, **snap})
    json.dump(hist[-120:], open(HIST, "w"), ensure_ascii=False)


st.set_page_config(page_title="港股流動性擠壓追蹤器", page_icon="🌊", layout="wide")
st.title("🌊 港股流動性擠壓追蹤器")
st.caption("對照 Chuck 個 framework 嘅香港版：5 層 liquidity squeeze 指標,每日 19:00 後更新（HKMA + Yahoo + eastmoney,全部免費源）")

auto = st.toggle("自動刷新（30 分鐘）", value=False)
if auto:
    st_autorefresh(interval=30 * 60 * 1000, key="liqref")

@st.cache_data(ttl=1800, show_spinner="拉緊數據中…")
def get_snap():
    return liquidity.snapshot()

snap = get_snap()
save_hist(snap)
hist = load_hist()

# ---------- header: gauge ----------
score = snap["gauge"]
label = liquidity.gauge_label(score)
c1, c2 = st.columns([1, 2])
with c1:
    st.metric("Squeeze Gauge", f"{score}/100", label)
    st.progress(score / 100)
with c2:
    if snap["flags"]:
        st.markdown("**⚠️ 觸發咗嘅警號：**")
        for f in snap["flags"]:
            st.markdown(f"- {f}")
    else:
        st.success("冇觸發警號")

st.divider()

# ---------- Layer 1 ----------
h = snap["hkma"]
st.subheader("① 資金的價格（最快訊號）")
l1 = st.columns(5)
l1[0].metric("O/N HIBOR", f"{h['hibor_on']:.2f}%" if h.get("hibor_on") else "—",
             delta=f"Base Rate {h.get('base_rate','—')}%" if h.get("hibor_on") and h.get("base_rate") else None)
l1[1].metric("1M HIBOR", f"{h['hibor_1m']:.3f}%" if h.get("hibor_1m") else "—")
l1[2].metric("USDHKD", f"{snap['usdhkd']:.4f}" if snap.get("usdhkd") else "—",
             delta=f"弱方 7.85,相隔 {(7.85-snap['usdhkd'])*1000:.1f} 點" if snap.get("usdhkd") else None)
l1[3].metric("兌換保證帶位置", f"{snap['band_pos']*100:.0f}%" if snap.get("band_pos") is not None else "—",
             delta="0% = 貼弱方 7.85" if snap.get("band_pos") is not None else None, delta_color="inverse")
l1[4].metric("港匯指數 TWI", f"{h['twi']:.1f}" if h.get("twi") else "—")

# ---------- Layer 2 ----------
st.subheader("② 資金的數量（金管局池）")
l2 = st.columns(4)
ab = h.get("ab_close")
l2[0].metric("Aggregate Balance 收市", f"HK${ab/1000:,.1f}bn" if ab else "—",
             delta=f"開市 {h.get('ab_open',0)/1000:,.1f}bn" if h.get("ab_open") else None)
l2[1].metric("貼現窗今日運作", f"HK${h.get('dw_today',0)/1000:,.1f}bn" if h.get("dw_today") is not None else "—",
             delta=">0 = 銀行要問金管局借錢" if (h.get("dw_today") or 0) > 0 else None, delta_color="inverse")
l2[2].metric("貼現窗退還", f"HK${h.get('dw_reversal',0)/1000:,.1f}bn" if h.get("dw_reversal") is not None else "—")
l2[3].metric("基本利率 Base Rate", f"{h.get('base_rate','—')}%")
st.caption(f"HKMA 數據日期：{h.get('asof')}　參考：AB 低過 HK$100bn = 偏低,低過 HK$50bn = 歷史低位區（2024 年曾跌到 ~HK$45bn）")

# ---------- Layer 3 ----------
st.subheader("③ 市場深度 / 資金流向")
conn = snap["connect"]
l3 = st.columns(3)
s = conn.get("south") or {}
n = conn.get("north") or {}
l3[0].metric("南向淨買額（今日）", f"{s.get('net_buy',0)/1e8:+.1f} 億" if s else "—", f"{s.get('date','')}")
l3[1].metric("南向 3 日累計", f"{conn.get('south_3d',0)/1e8:+.1f} 億" if conn.get("south_3d") is not None else "—")
l3[2].metric("北向淨買額（今日）", f"{n.get('net_buy',0)/1e8:+.1f} 億" if n else "—", f"{n.get('date','')}")
st.caption("負數連續 3 日 = 外資/內資持續抽水,係流動性 drain 訊號")

# ---------- Layer 4 ----------
st.subheader("④ 跨資產壓力")
hsi = snap.get("hsi")
l4 = st.columns(4)
if hsi:
    l4[0].metric("恒指", f"{hsi['close']:,.0f}", f"{hsi['chg_pct']:+.2f}%")
    l4[1].metric("52 週高位", f"{hsi['hi52']:,.0f}")
    l4[2].metric("52 週低位", f"{hsi['lo52']:,.0f}")
    l4[3].metric("52 週位置", f"{hsi['pos52']*100:.0f}%", "0% = 喺低位")
else:
    st.warning("恒指數據暫時攞唔到")

# ---------- trend charts ----------
if len(hist) >= 2:
    st.divider()
    st.subheader("📈 近期走勢（歷史快照累積中）")
    dates = [x["date"] for x in hist]
    tc = st.columns(3)
    with tc[0]:
        vals = [x.get("gauge", 0) for x in hist]
        st.line_chart({"Squeeze Gauge": vals}, x=dates)
        st.caption("Gauge: 0-25 正常 / 25-50 輕微 / 50-70 收緊 / 70+ 擠壓")
    with tc[1]:
        abv = [ (x.get("hkma") or {}).get("ab_close", 0) / 1000 for x in hist]
        st.line_chart({"Aggregate Balance (bn)": abv}, x=dates)
    with tc[2]:
        ud = [x.get("usdhkd") or 7.8 for x in hist]
        st.line_chart({"USDHKD": ud}, x=dates)
    with tc[0]:
        sb = [(x.get("connect") or {}).get("south") or {} for x in hist]
        sbv = [ (r.get("net_buy") or 0) / 1e8 for r in sb if r]
        if sbv:
            st.line_chart({"南向淨買額(億)": sbv}, x=dates[-len(sbv):])
    with tc[1]:
        hb = [(x.get("hkma") or {}).get("hibor_on") for x in hist]
        if any(v is not None for v in hb):
            st.line_chart({"O/N HIBOR %": [v or 0 for v in hb]}, x=dates)

st.divider()
st.caption("⚠️ 僅供參考,唔係投資建議。數據源：HKMA（官方）、Yahoo Finance、東方財富（滬深港通）。南向/北向為當日成交淨買額（元）。")