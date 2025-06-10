from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session
from app import models

def save_analysis(db: Session, content: str, news_id, analysis_date: datetime):
    analysis = models.Analysis(
        id_analysis=uuid4(),
        content=content,
        analysis_date=analysis_date,
        id_news=news_id
    )
    db.add(analysis)
    db.commit() 
    db.refresh(analysis)
    return analysis

def get_all_analysis(db: Session ):
    return (
        db.query(models.Analysis)
        .all()
    )

def get_analysis(db: Session, id_new: str):
    return (
        db.query(models.Analysis)
        .filter(models.Analysis.id_news == id_new)
    )