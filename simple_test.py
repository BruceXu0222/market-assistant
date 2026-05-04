import pandas as pd

df = pd.read_parquet("data/test.parquet", engine="pyarrow")
print(df.head())

import pyarrow.parquet as pq

pf = pq.ParquetFile("data/test.parquet")

num_rows = pf.metadata.num_rows
num_columns = pf.metadata.num_columns

print("Rows:", num_rows)
print("Columns:", num_columns)