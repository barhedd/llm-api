from sqlalchemy.orm import Session
from uuid import uuid4
from app import models

def get_all_visible_rights(db: Session):
    return (
        db.query(models.Right)
        .filter(models.Right.visible == True)
        .order_by(models.Right.order.asc())
        .all()
    )