from pydantic import BaseModel
from uuid import UUID

class RightBase(BaseModel):
    right: str

class RightCreate(RightBase):
    pass

class RightRead(RightBase):
    id_right: UUID

    class Config:
        orm_mode = True