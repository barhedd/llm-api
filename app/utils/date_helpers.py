from datetime import datetime, timedelta
from typing import List

def generar_rango_fechas(fecha_inicio: str, fecha_fin: str) -> List[str]:
    """Genera una lista de fechas (YYYY-MM-DD) entre dos fechas inclusive."""
    inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
    fin = datetime.strptime(fecha_fin, "%Y-%m-%d")
    rango = []
    while inicio <= fin:
        rango.append(inicio.strftime("%Y-%m-%d"))
        inicio += timedelta(days=1)
    return rango