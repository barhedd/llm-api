from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class NewsBase(BaseModel):
    headline: str
    content: str
    news_date: datetime

class NewsCreate(NewsBase):
    pass

class NewsRead(NewsBase):
    id_news: UUID

    class Config:
        orm_mode = True

