from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.schemas import analysis_right_schema as AnalysisRightSchema
from app.services import analysis_right_service as AnalysisRightService

router = APIRouter()

@router.get("/", response_model=list[AnalysisRightSchema.AnalysisRead])
def read_analysis(db: Session = Depends(get_db)):
    return AnalysisRightService.get_all_analysis_right(db)