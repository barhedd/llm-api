from pydantic import BaseModel
from typing import List

class ProcessNewsRequest(BaseModel):
    dates: List[str]
    rights: List[str]