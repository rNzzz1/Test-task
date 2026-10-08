import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import init_db, close_db
from app.elastic import close_elastic_client
from app.services.data_loader import load_csv_data

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


async def main():
    parser = argparse.ArgumentParser(description="Load CSV posts into Database and Elasticsearch")
    parser.add_argument("--csv", default="posts.csv", help="Path to CSV file (default: posts.csv)")
    parser.add_argument("--force", action="store_true", help="Force re-import even if DB already has records")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size for inserts (default: 500)")
    args = parser.parse_args()

    print(f"Starting import from {args.csv}...")
    await init_db()
    try:
        count = await load_csv_data(csv_path=args.csv, force=args.force, batch_size=args.batch_size)
        print(f"Completed! Total documents processed: {count}")
    finally:
        await close_db()
        await close_elastic_client()


if __name__ == "__main__":
    asyncio.run(main())
