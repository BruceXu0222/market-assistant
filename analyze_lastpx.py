#!/usr/bin/env python3
"""
Script to analyze the 'LastPx' field in test.parquet data.
Shows NaN values and their proportions.
"""

import pandas as pd
import numpy as np

def analyze_lastpx(parquet_file='./data/test.parquet'):
    """Analyze LastPx field for NaN values and proportions."""

    print(f"Loading parquet file: {parquet_file}")
    df = pd.read_parquet(parquet_file)

    print(f"\n{'='*60}")
    print(f"ANALYSIS OF 'LastPx' FIELD")
    print(f"{'='*60}\n")

    # Check if LastPx column exists
    if 'LastPx' not in df.columns:
        print(f"Error: 'LastPx' column not found in the dataset!")
        print(f"Available columns: {', '.join(df.columns)}")
        return

    # Get LastPx series
    lastpx = df['LastPx']

    # Total records
    total_records = len(lastpx)
    print(f"Total records: {total_records:,}")

    # Count NaN values
    nan_count = lastpx.isna().sum()
    non_nan_count = total_records - nan_count

    # Calculate proportions
    nan_proportion = (nan_count / total_records) * 100 if total_records > 0 else 0
    non_nan_proportion = (non_nan_count / total_records) * 100 if total_records > 0 else 0

    print(f"\n{'='*60}")
    print(f"NaN VALUE ANALYSIS")
    print(f"{'='*60}\n")
    print(f"Non-NaN values: {non_nan_count:,} ({non_nan_proportion:.2f}%)")
    print(f"NaN values:     {nan_count:,} ({nan_proportion:.2f}%)")

    # Additional statistics for non-NaN values
    if non_nan_count > 0:
        print(f"\n{'='*60}")
        print(f"STATISTICS FOR NON-NaN VALUES")
        print(f"{'='*60}\n")
        print(f"Min:    {lastpx.min():.4f}")
        print(f"Max:    {lastpx.max():.4f}")
        print(f"Mean:   {lastpx.mean():.4f}")
        print(f"Median: {lastpx.median():.4f}")
        print(f"Std:    {lastpx.std():.4f}")

        # Show distribution of values
        print(f"\n{'='*60}")
        print(f"VALUE DISTRIBUTION (QUARTILES)")
        print(f"{'='*60}\n")
        print(lastpx.describe())

    # Check for infinite values
    inf_count = np.isinf(lastpx).sum()
    if inf_count > 0:
        print(f"\n{'='*60}")
        print(f"WARNING: Found {inf_count} infinite values!")
        print(f"{'='*60}\n")

    print(f"\n{'='*60}")
    print(f"ANALYSIS COMPLETE")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    analyze_lastpx()
