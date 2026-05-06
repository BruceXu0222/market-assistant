from pathlib import Path
from time import sleep

import akshare as ak


us_stocks = {
"BLDP": "巴拉德动力系统",
"INTC": "英特尔",
"AKAM": "阿卡迈",
"DDD": "3D系统",
"MU": "美光科技",
"QCOM": "高通",
"DD": "陶氏杜邦",
"HOG": "哈雷戴维森",
"JACK": "Jack in the Box Inc",
"PLUG": "普拉格能源",
"SBLK": "Star Bulk Carriers Corp",
"SWKS": "思佳讯",
"WDC": "西部数据",
"AMBA": "安霸",
"MT": "安赛乐米塔尔",
"FLEX": "伟创力",
"AMAT": "应用材料",
"A": "安捷伦",
"AAL": "美国航空",
"HPE": "慧与",
"STX": "希捷科技",
"CRUS": "凌云半导体",
"FCEL": "燃料电池能源",
"AMD": "超威半导体",
"NUS": "如新集团",
"CLF": "克利夫兰克里夫",
"GCO": "格涅斯科",
"ADM": "阿彻丹尼尔斯米德兰",
"FCX": "自由港麦克莫兰",
"FSLR": "第一太阳能",
"CEVA": "CEVA Inc",
"LUV": "西南航空",
"LQDT": "Liquidity Services Inc",
"DAL": "达美航空",
"CAT": "卡特彼勒",
"CLDX": "塞德斯医疗",
"STLD": "Steel Dynamics Inc",
"GT": "固特异轮胎橡胶",
"TWLO": "Twilio Inc-A",
"MRVL": "迈威尔科技",
"CAKE": "起司工坊",
"IVZ": "景顺",
"NTAP": "美国网存",
"ORCL": "甲骨文",
"FRO": "Frontline plc",
"HLF": "康宝莱",
"NUE": "纽柯钢铁",
"WYNN": "永利度假村",
"PRU": "保德信金融",
"IBKR": "盈透证券",
"AAPL": "苹果",
"AVGO": "博通",
"LC": "LendingClub Corp",
"BEN": "富兰克林资源",
"RS": "Reliance Steel & Aluminum Co",
"SSYS": "Stratasys Ltd",
"WOR": "Worthington Industries Inc",
"PHM": "普得集团(帕尔迪)",
"DG": "达乐",
"GE": "GE航空航天",
"PRGO": "培瑞克",
"VMI": "维蒙特工业",
"LEN": "莱纳建筑-A",
"ALB": "美国雅保",
"LLY": "礼来",
"EMR": "艾默生电气",
"FMC": "FMC Corp",
"TTD": "The Trade Desk Inc-A",
"IP": "国际纸业",
"MAR": "万豪国际",
"MBI": "MBIA Inc",
"DHI": "霍顿房屋",
"GBX": "格林布赖尔",
"YELP": "Yelp Inc",
"C": "花旗集团",
"LBTYA": "自由全球-A",
"PBI": "必能宝",
"UPS": "联合包裹服务",
"MYGN": "万基遗传",
"CSCO": "思科",
"COLM": "哥伦比亚户外",
"H": "凯悦酒店",
"BAC": "美国银行",
"MNKD": "曼恩凯德生物医疗",
"AMGN": "安进",
"GS": "高盛",
"CF": "CF实业",
"UBS": "瑞银集团",
"AZO": "汽车地带",
"HPQ": "惠普",
"S": "SentinelOne Inc-A",
"F": "福特汽车",
"TOL": "托尔兄弟",
"PNC": "PNC金融服务集团",
"GME": "游戏驿站",
"HSY": "好时",
"AEO": "美鹰傲飞",
"EQR": "公平住屋",
"BYD": "博伊德赌场",
"IMAX": "IMAX Corp",
"BA": "波音",
"DB": "德意志银行",
"GPRO": "GoPro Inc-A",
"FDX": "联邦快递",
"RF": "地区金融",
"LVS": "金沙集团",
"GOOGL": "谷歌-A",
"GLW": "康宁",
"MOS": "美盛",
"GOOG": "谷歌-C",
"MET": "大都会人寿",
"CDNS": "铿腾电子",
"AIG": "美国国际集团",
"YUMC": "百胜中国",
"CL": "高露洁",
"MCO": "穆迪",
"PLD": "安博",
"SHAK": "Shake Shack Inc-A",
"CAG": "康尼格拉",
"WEN": "云狄斯快餐",
"BBQ": "Build-A-Bear Workshop Inc",
"JBLU": "捷蓝航空",
"PG": "宝洁",
"CMG": "墨式烧烤",
"BIIB": "生化基因",
"SCHW": "嘉信理财",
"PSX": "Phillips 66",
"L": "洛斯保险",
"AA": "美国铝业",
"HD": "家得宝",
"LULU": "lululemon athletica inc",
"WMB": "威廉姆斯",
"WFC": "富国银行",
"MMM": "3M公司",
"EXPE": "亿客行",
"APO": "阿波罗全球管理",
"NOV": "NOV Inc",
"M": "梅西百货",
"TGT": "塔吉特",
"CRM": "赛富时",
"MNST": "怪物饮料",
"BAX": "百特国际",
"XOM": "埃克森美孚",
"ADSK": "欧特克",
"FTNT": "防特网",
"TXT": "德事隆",
"GBR": "New Concept Energy Inc",
"VLO": "瓦莱罗能源",
"WY": "惠好",
"BMO": "蒙特利尔银行",
"CSX": "CSX运输",
"LOCO": "El Pollo Loco Holdings Inc",
"KBH": "KB Home",
"LOW": "劳氏",
"SLB": "斯伦贝谢",
"MS": "摩根士丹利",
"ADBE": "奥多比",
"USB": "美国合众银行",
"NEM": "纽蒙特",
"ROST": "罗斯百货",
"ON": "安森美半导体",
"JNJ": "强生",
"KIM": "金克地产",
"GILD": "吉利德科学",
"GM": "通用汽车",
"PFE": "辉瑞",
"JPM": "摩根大通",
"AMZN": "亚马逊",
"TXN": "德州仪器",
"NXPI": "恩智浦半导体",
"DOW": "陶氏",
"ARW": "艾睿电子",
"HLT": "希尔顿酒店",
"CP": "加拿大太平洋堪萨斯城",
"LAND": "Gladstone Land Corp",
"STT": "道富",
"SPG": "西蒙地产",
"CCL": "嘉年华邮轮",
"FPI": "Farmland Partners Inc",
"MCD": "麦当劳",
"KO": "可口可乐",
"BK": "纽约梅隆银行",
"COST": "开市客",
"GIS": "通用磨坊",
"IR": "英格索兰",
"DHR": "丹纳赫",
"JCI": "江森自控",
"ABUS": "Arbutus Biopharma Corp",
"MELI": "MercadoLibre Inc",
"TJX": "The TJX Companies Inc",
"CVX": "雪佛龙",
"PM": "菲利普莫里斯国际",
"SLM": "学贷美",
"MRK": "默沙东",
"CTSH": "高知特",
"GNW": "Genworth金融",
"SBUX": "星巴克",
"CAH": "卡地纳健康",
"MDLZ": "亿滋国际",
"BOX": "Box Inc-A",
"TMUS": "T-Mobile US Inc",
"TRV": "旅行者保险",
"NKE": "耐克",
"BCS": "巴克莱",
"EA": "艺电",
"ZTS": "硕腾",
"COF": "第一资本金融",
"G": "简柏特",
"AN": "车之国",
"IBM": "IBM国际商业机器",
"FOXA": "福克斯-A",
"ISRG": "直觉外科",
"ILMN": "Illumina Inc",
"KGC": "金罗斯黄金",
"FOX": "福克斯-B",
"BX": "黑石集团",
"BLK": "贝莱德",
"YUM": "Yum! Brands Inc",
"VFC": "威富",
"BRK_A": "伯克希尔哈撒韦-A",
"CPRT": "科帕特",
"ABT": "雅培",
"TRIP": "猫途鹰",
"DE": "迪尔",
"VZ": "威瑞森通讯",
"MSFT": "微软",
"KMI": "金德摩根",
"ANF": "阿贝克隆比&费奇",
"ACN": "埃森哲",
"ALL": "好事达保险",
"HAL": "哈里伯顿",
"BBY": "百思买",
"NHTC": "然健环球",
"MDT": "美敦力",
"WU": "西联汇款",
"NTNX": "路坦力",
"BMY": "百时美施贵宝",
"PGR": "前进保险",
"T": "美国电话电报",
"TSLA": "特斯拉",
"DIS": "迪士尼",
"AAP": "Advance Auto Parts Inc",
"MO": "奥驰亚集团",
"MCK": "麦克森",
"MGM": "美高梅",
"TEAM": "Atlassian Corp-A",
"MAT": "美泰",
"ZG": "Zillow Group Inc-A",
"GDDY": "GoDaddy Inc-A",
"SDRL": "Seadrill Ltd",
"KR": "克罗格",
"DXCM": "德康医疗",
"SNAP": "Snap Inc-A",
"REGN": "再生元制药",
"ABBV": "艾伯维",
"NVDA": "英伟达",
"AXP": "美国运通",
"JBL": "捷普",
"LFWD": "Lifeward Ltd",
"Z": "Zillow Group Inc-C",
"LNG": "Cheniere Energy Inc",
"NYT": "纽约时报",
"COP": "康菲石油",
"KKR": "KKR & Co Inc",
"SIRI": "天狼星XM",
"NWSA": "新闻集团-A",
"V": "维萨",
"MA": "万事达",
"BSX": "波士顿科学",
"GOGO": "Gogo Inc",
"CVS": "西维斯健康",
"LMT": "洛克希德马丁",
"UNH": "联合健康",
"CMCSA": "康卡斯特",
"NDAQ": "纳斯达克",
"W": "Wayfair Inc-A",
"GRPN": "Groupon Inc-A",
"NFLX": "奈飞",
"EBAY": "易趣",
"CAR": "安飞士",
"KBR": "KBR科技",
"PYPL": "PayPal Holdings Inc",
"RIG": "越洋钻探",
"NDLS": "Noodles & Co-A",
}


