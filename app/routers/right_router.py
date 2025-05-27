from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.schemas import right_schema as RightSchema
from app.services import right_service as RightService

router = APIRouter()

@router.get("/", response_model=list[RightSchema.RightRead])
def read_rights(db: Session = Depends(get_db)):
    return RightService.get_all_visible_rights(db)

