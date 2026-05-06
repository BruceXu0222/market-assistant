from pathlib import Path
from time import sleep

import akshare as ak


hk_stocks = {
"00005": "汇丰控股",
"00016": "新鸿基地产",
"00020": "商汤-W",
"00027": "银河娱乐",
"00168": "青岛啤酒股份",
"00175": "吉利汽车",
"00241": "阿里健康",
"00268": "金蝶国际",
"00285": "比亚迪电子",
"00291": "华润啤酒",
"00322": "康师傅控股",
"00388": "香港交易所",
"00493": "国美零售",
"00520": "呷哺呷哺",
"00656": "复星国际",
"00700": "腾讯控股",
"00728": "中国电信",
"00751": "创维集团",
"00753": "中国国航",
"00762": "中国联通",
"00763": "中兴通讯",
"00772": "阅文集团",
"00780": "同程旅行",
"00788": "中国铁塔",
"00868": "信义玻璃",
"00873": "世茂服务",
"00883": "中国海洋石油",
"00909": "明源云",
"00914": "海螺水泥",
"00939": "建设银行",
"00941": "中国移动",
"00981": "中芯国际",
"00991": "大唐发电",
"00992": "联想集团",
"00998": "中信银行",
"01024": "快手-W",
"01060": "大麦娱乐",
"01093": "石药集团",
"01138": "中远海能",
"01179": "华住集团-S",
"01211": "比亚迪股份",
"01288": "农业银行",
"01299": "友邦保险",
"01347": "华虹半导体",
"01357": "美图公司",
"01368": "特步国际",
"01385": "上海复旦",
"01398": "工商银行",
"01458": "周黑鸭",
"01516": "融创服务",
"01579": "颐海国际",
"01658": "邮储银行",
"01772": "赣锋锂业",
"01797": "东方甄选",
"01810": "小米集团-W",
"01816": "中广核电力",
"01833": "平安好医生",
"01876": "百威亚太",
"01896": "猫眼娱乐",
"01918": "融创中国",
"01919": "中远海控",
"01928": "金沙中国有限公司",
"01929": "周大福",
"02007": "碧桂园",
"02013": "微盟集团",
"02015": "理想汽车-W",
"02018": "瑞声科技",
"02020": "安踏体育",
"02057": "中通快递-W",
"02150": "奈雪的茶",
"02196": "复星医药",
"02202": "万科企业",
"02269": "药明生物",
"02318": "中国平安",
"02319": "蒙牛乳业",
"02331": "李宁",
"02333": "长城汽车",
"02359": "药明康德",
"02382": "舜宇光学科技",
"02400": "心动公司",
"02423": "贝壳-W",
"02600": "中国铝业",
"02618": "京东物流",
"02628": "中国人寿",
"02899": "紫金矿业",
"03323": "中国建材",
"03328": "交通银行",
"03690": "美团-W",
"03888": "金山软件",
"03900": "绿城中国",
"03968": "招商银行",
"03988": "中国银行",
"03998": "波司登",
"06049": "保利物业",
"06098": "碧桂园服务",
"06185": "康希诺生物",
"06186": "中国飞鹤",
"06618": "京东健康",
"06690": "海尔智家",
"06862": "海底捞",
"06865": "福莱特玻璃",
"06969": "思摩尔国际",
"09618": "京东集团-SW",
"09626": "哔哩哔哩-W",
"09633": "农夫山泉",
"09696": "天齐锂业",
"09698": "万国数据-SW",
"09866": "蔚来-SW",
"09868": "小鹏集团-W",
"09888": "百度集团-SW",
"09901": "新东方-S",
"09922": "九毛九",
"09961": "携程集团-S",
"09987": "百胜中国",
"09988": "阿里巴巴-W",
"09992": "泡泡玛特",
"09999": "网易-S",
}


OUTPUT_DIR = Path(__file__).resolve().parent / "hk"
START_DATE = "19700101"
END_DATE = "22220101"
PERIOD = "daily"
ADJUST = "qfq"
REQUEST_DELAY_SECONDS = 0.2


def safe_filename(name: str) -> str:
    """Keep stock names usable as filenames on common filesystems."""
    invalid_chars = '<>:"/\\|?*'
    return "".join("_" if char in invalid_chars else char for char in name).strip()


def fetch_stock_history(symbol: str):
    return ak.stock_hk_hist(
        symbol=symbol,
        period=PERIOD,
        start_date=START_DATE,
        end_date=END_DATE,
        adjust=ADJUST,
    )


def save_all_hk_stocks() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    failures = []

    for index, (symbol, stock_name) in enumerate(hk_stocks.items(), start=1):
        output_path = OUTPUT_DIR / f"{safe_filename(stock_name)}.parquet"
        print(f"[{index}/{len(hk_stocks)}] Fetching {symbol} {stock_name}")

        try:
            stock_df = fetch_stock_history(symbol)
            stock_df.insert(0, "stock_name", stock_name)
            stock_df.insert(0, "symbol", symbol)
            stock_df.to_parquet(output_path, index=False)
            print(f"Saved {len(stock_df)} rows to {output_path}")
        except Exception as exc:
            failures.append((symbol, stock_name, str(exc)))
            print(f"Failed {symbol} {stock_name}: {exc}")

        sleep(REQUEST_DELAY_SECONDS)

    if failures:
        print("\nFailed stocks:")
        for symbol, stock_name, error in failures:
            print(f"- {symbol} {stock_name}: {error}")
        raise SystemExit(1)

    print(f"\nDone. Saved {len(hk_stocks)} parquet files in {OUTPUT_DIR}")


if __name__ == "__main__":
    save_all_hk_stocks()
