"""
Generate US stock mock market data.

The generated Parquet uses the same column layout and dtypes as the existing
Chinese stock mock data in data/test.parquet, so the current SQL compiler can
query it without US-specific branches.
"""

from pathlib import Path

import numpy as np
import pandas as pd


US_STOCKS = [
    ("AAPL", "Apple Inc."),
    ("MSFT", "Microsoft Corp."),
    ("NVDA", "NVIDIA Corp."),
    ("AMZN", "Amazon.com Inc."),
    ("GOOGL", "Alphabet Inc."),
    ("META", "Meta Platforms Inc."),
    ("TSLA", "Tesla Inc."),
    ("AVGO", "Broadcom Inc."),
    ("JPM", "JPMorgan Chase & Co."),
    ("LLY", "Eli Lilly and Co."),
    ("V", "Visa Inc."),
    ("UNH", "UnitedHealth Group Inc."),
    ("XOM", "Exxon Mobil Corp."),
    ("MA", "Mastercard Inc."),
    ("COST", "Costco Wholesale Corp."),
    ("HD", "Home Depot Inc."),
    ("PG", "Procter & Gamble Co."),
    ("NFLX", "Netflix Inc."),
    ("CRM", "Salesforce Inc."),
    ("AMD", "Advanced Micro Devices Inc."),
]


def _snapshot_times(num_snapshots: int) -> list[str]:
    """Return evenly spaced US regular-session snapshot times."""

    candidates = [
        "093000000",
        "100000000",
        "103000000",
        "110000000",
        "113000000",
        "120000000",
        "123000000",
        "130000000",
        "133000000",
        "140000000",
        "143000000",
        "150000000",
        "153000000",
        "155900000",
    ]
    return candidates[:num_snapshots]


def _empty_record(template_columns: list[str]) -> dict:
    return {column: np.nan for column in template_columns}


def generate_us_mock_data(
    trading_day: str = "20250120",
    num_snapshots_per_stock: int = 8,
    output_dir: str = "data/US_Stock_Snapshot_Level2_Day",
    template_path: str = "data/test.parquet",
    seed: int = 2026,
) -> pd.DataFrame:
    """
    Generate US stock level-2 style snapshots and save them as partitioned Parquet.

    Args:
        trading_day: Trading day in YYYYMMDD format.
        num_snapshots_per_stock: Number of intraday snapshots per ticker.
        output_dir: Market directory under data/.
        template_path: Existing Parquet file used for column order and dtypes.
        seed: Random seed for deterministic mock data.
    """

    rng = np.random.default_rng(seed)
    template = pd.read_parquet(template_path)
    columns = list(template.columns)
    records = []

    for stock_idx, (ticker, symbol) in enumerate(US_STOCKS):
        pre_close = rng.uniform(35, 950)
        open_px = pre_close * rng.uniform(0.985, 1.02)
        cumulative_volume = 0.0
        cumulative_value = 0.0
        high_seen = open_px
        low_seen = open_px

        for snapshot_idx, mdtime in enumerate(_snapshot_times(num_snapshots_per_stock)):
            intraday_drift = rng.normal(0.0008, 0.012) * (snapshot_idx + 1)
            last_px = max(1.0, open_px * (1 + intraday_drift))
            high_seen = max(high_seen, last_px * rng.uniform(1.0, 1.015))
            low_seen = min(low_seen, last_px * rng.uniform(0.985, 1.0))

            snapshot_volume = rng.integers(60_000, 1_800_000)
            cumulative_volume += float(snapshot_volume)
            cumulative_value += float(snapshot_volume * last_px)

            spread = max(0.01, last_px * rng.uniform(0.0001, 0.0015))
            bid1 = last_px - spread / 2
            ask1 = last_px + spread / 2

            record = _empty_record(columns)
            record.update(
                {
                    "MDDate": trading_day,
                    "MDTime": mdtime,
                    "SecurityType": 2,
                    "SecuritySubType": "US01",
                    "SecurityID": ticker,
                    "SecurityIDSource": 840,
                    "Symbol": symbol,
                    "TradingPhaseCode": "REG",
                    "PreClosePx": round(pre_close, 2),
                    "NumTrades": int(rng.integers(5_000, 550_000)),
                    "TotalVolumeTrade": round(cumulative_volume, 2),
                    "TotalValueTrade": round(cumulative_value, 2),
                    "LastPx": round(last_px, 2),
                    "OpenPx": round(open_px, 2),
                    "ClosePx": round(last_px, 2),
                    "HighPx": round(high_seen, 2),
                    "LowPx": round(low_seen, 2),
                    "DiffPx1": round(last_px - pre_close, 2),
                    "DiffPx2": round((last_px - pre_close) / pre_close * 100, 4),
                    "MaxPx": round(pre_close * 1.2, 2),
                    "MinPx": round(pre_close * 0.8, 2),
                    "AfterHoursNumTrades": 0.0,
                    "AfterHoursTotalVolumeTrade": 0.0,
                    "AfterHoursTotalValueTrade": 0.0,
                    "HTSCSecurityID": f"{ticker}.US",
                    "ReceiveDateTime": int(f"{trading_day}{mdtime[:6]}{snapshot_idx:03d}"),
                    "ChannelNo": 8401,
                }
            )

            total_bid_qty = 0.0
            total_offer_qty = 0.0
            for level in range(1, 11):
                bid_price = max(0.01, bid1 - (level - 1) * spread)
                ask_price = ask1 + (level - 1) * spread
                bid_qty = float(rng.integers(100, 20_000))
                ask_qty = float(rng.integers(100, 20_000))
                total_bid_qty += bid_qty
                total_offer_qty += ask_qty

                record[f"Buy{level}Price"] = round(bid_price, 2)
                record[f"Buy{level}OrderQty"] = bid_qty
                record[f"Buy{level}NumOrders"] = float(rng.integers(1, 80))
                record[f"Sell{level}Price"] = round(ask_price, 2)
                record[f"Sell{level}OrderQty"] = ask_qty
                record[f"Sell{level}NumOrders"] = float(rng.integers(1, 80))

            record["Buy1NoOrders"] = record["Buy1NumOrders"]
            record["Sell1NoOrders"] = record["Sell1NumOrders"]
            record["Buy1OrderDetail"] = None
            record["Sell1OrderDetail"] = None
            record["TotalBidQty"] = round(total_bid_qty, 2)
            record["TotalOfferQty"] = round(total_offer_qty, 2)
            record["WeightedAvgBidPx"] = round(bid1 - spread * 2, 2)
            record["WeightedAvgOfferPx"] = round(ask1 + spread * 2, 2)

            records.append(record)

    df = pd.DataFrame(records, columns=columns)

    for column, dtype in template.dtypes.items():
        if column in df.columns:
            try:
                df[column] = df[column].astype(dtype)
            except (TypeError, ValueError):
                pass

    output_path = Path(output_dir) / f"tradingday={trading_day}" / "part-00000.parquet"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)

    print(f"Generated {len(df)} US stock records")
    print(f"Stocks: {len(US_STOCKS)}")
    print(f"Snapshots per stock: {num_snapshots_per_stock}")
    print(f"Output: {output_path}")

    return df


if __name__ == "__main__":
    generate_us_mock_data()
