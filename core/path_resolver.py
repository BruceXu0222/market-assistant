"""
数据文件路径解析
===============

功能：
1. 根据 market 解析 HK/US 历史日线 Parquet 文件路径
2. 检查文件是否存在
3. 列出 HK/US 文件内可用交易日

数据目录结构（示例）：
data/
  hk/
    腾讯控股.parquet
    ...
  us/
    苹果.parquet
    ...
"""

from functools import lru_cache
from typing import List, Optional
from pathlib import Path
import glob

import duckdb

# TODO: from loguru import logger

# ============================================================================
# 配置（可移至配置文件）
# ============================================================================

# 数据根目录
DATA_ROOT = Path(__file__).parent.parent / "data"

DAILY_HISTORY_MARKETS = ["HK", "US"]
SUPPORTED_MARKETS = {"HK", "US", "ALL"}


# ============================================================================
# 路径解析器
# ============================================================================

class PathResolver:
    """
    数据文件路径解析器

    使用方式：
        resolver = PathResolver()
        paths = resolver.resolve("20250115", "HK")
    """

    def __init__(self, data_root: Optional[Path] = None):
        """
        初始化路径解析器

        Args:
            data_root: 数据根目录（默认使用 DATA_ROOT）

        TODO:
        1. 从配置文件读取 data_root
        """

        self.data_root = data_root or DATA_ROOT

        # 确保目录存在
        if not self.data_root.exists():
            # TODO: 添加日志
            # logger.warning(f"[PathResolver] 数据根目录不存在: {self.data_root}")
            pass

    def resolve(self, date: str, market: str) -> List[str]:
        """
        解析 Parquet 文件路径

        Args:
            date: 交易日（格式：YYYYMMDD）
            market: 市场代码（HK/US/ALL）

        Returns:
            paths: Parquet 文件路径列表

        Raises:
            FileNotFoundError: 文件不存在
        """

        paths = []

        market = market.upper()
        if market not in SUPPORTED_MARKETS:
            raise ValueError(f"Invalid market code: {market}. Supported markets: HK/US/ALL")

        # HK/US 目录中每只股票一个历史日线 parquet，文件本身包含日期列。
        # 返回 glob pattern，避免把几百个股票文件展开成很长的 UNION SQL。
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
        """
        检查指定日期的数据是否存在

        Args:
            date: 交易日（格式：YYYYMMDD）
            market: 市场代码（HK/US/ALL）

        Returns:
            bool: 数据是否存在
        """

        try:
            normalized = str(date).replace("-", "").replace("/", "")[:8]
            return normalized in self.list_available_dates(market)
        except (FileNotFoundError, ValueError):
            return False

    def list_available_dates(self, market: str) -> List[str]:
        """
        列出可用的交易日

        Args:
            market: 市场代码（HK/US/ALL）

        Returns:
            dates: 交易日列表（格式：YYYYMMDD）
        """

        market = market.upper()
        if market not in SUPPORTED_MARKETS:
            raise ValueError(f"Invalid market code: {market}. Supported markets: HK/US/ALL")

        return list_available_daily_history_dates(str(self.data_root), market)

    def latest_available_date(self, market: str = "ALL") -> Optional[str]:
        """返回指定市场可用的最新交易日（YYYYMMDD）。"""
        dates = self.list_available_dates(market)
        return dates[-1] if dates else None


# ============================================================================
# 辅助函数
# ============================================================================

def resolve_parquet_paths(date: str, market: str) -> List[str]:
    """
    便捷函数：解析 Parquet 文件路径

    Args:
        date: 交易日（格式：YYYYMMDD）
        market: 市场代码（HK/US/ALL）

    Returns:
        paths: Parquet 文件路径列表
    """
    resolver = PathResolver()
    return resolver.resolve(date, market)


@lru_cache(maxsize=16)
def list_available_daily_history_dates(data_root: str, market: str) -> List[str]:
    """
    从 HK/US 历史日线 parquet 中读取可用日期。

    这些文件不是按日期分区的，所以需要查看文件内的 ``日期`` 列。DuckDB 会做列裁剪，
    只扫描日期列，成本比加载整表低很多。
    """
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
            SELECT REPLACE(COALESCE(CAST("日期" AS VARCHAR), CAST("date" AS VARCHAR)), '-', '') AS date
            FROM parquet_scan({quoted_pattern}, union_by_name=true)
            WHERE COALESCE(CAST("日期" AS VARCHAR), CAST("date" AS VARCHAR)) IS NOT NULL
            """)
        else:
            selects.append(f"""
            SELECT REPLACE(CAST("日期" AS VARCHAR), '-', '') AS date
            FROM parquet_scan({quoted_pattern})
            WHERE "日期" IS NOT NULL
            """)

    sql = f"""
    SELECT DISTINCT date
    FROM ({' UNION ALL '.join(selects)}) AS dates
    ORDER BY date
    """

    with duckdb.connect(":memory:") as conn:
        rows = conn.execute(sql).fetchall()

    return [row[0] for row in rows]


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    # 测试路径解析
    print("测试路径解析器...")

    resolver = PathResolver()
    print(f"数据根目录: {resolver.data_root}")

    # 测试解析（需要实际数据文件）
    try:
        paths = resolver.resolve("20250115", "HK")
        print(f"找到 {len(paths)} 个文件:")
        for path in paths[:3]:  # 只显示前 3 个
            print(f"  - {path}")
    except FileNotFoundError as e:
        print(f"文件不存在（预期）: {e}")

    # 测试列出可用日期
    dates = resolver.list_available_dates("ALL")
    if dates:
        print(f"\n可用交易日（前 10 个）: {dates[:10]}")
    else:
        print("\n未找到可用交易日（请添加数据文件）")
