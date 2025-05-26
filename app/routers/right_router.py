from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app import services, schemas
from app.database import get_db

router = APIRouter()

@router.get("/", response_model=list[schemas.RightRead])
def read_rights(db: Session = Depends(get_db)):
    return services.get_all_rights(db)

