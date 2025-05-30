from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.schemas import analysis_schema as AnalysisSchema
from app.services import analysis_service as AnalysisService

router = APIRouter()

@router.get("/", response_model=list[AnalysisSchema.AnalysisRead])
def read_analysis(db: Session = Depends(get_db)):
    return AnalysisService.get_all_analysis(db)