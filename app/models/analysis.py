from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import relationship, declarative_base
from .base import Base

class Analysis(Base):
    __tablename__ = "analysis"
    
    id_analysis = Column(UNIQUEIDENTIFIER, primary_key=True, index=True)
    content = Column(String, nullable=False)
    analysis_date = Column(DateTime, nullable=False)
    id_news = Column(UNIQUEIDENTIFIER, ForeignKey("news.id_news"), nullable=False)
    
    news = relationship("News", back_populates="analyses")
    rights = relationship(
        "Right",
        secondary="analysis_right",
        back_populates="analyses"
    )
