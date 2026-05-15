"""Resolve HK and US parquet data paths and available trading dates."""

from functools import lru_cache
from typing import List, Optional
from pathlib import Path
import glob

import duckdb


CN_DATE = "\u65e5\u671f"
DATA_ROOT = Path(__file__).parent.parent / "data"

DAILY_HISTORY_MARKETS = ["HK", "US"]
SUPPORTED_MARKETS = {"HK", "US", "ALL"}


class PathResolver:
    """Resolve data file patterns for supported markets."""

    def __init__(self, data_root: Optional[Path] = None):
        """Initialize the resolver."""

        self.data_root = Path(data_root) if data_root is not None else DATA_ROOT

        if not self.data_root.exists():
            pass

    def resolve(self, date: str, market: str) -> List[str]:
        """Return parquet scan patterns for a date and market."""

        paths = []

        market = market.upper()
        if market not in SUPPORTED_MARKETS:
            raise ValueError(f"Invalid market code: {market}. Supported markets: HK/US/ALL")

        markets_to_scan = DAILY_HISTORY_MARKETS if market == "ALL" else [market]
        for mkt in markets_to_scan:
            market_dir = "hk" if mkt == "HK" else "us"
            pattern_path = self.data_root / market_dir / "*.parquet"
            if glob.glob(str(pattern_path)):
                paths.append(str(pattern_path))

        if not paths:
            raise FileNotFoundError(
                f"No data files found: date={date}, market={market}\n"
                f"Please check the data directory: {self.data_root}"
            )

        return paths

    def check_date_exists(self, date: str, market: str) -> bool:
        """Return whether a market has data for a trading date."""

        try:
            normalized = str(date).replace("-", "").replace("/", "")[:8]
            return normalized in self.list_available_dates(market)
        except (FileNotFoundError, ValueError):
            return False

    def list_available_dates(self, market: str) -> List[str]:
        """List available trading dates for a market."""

        market = market.upper()
        if market not in SUPPORTED_MARKETS:
            raise ValueError(f"Invalid market code: {market}. Supported markets: HK/US/ALL")

        return list_available_daily_history_dates(str(self.data_root), market)

    def latest_available_date(self, market: str = "ALL") -> Optional[str]:
        """Return the latest available trading date for a market."""
        dates = self.list_available_dates(market)
        return dates[-1] if dates else None


def resolve_parquet_paths(date: str, market: str) -> List[str]:
    """Resolve parquet scan patterns with a default resolver."""
    resolver = PathResolver()
    return resolver.resolve(date, market)


@lru_cache(maxsize=16)
def list_available_daily_history_dates(data_root: str, market: str) -> List[str]:
    """Read available trading dates from per-stock daily-history parquet files."""
    root = Path(data_root)
    market = market.upper()
    patterns = []

    if market in {"HK", "ALL"} and (root / "hk").exists():
        patterns.append(str(root / "hk" / "*.parquet"))
    if market in {"US", "ALL"} and (root / "us").exists():
        patterns.append(str(root / "us" / "*.parquet"))

    if not patterns:
        return []

    selects = []
    for pattern in patterns:
        quoted_pattern = "'" + pattern.replace("'", "''") + "'"
        if "/us/" in pattern.replace("\\", "/").lower():
            selects.append(f"""
            SELECT REPLACE(COALESCE(CAST("{CN_DATE}" AS VARCHAR), CAST("date" AS VARCHAR)), '-', '') AS date
            FROM parquet_scan({quoted_pattern}, union_by_name=true)
            WHERE COALESCE(CAST("{CN_DATE}" AS VARCHAR), CAST("date" AS VARCHAR)) IS NOT NULL
            """)
        else:
            selects.append(f"""
            SELECT REPLACE(CAST("{CN_DATE}" AS VARCHAR), '-', '') AS date
            FROM parquet_scan({quoted_pattern})
            WHERE "{CN_DATE}" IS NOT NULL
            """)

    sql = f"""
    SELECT DISTINCT date
    FROM ({' UNION ALL '.join(selects)}) AS dates
    ORDER BY date
    """

    with duckdb.connect(":memory:") as conn:
        rows = conn.execute(sql).fetchall()

    return [row[0] for row in rows]


if __name__ == "__main__":
    resolver = PathResolver()
    print(f"Data root: {resolver.data_root}")

    try:
        paths = resolver.resolve("20250115", "HK")
        print(f"Found {len(paths)} file patterns:")
        for path in paths[:3]:
            print(f"  - {path}")
    except FileNotFoundError as e:
        print(f"No files found: {e}")

    dates = resolver.list_available_dates("ALL")
    if dates:
        print(f"\nAvailable trading dates, first 10: {dates[:10]}")
    else:
        print("\nNo available trading dates found")