OUTPUT_DIR = Path(__file__).resolve().parent / "us"
START_DATE = "19700101"
END_DATE = "22220101"
PERIOD = "daily"
ADJUST = "qfq"
ADJUST_OPTIONS = tuple(dict.fromkeys([ADJUST, ""]))
REQUEST_DELAY_SECONDS = 0.2


def safe_filename(name: str) -> str:
    """Keep stock names usable as filenames on common filesystems."""
    invalid_chars = '<>:"/\\|?*'
    return "".join("_" if char in invalid_chars else char for char in name).strip()


def symbol_candidates(symbol: str) -> tuple[str, ...]:
    candidates = [symbol]
    if "_" in symbol:
        candidates.extend([symbol.replace("_", "."), symbol.replace("_", "-")])
    return tuple(dict.fromkeys(candidates))


def build_eastmoney_symbol_map() -> dict[str, str]:
    try:
        spot_df = ak.stock_us_spot_em()
    except Exception as exc:
        print(f"Could not load EastMoney US symbol map: {exc}; using Sina fallback")
        return {}

    symbol_map = {}

    if spot_df is None or spot_df.empty or "代码" not in spot_df.columns:
        return symbol_map

    for code in spot_df["代码"].dropna().astype(str):
        ticker = code.split(".")[-1]
        symbol_map[ticker] = code

    return symbol_map


