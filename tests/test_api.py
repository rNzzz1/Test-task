from datetime import datetime, timedelta
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] is True
    assert data["elasticsearch"] is True


@pytest.mark.asyncio
async def test_create_and_get_post(async_client: AsyncClient):
    post_payload = {
        "text": "Тестовый документ про искусственный интеллект",
        "rubrics": ["VK-123", "AI-TECH"],
        "created_date": "2023-05-15T10:30:00",
    }
    response = await async_client.post("/posts", json=post_payload)
    assert response.status_code == 201
    created_post = response.json()
    assert "id" in created_post
    assert created_post["text"] == post_payload["text"]
    assert created_post["rubrics"] == post_payload["rubrics"]

    # Verify GET by ID
    get_res = await async_client.get(f"/posts/{created_post['id']}")
    assert get_res.status_code == 200
    fetched_post = get_res.json()
    assert fetched_post["id"] == created_post["id"]
    assert fetched_post["text"] == post_payload["text"]


@pytest.mark.asyncio
async def test_search_posts_ordered_by_created_date(async_client: AsyncClient):
    # Insert posts with different dates
    dates = [
        "2019-01-01T12:00:00",
        "2023-01-01T12:00:00",
        "2021-01-01T12:00:00",
    ]
    for d in dates:
        await async_client.post(
            "/posts",
            json={
                "text": f"Уникальное сообщение про Python робота дата {d}",
                "rubrics": ["TECH"],
                "created_date": d,
            },
        )

    # Search for "робота"
    response = await async_client.get("/search?query=робота")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 3

    # Check fields of the DB structure
    for doc in results:
        assert "id" in doc
        assert "rubrics" in doc
        assert "text" in doc
        assert "created_date" in doc

    # Verify descending ordering by created_date
    res_dates = [doc["created_date"] for doc in results]
    assert res_dates == [
        "2023-01-01T12:00:00",
        "2021-01-01T12:00:00",
        "2019-01-01T12:00:00",
    ]


@pytest.mark.asyncio
async def test_search_posts_limit_20(async_client: AsyncClient):
    # Insert 25 documents matching "лимит_тест"
    base_time = datetime(2022, 1, 1, 10, 0, 0)
    for i in range(25):
        dt = base_time + timedelta(hours=i)
        await async_client.post(
            "/posts",
            json={
                "text": f"Документ #{i} для проверки лимит_тест параметров",
                "rubrics": ["BENCHMARK"],
                "created_date": dt.isoformat(),
            },
        )

    response = await async_client.get("/search?query=лимит_тест")
    assert response.status_code == 200
    results = response.json()

    # Must return first 20 documents
    assert len(results) == 20
    # Must be sorted by created_date descending (document #24 is first)
    assert "Документ #24" in results[0]["text"]
    assert "Документ #5" in results[19]["text"]


@pytest.mark.asyncio
async def test_search_empty_results(async_client: AsyncClient):
    response = await async_client.get("/search?query=абсолютноНесуществующееСлово12345")
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_search_validation_empty_query(async_client: AsyncClient):
    # Query param missing
    response = await async_client.get("/search")
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_delete_post_removes_from_db_and_index(async_client: AsyncClient):
    # 1. Create document
    create_res = await async_client.post(
        "/posts",
        json={
            "text": "Документ для последующего удаления",
            "rubrics": ["DELETE-ME"],
            "created_date": "2023-06-01T15:00:00",
        },
    )
    doc_id = create_res.json()["id"]

    # 2. Check it appears in search
    search_before = await async_client.get("/search?query=последующего")
    assert any(doc["id"] == doc_id for doc in search_before.json())

    # 3. Delete document
    del_res = await async_client.delete(f"/posts/{doc_id}")
    assert del_res.status_code == 204

    # 4. Check it is removed from DB
    get_res = await async_client.get(f"/posts/{doc_id}")
    assert get_res.status_code == 404

    # 5. Check it is removed from search index
    search_after = await async_client.get("/search?query=последующего")
    assert not any(doc["id"] == doc_id for doc in search_after.json())


@pytest.mark.asyncio
async def test_delete_non_existent_post(async_client: AsyncClient):
    response = await async_client.delete("/posts/999999")
    assert response.status_code == 404
    assert response.json()["detail"] == "Документ с id=999999 не найден"


@pytest.mark.asyncio
async def test_get_non_existent_post(async_client: AsyncClient):
    response = await async_client.get("/posts/999999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_api_v1_versioned_routes(async_client: AsyncClient):
    # Test prefixed /api/v1 routes
    create_res = await async_client.post(
        "/api/v1/posts",
        json={
            "text": "Версионированный API запрос",
            "rubrics": ["API-V1"],
            "created_date": "2023-07-01T12:00:00",
        },
    )
    assert create_res.status_code == 201
    doc_id = create_res.json()["id"]

    search_res = await async_client.get("/api/v1/search?query=Версионированный")
    assert search_res.status_code == 200
    assert any(d["id"] == doc_id for d in search_res.json())

    del_res = await async_client.delete(f"/api/v1/posts/{doc_id}")
    assert del_res.status_code == 204


@pytest.mark.asyncio
async def test_search_posts_order_asc(async_client: AsyncClient):
    dates = [
        "2020-01-01T12:00:00",
        "2022-01-01T12:00:00",
        "2021-01-01T12:00:00",
    ]
    for d in dates:
        await async_client.post(
            "/posts",
            json={
                "text": f"Сортировка по возрастанию даты {d}",
                "rubrics": ["SORT-ASC"],
                "created_date": d,
            },
        )

    response = await async_client.get("/search?query=Сортировка&order=asc")
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 3
    res_dates = [doc["created_date"] for doc in results]
    assert res_dates == [
        "2020-01-01T12:00:00",
        "2021-01-01T12:00:00",
        "2022-01-01T12:00:00",
    ]


@pytest.mark.asyncio
async def test_parse_csv_posts_parser():
    from app.services.data_loader import parse_csv_posts
    parsed = parse_csv_posts("posts.csv")
    assert len(parsed) == 1500
    first = parsed[0]
    assert isinstance(first["text"], str)
    assert len(first["text"]) > 0
    assert isinstance(first["rubrics"], list)
    assert len(first["rubrics"]) == 3
    assert isinstance(first["created_date"], datetime)
