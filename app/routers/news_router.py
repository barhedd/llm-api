import json
from fastapi import FastAPI, APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

# NUEVAS IMPORTACIONES
from app.core import config
from app.utils import files_helpers as FilesHelpers
from app.schemas.process_news_request import ProcessNewsRequest
from app.services import news_processor_service as NewsProcessorService

router = APIRouter()

@router.post("/process")
def process_rights(data: ProcessNewsRequest):
    results = []

    for date in data.dates:
        news = FilesHelpers.read_news_by_date(date)

        if not news:
            results.append({
                "fecha": date,
                "conteo": [{"derecho": d, "cantidad": 0, "lugares": [""]} for d in data.rights],
                "respuesta_cruda": "No hay noticias disponibles para esta fecha."
            })
            continue

        prompt = NewsProcessorService.build_prompt(data.rights, news, date)
        respuesta_str = NewsProcessorService.get_ollama_response(prompt)

        try:
            quantity = json.loads(respuesta_str)
        except Exception as e:
            print("❌ Error al parsear JSON:", e)
            quantity = [{"derecho": d, "cantidad": 0, "lugares": [""]} for d in data.rights]

        results.append({
            "fecha": date,
            "conteo": quantity,
            "respuesta_cruda": respuesta_str
        })

    FilesHelpers.save_results_in_csv(results)

    return JSONResponse(content={
        "resultados": [
            {"fecha": r["fecha"], "conteo": r["conteo"]}
            for r in results
        ]
    })
