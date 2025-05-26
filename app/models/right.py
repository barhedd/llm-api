from sqlalchemy import Column, String
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import relationship, declarative_base
from .base import Base

class Right(Base):
    __tablename__ = "right"
    
    id_right = Column(UNIQUEIDENTIFIER, primary_key=True, index=True)
    right = Column(String(200), nullable=False)
    
    analyses = relationship(
        "Analysis",
        secondary="analysis_right",
        back_populates="rights"
    )