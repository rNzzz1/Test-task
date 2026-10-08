import logging
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import app.elastic as elastic
from app.models import Post
from app.schemas import PostCreate

logger = logging.getLogger(__name__)


async def search_posts(
    query: str,
    session: AsyncSession,
    limit: int = 20,
    order_desc: bool = True,
) -> List[Post]:
    if not query.strip():
        return []

    # 1. Search Elasticsearch index for matching document IDs
    doc_ids = await elastic.search_document_ids(query=query)
    if not doc_ids:
        return []

    # 2. Fetch full documents from DB ordered by created_date
    order_clause = Post.created_date.desc() if order_desc else Post.created_date.asc()
    stmt = (
        select(Post)
        .where(Post.id.in_(doc_ids))
        .order_by(order_clause)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def delete_post(
    post_id: int,
    session: AsyncSession,
) -> bool:
    # 1. Fetch from DB
    post = await session.get(Post, post_id)
    if not post:
        return False

    # 2. Delete from DB
    await session.delete(post)
    await session.commit()

    # 3. Delete from Elasticsearch index
    await elastic.delete_document_from_index(post_id)
    logger.info(f"Post with id={post_id} deleted from DB and Elasticsearch.")
    return True


async def create_post(
    post_in: PostCreate,
    session: AsyncSession,
) -> Post:
    post = Post(
        rubrics=post_in.rubrics,
        text=post_in.text,
        created_date=post_in.created_date,
    )
    session.add(post)
    await session.commit()
    await session.refresh(post)

    # Index in Elasticsearch
    try:
        await elastic.index_document(doc_id=post.id, text=post.text)
    except Exception as e:
        logger.error(f"Failed to index post {post.id} in Elasticsearch: {e}")

    return post


async def get_post_by_id(
    post_id: int,
    session: AsyncSession,
) -> Optional[Post]:
    return await session.get(Post, post_id)
