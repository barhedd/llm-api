from sqlalchemy.orm import Session
from uuid import uuid4
from app import models

def get_all_rights(db: Session):
    return db.query(models.Right).all()