import logging
from typing import List, Literal
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
import app.elastic as elastic
from app.schemas import PostCreate, PostResponse, HealthResponse
from app.services import post_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/search",
    response_model=List[PostResponse],
    summary="Поиск документов по тексту",
    description="Принимает произвольный текстовый запрос, ищет по тексту документа в индексе Elasticsearch "
                "и возвращает первые 20 документов со всеми полями БД, упорядоченные по дате создания.",
    tags=["Search"],
)
async def search_posts(
    query: str = Query(..., min_length=1, description="Текстовый запрос для полнотекстового поиска"),
    limit: int = Query(20, ge=1, le=100, description="Количество возвращаемых документов (по умолчанию 20)"),
    order: Literal["desc", "asc"] = Query("desc", description="Порядок сортировки по дате создания ('desc' или 'asc')"),
    session: AsyncSession = Depends(get_db_session),
):
    posts = await post_service.search_posts(
        query=query,
        session=session,
        limit=limit,
        order_desc=(order == "desc"),
    )
    return posts


@router.delete(
    "/posts/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удаление документа по ID",
    description="Удаляет документ из базы данных и индекса Elasticsearch по уникальному полю id.",
    tags=["Posts"],
)
async def delete_post(
    id: int,
    session: AsyncSession = Depends(get_db_session),
):
    deleted = await post_service.delete_post(post_id=id, session=session)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Документ с id={id} не найден",
        )
    return None


@router.get(
    "/posts/{id}",
    response_model=PostResponse,
    summary="Получение документа по ID",
    description="Возвращает документ со всеми полями из базы данных по его уникальному ID.",
    tags=["Posts"],
)
async def get_post(
    id: int,
    session: AsyncSession = Depends(get_db_session),
):
    post = await post_service.get_post_by_id(post_id=id, session=session)
    if not post:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Документ с id={id} не найден",
        )
    return post


@router.post(
    "/posts",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создание нового документа",
    description="Добавляет новый документ в базу данных и индексирует его в Elasticsearch.",
    tags=["Posts"],
)
async def create_post(
    post_in: PostCreate,
    session: AsyncSession = Depends(get_db_session),
):
    return await post_service.create_post(post_in=post_in, session=session)


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Проверка работоспособности сервиса",
    description="Проверяет соединение с базой данных и сервисом Elasticsearch.",
    tags=["Health"],
)
async def health_check(
    session: AsyncSession = Depends(get_db_session),
):
    db_ok = False
    try:
        res = await session.execute(text("SELECT 1"))
        db_ok = res.scalar() == 1
    except Exception as e:
        logger.error(f"Database health check failed: {e}")

    es_ok = await elastic.ping_elastic()

    overall_status = "ok" if (db_ok and es_ok) else "degraded"
    return HealthResponse(
        status=overall_status,
        database=db_ok,
        elasticsearch=es_ok,
    )
