from uuid import uuid4
from datetime import datetime
from sqlalchemy.orm import Session
from app import models

def save_news(db: Session, headline: str, content: str, news_date: datetime):
    news = models.News(
        id_news=uuid4(),
        headline=headline,
        content=content,
        news_date=news_date
    )
    db.add(news)
    db.commit()        
    db.refresh(news)
    return news

def get_news(db: Session, title: str, news_date: datetime):
    return (
        db.query(models.News)
        .filter(models.News.headline == title, models.News.news_date == news_date).first()
    )