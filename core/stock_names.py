"""English display names for stock results."""

from __future__ import annotations

import re
from typing import Any


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


STOCK_NAME_OVERRIDES = {
    "00700": "Tencent Holdings",
    "09988": "Alibaba Group",
    "03690": "Meituan",
    "01810": "Xiaomi Group",
    "00388": "Hong Kong Exchanges and Clearing",
    "00941": "China Mobile",
    "00005": "HSBC Holdings",
    "01299": "AIA Group",
    "02318": "Ping An Insurance",
    "01211": "BYD Company",
    "09618": "JD.com",
    "09888": "Baidu",
    "09866": "NIO",
    "09868": "XPeng",
    "02015": "Li Auto",
    "09999": "NetEase",
    "09626": "Bilibili",
    "09961": "Trip.com Group",
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "TSLA": "Tesla",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet Class A",
    "GOOG": "Alphabet Class C",
    "META": "Meta Platforms",
    "NFLX": "Netflix",
    "AMD": "Advanced Micro Devices",
    "INTC": "Intel",
    "QCOM": "Qualcomm",
    "ORCL": "Oracle",
    "IBM": "IBM",
    "JPM": "JPMorgan Chase",
    "BAC": "Bank of America",
    "C": "Citigroup",
    "GS": "Goldman Sachs",
    "MS": "Morgan Stanley",
    "V": "Visa",
    "MA": "Mastercard",
    "KO": "Coca-Cola",
    "PEP": "PepsiCo",
    "MCD": "McDonald's",
    "SBUX": "Starbucks",
    "DIS": "Disney",
    "NKE": "Nike",
    "BA": "Boeing",
    "GE": "GE Aerospace",
    "XOM": "Exxon Mobil",
    "CVX": "Chevron",
    "JNJ": "Johnson & Johnson",
    "PFE": "Pfizer",
    "MRK": "Merck",
    "LLY": "Eli Lilly",
    "UNH": "UnitedHealth Group",
    "COST": "Costco",
    "WMT": "Walmart",
    "HD": "Home Depot",
    "LOW": "Lowe's",
    "F": "Ford Motor",
    "GM": "General Motors",
}


def has_cjk(value: Any) -> bool:
    """Return True when a value contains CJK characters."""
    return bool(_CJK_RE.search(str(value or "")))


def english_stock_name(security_id: Any, symbol: Any = None) -> str:
    """Return an English display label, falling back to the ticker/code."""
    code = str(security_id or "").strip()
    raw_symbol = str(symbol or "").strip()
    upper_code = code.upper()

    if upper_code in STOCK_NAME_OVERRIDES:
        return STOCK_NAME_OVERRIDES[upper_code]
    if code in STOCK_NAME_OVERRIDES:
        return STOCK_NAME_OVERRIDES[code]
    if raw_symbol and not has_cjk(raw_symbol):
        return raw_symbol
    return code or raw_symbol
