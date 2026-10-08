import logging
from typing import List, Optional
from elasticsearch import AsyncElasticsearch
from elasticsearch.exceptions import NotFoundError, ConnectionError, BadRequestError
from elasticsearch.helpers import async_bulk
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_elastic_client: Optional[AsyncElasticsearch] = None


def get_elastic_client() -> AsyncElasticsearch:
    global _elastic_client
    if _elastic_client is None:
        _elastic_client = AsyncElasticsearch(
            hosts=[settings.elasticsearch_url],
            request_timeout=30.0,
            max_retries=3,
            retry_on_timeout=True,
        )
    return _elastic_client


async def close_elastic_client() -> None:
    global _elastic_client
    if _elastic_client is not None:
        await _elastic_client.close()
        _elastic_client = None


async def ping_elastic() -> bool:
    try:
        es = get_elastic_client()
        return await es.ping()
    except Exception as e:
        logger.warning(f"Elasticsearch ping failed: {e}")
        return False


async def create_index_if_not_exists(index_name: Optional[str] = None) -> None:
    index = index_name or settings.elasticsearch_index
    es = get_elastic_client()

    if await es.indices.exists(index=index):
        logger.info(f"Elasticsearch index '{index}' already exists.")
        return

    mapping = {
        "mappings": {
            "properties": {
                "id": {"type": "integer"},
                "text": {
                    "type": "text",
                    "analyzer": "russian",
                },
            }
        }
    }

    try:
        await es.indices.create(index=index, body=mapping)
        logger.info(f"Elasticsearch index '{index}' created successfully.")
    except BadRequestError as e:
        if "resource_already_exists_exception" in str(e):
            logger.info(f"Index '{index}' was created concurrently.")
        else:
            raise


async def index_document(doc_id: int, text: str, index_name: Optional[str] = None) -> None:
    index = index_name or settings.elasticsearch_index
    es = get_elastic_client()
    await es.index(
        index=index,
        id=str(doc_id),
        document={"id": doc_id, "text": text},
        refresh=True,
    )


async def bulk_index_documents(documents: List[dict], index_name: Optional[str] = None) -> None:
    if not documents:
        return
    index = index_name or settings.elasticsearch_index
    es = get_elastic_client()

    actions = [
        {
            "_index": index,
            "_id": str(doc["id"]),
            "_source": {
                "id": doc["id"],
                "text": doc["text"],
            },
        }
        for doc in documents
    ]

    await async_bulk(es, actions, refresh=True)


async def delete_document_from_index(doc_id: int, index_name: Optional[str] = None) -> bool:
    index = index_name or settings.elasticsearch_index
    es = get_elastic_client()
    try:
        await es.delete(index=index, id=str(doc_id), refresh=True)
        return True
    except NotFoundError:
        logger.info(f"Document with id {doc_id} not found in Elasticsearch index '{index}'.")
        return False


async def search_document_ids(query: str, size: int = 1000, index_name: Optional[str] = None) -> List[int]:
    index = index_name or settings.elasticsearch_index
    es = get_elastic_client()
    try:
        response = await es.search(
            index=index,
            query={"match": {"text": query}},
            _source=["id"],
            size=size,
        )
        hits = response.get("hits", {}).get("hits", [])
        return [int(hit["_id"]) for hit in hits]
    except NotFoundError:
        return []
