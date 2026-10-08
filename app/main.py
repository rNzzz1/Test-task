import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import router as api_v1_router
from app.config import get_settings
from app.database import init_db, close_db
from app.elastic import close_elastic_client
from app.services.data_loader import load_csv_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("document_search")
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database tables...")
    await init_db()

    if settings.auto_seed_on_startup:
        try:
            logger.info("Running automatic seed check...")
            await load_csv_data()
        except Exception as e:
            logger.warning(f"Could not auto-seed data on startup (will continue): {e}")

    yield

    # Shutdown
    logger.info("Shutting down service...")
    await close_db()
    await close_elastic_client()


app = FastAPI(
    title="Document Search Service",
    description="Сервис полнотекстового поиска по текстам документов с использованием PostgreSQL и Elasticsearch.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root-level endpoints (matching test assignment requirements: /search, /posts/{id}, /health)
app.include_router(api_v1_router)

# Also expose under /api/v1 for standard API versioning
app.include_router(api_v1_router, prefix="/api/v1")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.debug,
    )
