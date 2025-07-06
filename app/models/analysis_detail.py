from sqlalchemy import Column, ForeignKey, String, Integer
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import relationship
from uuid import uuid4
from .base import Base

class AnalysisDetail(Base):
    __tablename__ = "analysis_detail"

    id_detail = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid4, index=True)
    id_analysis = Column(UNIQUEIDENTIFIER, ForeignKey("analysis.id_analysis"), nullable=False)
    id_right = Column(UNIQUEIDENTIFIER, ForeignKey("right.id_right"), nullable=False)
    count = Column(Integer, nullable=False)
    places = Column(String, nullable=True)

    analysis = relationship("Analysis", back_populates="details")
    right = relationship("Right", back_populates="details")