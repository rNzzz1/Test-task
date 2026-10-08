import asyncio
from datetime import datetime
from typing import AsyncGenerator, Dict, List
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import get_db_session
from app.models import Base, Post
from app.main import app
import app.elastic as elastic_module

# Test SQLite in-memory database
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class InMemoryElasticMock:
    """Mock Elasticsearch storing documents in memory for fast functional tests."""

    def __init__(self):
        self.docs: Dict[int, str] = {}

    async def ping(self) -> bool:
        return True

    async def create_index(self, index_name=None):
        pass

    async def index_doc(self, doc_id: int, text: str, index_name=None):
        self.docs[doc_id] = text

    async def bulk_index(self, documents: List[dict], index_name=None):
        for doc in documents:
            self.docs[doc["id"]] = doc["text"]

    async def delete_doc(self, doc_id: int, index_name=None) -> bool:
        if doc_id in self.docs:
            del self.docs[doc_id]
            return True
        return False

    async def search(self, query: str, size: int = 1000, index_name=None) -> List[int]:
        q_lower = query.lower().strip()
        matched = []
        for doc_id, text in self.docs.items():
            if q_lower in text.lower():
                matched.append(doc_id)
        return matched


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(autouse=True)
async def prepare_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    async with TestingSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
def mock_elastic(monkeypatch):
    es_mock = InMemoryElasticMock()

    monkeypatch.setattr(elastic_module, "ping_elastic", es_mock.ping)
    monkeypatch.setattr(elastic_module, "create_index_if_not_exists", es_mock.create_index)
    monkeypatch.setattr(elastic_module, "index_document", es_mock.index_doc)
    monkeypatch.setattr(elastic_module, "bulk_index_documents", es_mock.bulk_index)
    monkeypatch.setattr(elastic_module, "delete_document_from_index", es_mock.delete_doc)
    monkeypatch.setattr(elastic_module, "search_document_ids", es_mock.search)

    return es_mock


@pytest_asyncio.fixture
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
