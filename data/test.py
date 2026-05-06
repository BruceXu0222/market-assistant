import pandas as pd
df = pd.read_parquet("data/hk/万科企业.parquet")
print(df.shape)
print(df.head())