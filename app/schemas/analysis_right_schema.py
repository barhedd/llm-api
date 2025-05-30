from pydantic import BaseModel
from uuid import UUID
from typing import List, Optional
from .analysis_schema import AnalysisRead
from .right_schema import RightRead

class RightAnalysisBase(BaseModel):
    id_analysis: UUID
    id_right: UUID

class RightAnalysisCreate(RightAnalysisBase):
    pass

class RightAnalysisRead(RightAnalysisBase):
    id_analysis: UUID
    analysis: Optional[AnalysisRead]
    rights: Optional[RightRead]

    class Config:
        orm_mode = True