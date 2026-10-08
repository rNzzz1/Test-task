import ast
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import AsyncSessionLocal
from app.elastic import (
    create_index_if_not_exists,
    bulk_index_documents,
    ping_elastic,
)
from app.models import Post

logger = logging.getLogger(__name__)
settings = get_settings()


def parse_csv_posts(file_path: str) -> List[dict]:
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found at: {file_path}")

    posts = []
    with open(path, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return posts

        for row_idx, row in enumerate(reader, start=1):
            if not row or len(row) < 3:
                continue
            text = row[0].strip()
            date_str = row[1].strip()
            rubrics_raw = row[2].strip()

            try:
                created_date = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
            except ValueError:
                # Handle possible alternative ISO format
                created_date = datetime.fromisoformat(date_str)

            try:
                rubrics = ast.literal_eval(rubrics_raw)
                if not isinstance(rubrics, list):
                    rubrics = [str(rubrics)]
            except Exception:
                rubrics = []

            posts.append({
                "text": text,
                "created_date": created_date,
                "rubrics": rubrics,
            })

    return posts


async def load_csv_data(
    csv_path: Optional[str] = None,
    force: bool = False,
    batch_size: int = 500,
) -> int:
    path = csv_path or settings.csv_data_path
    logger.info(f"Checking data initialization from: {path}")

    async with AsyncSessionLocal() as session:
        count_stmt = select(func.count()).select_from(Post)
        result = await session.execute(count_stmt)
        existing_count = result.scalar_one()

        if existing_count > 0 and not force:
            logger.info(f"Database already contains {existing_count} posts. Skipping CSV load.")
            return existing_count

        parsed_rows = parse_csv_posts(path)
        logger.info(f"Parsed {len(parsed_rows)} documents from CSV.")

        if not parsed_rows:
            return 0

        # Ensure Elasticsearch index exists if ES is reachable
        es_available = await ping_elastic()
        if es_available:
            await create_index_if_not_exists()
        else:
            logger.warning("Elasticsearch is not reachable. Indexing will be skipped for now.")

        total_inserted = 0
        for i in range(0, len(parsed_rows), batch_size):
            chunk = parsed_rows[i : i + batch_size]
            post_models = [
                Post(
                    text=item["text"],
                    created_date=item["created_date"],
                    rubrics=item["rubrics"],
                )
                for item in chunk
            ]

            session.add_all(post_models)
            await session.commit()

            # Refresh to obtain generated DB ids
            es_docs = []
            for post in post_models:
                await session.refresh(post)
                es_docs.append({"id": post.id, "text": post.text})

            if es_available:
                await bulk_index_documents(es_docs)

            total_inserted += len(post_models)
            logger.info(f"Loaded {total_inserted}/{len(parsed_rows)} documents into DB and Elasticsearch.")

        return total_inserted
