from pathlib import Path
from time import sleep

import akshare as ak


hk_stocks = {
"00005": "00005",
"00016": "00016",
"00020": "00020",
"00027": "00027",
"00168": "00168",
"00175": "00175",
"00241": "00241",
"00268": "00268",
"00285": "00285",
"00291": "00291",
"00322": "00322",
"00388": "00388",
"00493": "00493",
"00520": "00520",
"00656": "00656",
"00700": "00700",
"00728": "00728",
"00751": "00751",
"00753": "00753",
"00762": "00762",
"00763": "00763",
"00772": "00772",
"00780": "00780",
"00788": "00788",
"00868": "00868",
"00873": "00873",
"00883": "00883",
"00909": "00909",
"00914": "00914",
"00939": "00939",
"00941": "00941",
"00981": "00981",
"00991": "00991",
"00992": "00992",
"00998": "00998",
"01024": "01024",
"01060": "01060",
"01093": "01093",
"01138": "01138",
"01179": "01179",
"01211": "01211",
"01288": "01288",
"01299": "01299",
"01347": "01347",
"01357": "01357",
"01368": "01368",
"01385": "01385",
"01398": "01398",
"01458": "01458",
"01516": "01516",
"01579": "01579",
"01658": "01658",
"01772": "01772",
"01797": "01797",
"01810": "01810",
"01816": "01816",
"01833": "01833",
"01876": "01876",
"01896": "01896",
"01918": "01918",
"01919": "01919",
"01928": "01928",
"01929": "01929",
"02007": "02007",
"02013": "02013",
"02015": "02015",
"02018": "02018",
"02020": "02020",
"02057": "02057",
"02150": "02150",
"02196": "02196",
"02202": "02202",
"02269": "02269",
"02318": "02318",
"02319": "02319",
"02331": "02331",
"02333": "02333",
"02359": "02359",
"02382": "02382",
"02400": "02400",
"02423": "02423",
"02600": "02600",
"02618": "02618",
"02628": "02628",
"02899": "02899",
"03323": "03323",
"03328": "03328",
"03690": "03690",
"03888": "03888",
"03900": "03900",
"03968": "03968",
"03988": "03988",
"03998": "03998",
"06049": "06049",
"06098": "06098",
"06185": "06185",
"06186": "06186",
"06618": "06618",
"06690": "06690",
"06862": "06862",
"06865": "06865",
"06969": "06969",
"09618": "09618",
"09626": "09626",
"09633": "09633",
"09696": "09696",
"09698": "09698",
"09866": "09866",
"09868": "09868",
"09888": "09888",
"09901": "09901",
"09922": "09922",
"09961": "09961",
"09987": "09987",
"09988": "09988",
"09992": "09992",
"09999": "09999",
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
        print(f"[{index}/{len(hk_stocks)}] Fetching {symbol}")

        try:
            stock_df = fetch_stock_history(symbol)
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

    print(f"\nDone. Saved {len(hk_stocks)} parquet files in {OUTPUT_DIR}")


if __name__ == "__main__":
    save_all_hk_stocks()
