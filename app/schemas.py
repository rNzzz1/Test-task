from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class PostBase(BaseModel):
    rubrics: List[str] = Field(..., description="Массив рубрик документа")
    text: str = Field(..., description="Текст документа")
    created_date: datetime = Field(..., description="Дата создания документа")


class PostCreate(BaseModel):
    rubrics: List[str] = Field(default_factory=list, description="Массив рубрик документа")
    text: str = Field(..., min_length=1, description="Текст документа")
    created_date: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Дата создания (по умолчанию текущее время)")


class PostResponse(PostBase):
    id: int = Field(..., description="Уникальный идентификатор документа")

    model_config = ConfigDict(from_attributes=True)


class HealthResponse(BaseModel):
    status: str = Field(..., description="Общий статус сервиса ('ok' или 'degraded')")
    database: bool = Field(..., description="Статус подключения к БД")
    elasticsearch: bool = Field(..., description="Статус подключения к Elasticsearch")
