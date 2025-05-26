from pydantic import BaseModel
from typing import List, Dict

class ProcessNewsResponse(BaseModel):
    response: Dict[str, Dict[str, int]]  # {fecha: {derecho: conteo}}