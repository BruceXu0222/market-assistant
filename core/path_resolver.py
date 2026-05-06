"""
数据文件路径解析
===============

功能：
1. 根据 date/market 解析 Parquet 文件路径
2. 检查文件是否存在
3. 支持模糊匹配（例如：tradingday=YYYYMMDD/*.parquet）

数据目录结构（示例）：
data/
  XSHG_Stock_Snapshot_Level2_Day/
    tradingday=20250115/
      part-00000.parquet
      part-00001.parquet
  XSHE_Stock_Snapshot_Level2_Day/
    tradingday=20250115/
      part-00000.parquet
      part-00001.parquet
  US_Stock_Snapshot_Level2_Day/
    tradingday=20250120/
      part-00000.parquet
"""

from typing import List, Optional
from pathlib import Path
import glob

# TODO: from loguru import logger

# ============================================================================
# 配置（可移至配置文件）
# ============================================================================

# 数据根目录
DATA_ROOT = Path(__file__).parent.parent / "data"

# 市场数据目录模板
MARKET_DIR_TEMPLATES = {
    "XSHG": "XSHG_Stock_Snapshot_Level2_Day",
    "XSHE": "XSHE_Stock_Snapshot_Level2_Day",
    "US": "US_Stock_Snapshot_Level2_Day",
}

CHINA_MARKETS = ["XSHG", "XSHE"]


# ============================================================================
# 路径解析器
# ============================================================================

class PathResolver:
    """
    数据文件路径解析器

    使用方式：
        resolver = PathResolver()
        paths = resolver.resolve("20250115", "XSHG")
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
            market: 市场代码（XSHG/XSHE/US/ALL）

        Returns:
            paths: Parquet 文件路径列表

        Raises:
            FileNotFoundError: 文件不存在

        TODO:
        1. 实现路径解析逻辑
        2. 支持 glob 模式匹配
        3. 添加缓存（避免重复扫描）
        4. 添加日志
        """

        paths = []

        # 根据 market 确定需要扫描的目录
        if market == "ALL":
            markets_to_scan = CHINA_MARKETS
        else:
            markets_to_scan = [market]

        # 遍历市场目录
        for mkt in markets_to_scan:
            market_dir = MARKET_DIR_TEMPLATES.get(mkt)
            if not market_dir:
                # logger.warning(f"[PathResolver] 未知市场代码: {mkt}")
                continue

            # 构建路径：data_root / market_dir / tradingday=YYYYMMDD / *.parquet
            pattern = str(self.data_root / market_dir / f"tradingday={date}" / "*.parquet")

            # glob 匹配
            matched_files = glob.glob(pattern)

            if not matched_files:
                # TODO: 添加日志
                # logger.warning(f"[PathResolver] 未找到文件: {pattern}")
                pass
            else:
                paths.extend(matched_files)
                # logger.info(f"[PathResolver] 找到 {len(matched_files)} 个文件: {pattern}")

        # 如果没有找到任何文件，抛出异常
        if not paths:
            raise FileNotFoundError(
                f"未找到数据文件: date={date}, market={market}\n"
                f"请检查数据目录: {self.data_root}"
            )

        return paths

    def check_date_exists(self, date: str, market: str) -> bool:
        """
        检查指定日期的数据是否存在

        Args:
            date: 交易日（格式：YYYYMMDD）
            market: 市场代码（XSHG/XSHE/US/ALL）

        Returns:
            bool: 数据是否存在

        TODO:
        1. 实现存在性检查
        """

        try:
            self.resolve(date, market)
            return True
        except FileNotFoundError:
            return False

    def list_available_dates(self, market: str) -> List[str]:
        """
        列出可用的交易日

        Args:
            market: 市场代码（XSHG/XSHE/US/ALL）

        Returns:
            dates: 交易日列表（格式：YYYYMMDD）

        TODO:
        1. 实现日期列表查询
        2. 添加缓存
        """

        dates = set()

        # 根据 market 确定需要扫描的目录
        if market == "ALL":
            markets_to_scan = CHINA_MARKETS
        else:
            markets_to_scan = [market]

        # 遍历市场目录
        for mkt in markets_to_scan:
            market_dir = MARKET_DIR_TEMPLATES.get(mkt)
            if not market_dir:
                continue

            # 扫描 tradingday=* 目录
            market_path = self.data_root / market_dir
            if not market_path.exists():
                continue

            for trading_day_dir in market_path.glob("tradingday=*"):
                date = trading_day_dir.name.replace("tradingday=", "")
                dates.add(date)

        return sorted(list(dates))


# ============================================================================
# 辅助函数
# ============================================================================

def resolve_parquet_paths(date: str, market: str) -> List[str]:
    """
    便捷函数：解析 Parquet 文件路径

    Args:
        date: 交易日（格式：YYYYMMDD）
        market: 市场代码（XSHG/XSHE/US/ALL）

    Returns:
        paths: Parquet 文件路径列表
    """
    resolver = PathResolver()
    return resolver.resolve(date, market)


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
        paths = resolver.resolve("20250115", "XSHG")
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
