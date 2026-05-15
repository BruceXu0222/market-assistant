from pathlib import Path
from time import sleep

import akshare as ak


us_stocks = {
"BLDP": "BLDP",
"INTC": "INTC",
"AKAM": "AKAM",
"DDD": "DDD",
"MU": "MU",
"QCOM": "QCOM",
"DD": "DD",
"HOG": "HOG",
"JACK": "JACK",
"PLUG": "PLUG",
"SBLK": "SBLK",
"SWKS": "SWKS",
"WDC": "WDC",
"AMBA": "AMBA",
"MT": "MT",
"FLEX": "FLEX",
"AMAT": "AMAT",
"A": "A",
"AAL": "AAL",
"HPE": "HPE",
"STX": "STX",
"CRUS": "CRUS",
"FCEL": "FCEL",
"AMD": "AMD",
"NUS": "NUS",
"CLF": "CLF",
"GCO": "GCO",
"ADM": "ADM",
"FCX": "FCX",
"FSLR": "FSLR",
"CEVA": "CEVA",
"LUV": "LUV",
"LQDT": "LQDT",
"DAL": "DAL",
"CAT": "CAT",
"CLDX": "CLDX",
"STLD": "STLD",
"GT": "GT",
"TWLO": "TWLO",
"MRVL": "MRVL",
"CAKE": "CAKE",
"IVZ": "IVZ",
"NTAP": "NTAP",
"ORCL": "ORCL",
"FRO": "FRO",
"HLF": "HLF",
"NUE": "NUE",
"WYNN": "WYNN",
"PRU": "PRU",
"IBKR": "IBKR",
"AAPL": "AAPL",
"AVGO": "AVGO",
"LC": "LC",
"BEN": "BEN",
"RS": "RS",
"SSYS": "SSYS",
"WOR": "WOR",
"PHM": "PHM",
"DG": "DG",
"GE": "GE",
"PRGO": "PRGO",
"VMI": "VMI",
"LEN": "LEN",
"ALB": "ALB",
"LLY": "LLY",
"EMR": "EMR",
"FMC": "FMC",
"TTD": "TTD",
"IP": "IP",
"MAR": "MAR",
"MBI": "MBI",
"DHI": "DHI",
"GBX": "GBX",
"YELP": "YELP",
"C": "C",
"LBTYA": "LBTYA",
"PBI": "PBI",
"UPS": "UPS",
"MYGN": "MYGN",
"CSCO": "CSCO",
"COLM": "COLM",
"H": "H",
"BAC": "BAC",
"MNKD": "MNKD",
"AMGN": "AMGN",
"GS": "GS",
"CF": "CF",
"UBS": "UBS",
"AZO": "AZO",
"HPQ": "HPQ",
"S": "S",
"F": "F",
"TOL": "TOL",
"PNC": "PNC",
"GME": "GME",
"HSY": "HSY",
"AEO": "AEO",
"EQR": "EQR",
"BYD": "BYD",
"IMAX": "IMAX",
"BA": "BA",
"DB": "DB",
"GPRO": "GPRO",
"FDX": "FDX",
"RF": "RF",
"LVS": "LVS",
"GOOGL": "GOOGL",
"GLW": "GLW",
"MOS": "MOS",
"GOOG": "GOOG",
"MET": "MET",
"CDNS": "CDNS",
"AIG": "AIG",
"YUMC": "YUMC",
"CL": "CL",
"MCO": "MCO",
"PLD": "PLD",
"SHAK": "SHAK",
"CAG": "CAG",
"WEN": "WEN",
"BBQ": "BBQ",
"JBLU": "JBLU",
"PG": "PG",
"CMG": "CMG",
"BIIB": "BIIB",
"SCHW": "SCHW",
"PSX": "PSX",
"L": "L",
"AA": "AA",
"HD": "HD",
"LULU": "LULU",
"WMB": "WMB",
"WFC": "WFC",
"MMM": "MMM",
"EXPE": "EXPE",
"APO": "APO",
"NOV": "NOV",
"M": "M",
"TGT": "TGT",
"CRM": "CRM",
"MNST": "MNST",
"BAX": "BAX",
"XOM": "XOM",
"ADSK": "ADSK",
"FTNT": "FTNT",
"TXT": "TXT",
"GBR": "GBR",
"VLO": "VLO",
"WY": "WY",
"BMO": "BMO",
"CSX": "CSX",
"LOCO": "LOCO",
"KBH": "KBH",
"LOW": "LOW",
"SLB": "SLB",
"MS": "MS",
"ADBE": "ADBE",
"USB": "USB",
"NEM": "NEM",
"ROST": "ROST",
"ON": "ON",
"JNJ": "JNJ",
"KIM": "KIM",
"GILD": "GILD",
"GM": "GM",
"PFE": "PFE",
"JPM": "JPM",
"AMZN": "AMZN",
"TXN": "TXN",
"NXPI": "NXPI",
"DOW": "DOW",
"ARW": "ARW",
"HLT": "HLT",
"CP": "CP",
"LAND": "LAND",
"STT": "STT",
"SPG": "SPG",
"CCL": "CCL",
"FPI": "FPI",
"MCD": "MCD",
"KO": "KO",
"BK": "BK",
"COST": "COST",
"GIS": "GIS",
"IR": "IR",
"DHR": "DHR",
"JCI": "JCI",
"ABUS": "ABUS",
"MELI": "MELI",
"TJX": "TJX",
"CVX": "CVX",
"PM": "PM",
"SLM": "SLM",
"MRK": "MRK",
"CTSH": "CTSH",
"GNW": "GNW",
"SBUX": "SBUX",
"CAH": "CAH",
"MDLZ": "MDLZ",
"BOX": "BOX",
"TMUS": "TMUS",
"TRV": "TRV",
"NKE": "NKE",
"BCS": "BCS",
"EA": "EA",
"ZTS": "ZTS",
"COF": "COF",
"G": "G",
"AN": "AN",
"IBM": "IBM",
"FOXA": "FOXA",
"ISRG": "ISRG",
"ILMN": "ILMN",
"KGC": "KGC",
"FOX": "FOX",
"BX": "BX",
"BLK": "BLK",
"YUM": "YUM",
"VFC": "VFC",
"BRK_A": "BRK_A",
"CPRT": "CPRT",
"ABT": "ABT",
"TRIP": "TRIP",
"DE": "DE",
"VZ": "VZ",
"MSFT": "MSFT",
"KMI": "KMI",
"ANF": "ANF",
"ACN": "ACN",
"ALL": "ALL",
"HAL": "HAL",
"BBY": "BBY",
"NHTC": "NHTC",
"MDT": "MDT",
"WU": "WU",
"NTNX": "NTNX",
"BMY": "BMY",
"PGR": "PGR",
"T": "T",
"TSLA": "TSLA",
"DIS": "DIS",
"AAP": "AAP",
"MO": "MO",
"MCK": "MCK",
"MGM": "MGM",
"TEAM": "TEAM",
"MAT": "MAT",
"ZG": "ZG",
"GDDY": "GDDY",
"SDRL": "SDRL",
"KR": "KR",
"DXCM": "DXCM",
"SNAP": "SNAP",
"REGN": "REGN",
"ABBV": "ABBV",
"NVDA": "NVDA",
"AXP": "AXP",
"JBL": "JBL",
"LFWD": "LFWD",
"Z": "Z",
"LNG": "LNG",
"NYT": "NYT",
"COP": "COP",
"KKR": "KKR",
"SIRI": "SIRI",
"NWSA": "NWSA",
"V": "V",
"MA": "MA",
"BSX": "BSX",
"GOGO": "GOGO",
"CVS": "CVS",
"LMT": "LMT",
"UNH": "UNH",
"CMCSA": "CMCSA",
"NDAQ": "NDAQ",
"W": "W",
"GRPN": "GRPN",
"NFLX": "NFLX",
"EBAY": "EBAY",
"CAR": "CAR",
"KBR": "KBR",
"PYPL": "PYPL",
"RIG": "RIG",
"NDLS": "NDLS",
}


