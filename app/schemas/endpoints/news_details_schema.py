from pydantic import BaseModel
from uuid import UUID
from typing import List
from datetime import datetime

class NewsIdsRequest(BaseModel):
    ids: List[UUID]

class NewsDetailsResponse(BaseModel):
    id_news: UUID
    headline: str
    content: str
    news_date: datetime 

    class Config:
        orm_mode = True
        json_encoders = {
            UUID: lambda u: str(u)
        }
