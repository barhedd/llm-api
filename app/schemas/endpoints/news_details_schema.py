from pydantic import BaseModel
from uuid import UUID
from typing import Any, Dict, List, Optional
from datetime import datetime

class NewsDetailsRequest(BaseModel):
    ids: List[UUID]
    rights: List[str]

class NewsDetailsResponse(BaseModel):
    id_news: UUID
    headline: str
    content: str
    news_date: datetime 
    filtered_analysis: Optional[List[Dict[str, Any]]] = None 

    class Config:
        orm_mode = True
        json_encoders = {
            UUID: lambda u: str(u)
        }