OUTPUT_DIR = Path(__file__).resolve().parent / "us"
START_DATE = "19700101"
END_DATE = "22220101"
PERIOD = "daily"
ADJUST = "qfq"
ADJUST_OPTIONS = tuple(dict.fromkeys([ADJUST, ""]))
REQUEST_DELAY_SECONDS = 0.2
CN_CODE = "\u4ee3\u7801"


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

    if spot_df is None or spot_df.empty or CN_CODE not in spot_df.columns:
        return symbol_map

    for code in spot_df[CN_CODE].dropna().astype(str):
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
        print(f"[{index}/{len(us_stocks)}] Fetching {symbol}")

        try:
            stock_df = fetch_stock_history(symbol, em_symbol_map)
            stock_df.insert(0, "stock_name", stock_name)
            stock_df.insert(0, "symbol", symbol)
            stock_df.to_parquet(output_path, index=False)
            print(f"Saved {len(stock_df)} rows to {output_path}")
        except Exception as exc:
            failures.append((symbol, str(exc)))
            print(f"Failed {symbol}: {exc}")

        sleep(REQUEST_DELAY_SECONDS)

    if failures:
        print("\nFailed stocks:")
        for symbol, error in failures:
            print(f"- {symbol}: {error}")
        raise SystemExit(1)

    print(f"\nDone. Saved {len(us_stocks)} parquet files in {OUTPUT_DIR}")


if __name__ == "__main__":
    save_all_us_stocks()