def ensure_rows(stock_df, source: str):
    if stock_df is None or stock_df.empty:
        raise ValueError(f"No rows returned from {source}")
    return stock_df


def fetch_stock_history_from_eastmoney(symbol: str, em_symbol_map: dict[str, str]):
    em_symbol = None
    for candidate in symbol_candidates(symbol):
        em_symbol = em_symbol_map.get(candidate)
        if em_symbol:
            break

    if not em_symbol:
        raise ValueError(f"Could not find EastMoney code for {symbol}")

    last_error = None
    for adjust in ADJUST_OPTIONS:
        try:
            stock_df = ak.stock_us_hist(
                symbol=em_symbol,
                period=PERIOD,
                start_date=START_DATE,
                end_date=END_DATE,
                adjust=adjust,
            )
            return ensure_rows(stock_df, f"EastMoney adjust={adjust!r}")
        except Exception as exc:
            last_error = exc

    raise last_error


def fetch_stock_history_from_sina(symbol: str):
    last_error = None
    for candidate in symbol_candidates(symbol):
        for adjust in ADJUST_OPTIONS:
            try:
                stock_df = ak.stock_us_daily(symbol=candidate, adjust=adjust)
                return ensure_rows(stock_df, f"Sina symbol={candidate} adjust={adjust!r}")
            except Exception as exc:
                last_error = exc

    raise last_error


def fetch_stock_history(symbol: str, em_symbol_map: dict[str, str]):
    try:
        return fetch_stock_history_from_eastmoney(symbol, em_symbol_map)
    except Exception as em_exc:
        print(f"EastMoney fetch failed for {symbol}: {em_exc}; trying Sina daily")
        return fetch_stock_history_from_sina(symbol)


def save_all_us_stocks() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    failures = []
    em_symbol_map = build_eastmoney_symbol_map()

    for index, (symbol, stock_name) in enumerate(us_stocks.items(), start=1):
        output_path = OUTPUT_DIR / f"{safe_filename(stock_name)}.parquet"
        print(f"[{index}/{len(us_stocks)}] Fetching {symbol} {stock_name}")

        try:
            stock_df = fetch_stock_history(symbol, em_symbol_map)
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

    print(f"\nDone. Saved {len(us_stocks)} parquet files in {OUTPUT_DIR}")


if __name__ == "__main__":
    save_all_us_stocks()
