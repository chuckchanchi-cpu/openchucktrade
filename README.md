# 🦞 OpenChuckTrade

**Owner**: Chuck (@chuck)  
**Created**: 2026-09-22  
**Repo**: `chuckchanchi-cpu/openchucktrade` (private)

Personal trading record & analysis project. Track pair trades (Sell/Buy legs), P/L, and holding status over time.

## 📁 Structure

```
openchucktrade/
├── data/                 # 交易紀錄 (trading records, xlsx)
│   └── Record_Sept-22.xlsx
├── README.md
└── LICENSE
```

## 📊 Data format (Record_Sept-22.xlsx)

- **Header row**: Base / Now / Change — e.g. HS index reference (25,566 → 24,800, -3.00%)
- **Trade blocks**: date, Sell/Buy leg prices & quantities, Stock qty, Earn (P/L per trade + running cumulative)
- **Status tags**: `H` = open/held position, `TRADE` = closed (realized)

## 🚀 Upload 步驟

1. `git pull --rebase` (保護機制，防止覆蓋手動改動)
2. Add / commit / push

---

_由 OpenClaw 🦞 維護_
