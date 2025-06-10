from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import List, Optional
from .news_schema import NewsRead
from .right_schema import RightRead

class AnalysisBase(BaseModel):
    content: str
    analysis_date: datetime
    id_news: UUID

class AnalysisCreate(AnalysisBase):
    rights: Optional[List[UUID]] = []  # UUIDs de los derechos asociados

class AnalysisRead(AnalysisBase):
    id_analysis: UUID
    news: Optional[NewsRead]
    rights: Optional[List[RightRead]] = []

    class Config:
        orm_mode = True
