from sqlalchemy import Column, DateTime, String
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import relationship, declarative_base
from .base import Base

class News(Base):
    __tablename__ = "news"
    
    id_news = Column(UNIQUEIDENTIFIER, primary_key=True, index=True)
    headline = Column(String, nullable=False)
    content = Column(String, nullable=False)
    news_date = Column(DateTime, nullable=False)
    
    analyses = relationship("Analysis", back_populates="news")