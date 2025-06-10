from pydantic import BaseModel
from typing import List

class ProcessNewsRequest(BaseModel):
    dates: List[str]  # Lista de fechas a procesar en formato "YYYY-MM-DD"
    rights: List[str]  # Lista de derechos humanos a analizar

class RightCount(BaseModel):
    derecho: str
    cantidad: int
    lugares: List[str]

class ProcessResult(BaseModel):
    fecha: str
    conteo: List[RightCount]

class ProcessNewsResponse(BaseModel):
    resultados: List[ProcessResult]
    noticias: List[str]  # Lista de IDs de noticias analizadas
