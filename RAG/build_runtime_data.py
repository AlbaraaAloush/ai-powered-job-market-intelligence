"""Build the compact backend dataset used on every normal server restart."""
from data_loader import build_runtime_snapshot


if __name__ == "__main__":
    parquet, manifest, count = build_runtime_snapshot()
    print(f"Runtime data ready: {count:,} postings")
    print(f"  parquet: {parquet}")
    print(f"  manifest: {manifest}")
