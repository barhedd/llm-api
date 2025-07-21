from sqlalchemy.orm import Session
from app.models.right import Right

def get_all_visible_rights(db: Session):
    return (
        db.query(Right)
        .filter(Right.visible == True)
        .order_by(Right.order.asc())
        .all()
    )