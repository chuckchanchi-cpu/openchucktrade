# 🦞 OpenChuckTrade

**Owner**: Chuck (@chuck)  
**Created**: 2026-09-22  
**Repo**: `chuckchanchi-cpu/openchucktrade` (private)

Personal trading record & analysis project. Track pair trades (Sell/Buy legs), P/L, and holding status over time.

## 📁 Structure

```
openchucktrade/
├── app.py                # 🦞 對沖監察 Streamlit app (manual price input -> profitable pair flags)
├── pairs.py              # xlsx -> open pairs parser (pair P/L model)
├── requirements.txt
├── data/                 # 交易紀錄 (trading records, xlsx)
│   ├── Record_Sept-22.xlsx
│   └── now_prices.json   # 本地暫存嘅最新價格 (auto-generated)
├── README.md
└── LICENSE
```

## 🦞 Monitor App

```bash
pip install -r requirements.txt
streamlit run app.py
```

- Input the latest price of each stock (manual), or bulk-paste `code price` lines (openD/fring1118 攞價後貼入)
- Live P/L per pair: **buy leg** = (now − bought) × qty · **sell leg** = (sold − now) × qty
- ✅ **Profitable pair** = both legs positive (Chuck's definition)
- Prices persist locally in `data/now_prices.json`

## 📊 Data format (Record_Sept-22.xlsx)

- **Header row**: Base / Now / Change — e.g. HS index reference (25,566 → 24,800, -3.00%)
- **Trade blocks**: date, Sell/Buy leg prices & quantities, Stock qty, Earn (P/L per trade + running cumulative)
- **Status tags**: `H` = open/held position, `TRADE` = closed (realized)

## 🚀 Upload 步驟

1. `git pull --rebase` (保護機制，防止覆蓋手動改動)
2. Add / commit / push

---

_由 OpenClaw 🦞 維護_
