from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import relationship, declarative_base
from .base import Base

class AnalysisRight(Base):
    __tablename__ = "analysis_right"
    
    id_right = Column(UNIQUEIDENTIFIER, ForeignKey("right.id_right"), primary_key=True)
    id_analysis = Column(UNIQUEIDENTIFIER, ForeignKey("analysis.id_analysis"), primary_key=True)