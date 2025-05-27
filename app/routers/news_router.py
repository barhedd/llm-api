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
    all_results = []
    detailed_analysis = []  # 🔍 Análisis por noticia

    for date in data.dates:
        news_list = FilesHelpers.read_news_from_json_by_date(date)

        if not news_list:
            all_results.append({
                "fecha": date,
                "conteo": [{"derecho": d, "cantidad": 0, "lugares": [""]} for d in data.rights],
                "respuesta_cruda": "No hay noticias disponibles para esta fecha."
            })
            continue

        conteo_total = {d: {"cantidad": 0, "lugares": []} for d in data.rights}

        for noticia in news_list:
            print("DEBUG noticia:", noticia)
            prompt = NewsProcessorService.build_prompt(data.rights, [noticia], date)  # 👈 Una sola noticia
            respuesta_str = NewsProcessorService.get_ollama_response(prompt)

            try:
                analisis = json.loads(respuesta_str)
            except Exception as e:
                print("❌ Error al parsear JSON:", e)
                analisis = [{"derecho": d, "cantidad": 0, "lugares": []} for d in data.rights]

            # 📦 Acumular resultado para guardar en DB
            detailed_analysis.append({
                "fecha": noticia["fecha"],
                "titular": noticia["titular"],
                "contenido": noticia["contenido"],
                "derechos_analizados": data.rights,
                "respuesta": analisis
            })

            # 📊 Acumular conteo total por derecho
            for item in analisis:
                derecho = item["derecho"]
                conteo_total[derecho]["cantidad"] += item["cantidad"]
                conteo_total[derecho]["lugares"].extend(item["lugares"])

        # Formatear conteo acumulado
        conteo_final = [{
            "derecho": d,
            "cantidad": conteo_total[d]["cantidad"],
            "lugares": list(set(conteo_total[d]["lugares"]))
        } for d in data.rights]

        all_results.append({
            "fecha": date,
            "conteo": conteo_final,
            "respuesta_cruda": "[Individual responses collected per news item]"
        })

    # 💾 Guardar en CSV o DB si es necesario
    FilesHelpers.save_results_in_csv(all_results)
    # DatabaseHelpers.save_news_analysis_batch(detailed_analysis)  # 💾 Nuevo paso

    return JSONResponse(content={
        "resultados": [{"fecha": r["fecha"], "conteo": r["conteo"]} for r in all_results]
    })
