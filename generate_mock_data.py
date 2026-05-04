"""
生成模拟市场数据
==================

根据示例指标生成 Parquet 格式的测试数据
"""

import pandas as pd
import numpy as np
import os

def generate_mock_data(num_stocks=100, num_snapshots_per_stock=5, output_dir="data"):
    """
    生成模拟市场数据

    参数:
        num_stocks: 股票数量
        num_snapshots_per_stock: 每只股票的快照数量（模拟不同时间点）
        output_dir: 输出目录
    """

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 时间戳列表（从9:30到15:30，每分钟一个快照）
    timestamps = [
        f"{9 + h:02d}{30 + m:02d}{s:02d}000"
        for h in range(6)
        for m in range(0, 60, 60 // num_snapshots_per_stock)
        for s in [0]
    ][:num_snapshots_per_stock]

    data_records = []

    for stock_idx in range(num_stocks):
        security_id = f"{stock_idx:06d}"

        # 为每只股票生成基础价格
        base_price = np.random.uniform(5, 200)
        pre_close_price = base_price * np.random.uniform(0.95, 1.05)

        # 生成多个快照（不同时间点）
        for snapshot_idx, mdtime in enumerate(timestamps):
            # 价格随时间波动
            price_change_factor = 1 + np.random.uniform(-0.05, 0.05)
            close_px = base_price * price_change_factor

            # 计算最高价和最低价
            high_px = close_px * np.random.uniform(1.0, 1.05)
            low_px = close_px * np.random.uniform(0.95, 1.0)

            # 涨跌停价格
            max_px = pre_close_price * 1.1
            min_px = pre_close_price * 0.9

            # 成交量和成交额
            total_volume = np.random.uniform(1e6, 1e8)
            total_value = total_volume * close_px

            # 买卖盘口
            buy1_price = close_px * 0.999
            sell1_price = close_px * 1.001

            record = {
                'MDTime': mdtime,
                'SecurityID': security_id,
                'SecurityType': np.random.choice([1, 2]),  # 1=股票, 2=基金
                'SecuritySubType': np.random.choice(['02001', '02002', '02003']),
                'ClosePx': round(close_px, 2),
                'PreClosePx': round(pre_close_price, 2),
                'HighPx': round(high_px, 2),
                'LowPx': round(low_px, 2),
                'MaxPx': round(max_px, 2),
                'MinPx': round(min_px, 2),
                'TotalVolumeTrade': round(total_volume, 2),
                'TotalValueTrade': round(total_value, 2),
                'Buy1Price': round(buy1_price, 2),
                'Buy1OrderQty': round(np.random.uniform(1e3, 1e5), 2),
                'Buy1NumOrders': float(np.random.randint(1, 50)),
                'Buy2Price': round(buy1_price * 0.999, 2),
                'Buy2OrderQty': round(np.random.uniform(1e3, 1e5), 2),
                'Buy2NumOrders': float(np.random.randint(1, 50)),
                'Buy3Price': round(buy1_price * 0.998, 2),
                'Buy3OrderQty': round(np.random.uniform(1e3, 1e5), 2),
                'Buy3NumOrders': float(np.random.randint(1, 50)),
                'Buy4Price': round(buy1_price * 0.997, 2),
                'Buy4OrderQty': round(np.random.uniform(1e3, 1e5), 2),
                'Buy4NumOrders': float(np.random.randint(1, 50)),
                'Buy5Price': round(buy1_price * 0.996, 2),
                'Buy5OrderQty': round(np.random.uniform(1e3, 1e5), 2),
                'Buy5NumOrders': float(np.random.randint(1, 50)),
                'Sell1Price': round(sell1_price, 2),
                'Sell1OrderQty': round(np.random.uniform(1e3, 1e5), 2),
                'Sell1NumOrders': float(np.random.randint(1, 50)),
                'Sell2Price': round(sell1_price * 1.001, 2),
                'Sell2OrderQty': round(np.random.uniform(1e3, 1e5), 2),
                'Sell2NumOrders': float(np.random.randint(1, 50)),
                'Sell3Price': round(sell1_price * 1.002, 2),
                'Sell3OrderQty': round(np.random.uniform(1e3, 1e5), 2),
                'Sell3NumOrders': float(np.random.randint(1, 50)),
                'Sell4Price': round(sell1_price * 1.003, 2),
                'Sell4OrderQty': round(np.random.uniform(1e3, 1e5), 2),
                'Sell4NumOrders': float(np.random.randint(1, 50)),
                'Sell5Price': round(sell1_price * 1.004, 2),
                'Sell5OrderQty': round(np.random.uniform(1e3, 1e5), 2),
                'Sell5NumOrders': float(np.random.randint(1, 50)),
            }

            data_records.append(record)

    # 创建 DataFrame
    df = pd.DataFrame(data_records)

    # 保存为 Parquet
    output_path = os.path.join(output_dir, "test.parquet")
    df.to_parquet(output_path, index=False)

    print(f"✓ 生成 {len(df)} 条记录")
    print(f"  - 股票数量: {num_stocks}")
    print(f"  - 每只股票快照数: {num_snapshots_per_stock}")
    print(f"  - 输出文件: {output_path}")
    print(f"\n数据样例:")
    print(df.head(3))
    print(f"\n数据统计:")
    print(df.describe())

    return df


if __name__ == "__main__":
    print("="*80)
    print("生成模拟市场数据")
    print("="*80 + "\n")

    df = generate_mock_data(num_stocks=100, num_snapshots_per_stock=5)

    print("\n" + "="*80)
    print("完成！")
    print("="*80)
