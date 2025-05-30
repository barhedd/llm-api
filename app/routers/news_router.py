import json
import os
from fastapi import FastAPI, APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse
from datetime import datetime

# NUEVAS IMPORTACIONES
from app.database import get_db
from app.core import config
from app.utils import files_helpers as FilesHelpers
from app.utils import logger as Logger
from app.schemas.process_news_request import ProcessNewsRequest
from app.services import news_processor_service as NewsProcessorService
from app.services import analysis_right_service as AnalysisRightService
from app.services import analysis_service as AnalysisService
from app.services import news_service as NewsService
from app.services import extract_news_service as TextMiner
from app import models

router = APIRouter()

@router.post("/process")
def process_rights(data: ProcessNewsRequest, db: Session = Depends(get_db)):
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

            #new = NewsService.get_news(db, noticia["titular"], noticia["fecha"]) Metodo mediante service
            
            # 💾 Verificar si ya existe la noticia
            noticia_existente = db.query(models.News).filter_by(
                headline=noticia["titular"],
                news_date=noticia["fecha"]
            ).first()

            analisis_previo = None

            if noticia_existente:
                # ✅ Buscar análisis asociado a esa noticia
                analisis_previo = db.query(models.Analysis).filter_by(
                    id_news=noticia_existente.id_news
                ).order_by(models.Analysis.analysis_date.desc()).first()

                if analisis_previo:
                    # ✅ Obtener derechos asociados a ese análisis
                    derechos_analisis = db.query(models.AnalysisRight).join(models.Right).filter(
                        models.AnalysisRight.id_analysis == analisis_previo.id_analysis
                    ).with_entities(models.Right.right).all()

                    derechos_analisis_set = set(d[0] for d in derechos_analisis)

                    # ✅ Comprobar si los derechos solicitados están todos en el análisis previo
                    if set(data.rights).issubset(derechos_analisis_set):
                        print("✔️ Usando análisis previo")
                        analisis = json.loads(analisis_previo.content)
                    else:
                        analisis_previo = None  # Hay análisis pero con otros derechos

            if not analisis_previo:
                # ❌ No hay análisis previo compatible, usar el LLM
                prompt = NewsProcessorService.build_prompt(noticia, date, data.rights)
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

            # 💾 Guardar noticia
            noticia_guardada = NewsService.save_news(
                db,
                headline=noticia["titular"],
                content=noticia["contenido"],
                news_date=datetime.strptime(noticia["fecha"], "%Y-%m-%d")  # Asegúrate del formato
            )

            # 💾 Guardar análisis
            analisis_guardado = AnalysisService.save_analysis(
                db,
                content=json.dumps(analisis, ensure_ascii=False),
                news_id=noticia_guardada.id_news,
                analysis_date=datetime.today()
            )

            # 💾 Obtener IDs de derechos mencionados
            derechos_db = db.query(models.Right).filter(models.Right.right.in_(data.rights)).all()
            derechos_ids = [d.id_right for d in derechos_db]

            # 💾 Guardar relaciones en analysis_right
            AnalysisRightService.link_rights_to_analysis(
                db,
                analysis_id=analisis_guardado.id_analysis,
                rights_ids=derechos_ids
            )

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


    return JSONResponse(content={
        "resultados": [{"fecha": r["fecha"], "conteo": r["conteo"]} for r in all_results]
    })

@router.post("/extract")
def extract_news(folder_name : str):

    pdf_files = TextMiner.leer_pdf(folder_name)
    text_extracted = TextMiner.extraer_texto_pdf(pdfs=pdf_files)
    fecha = TextMiner.extraer_fecha_pdf(text_extracted[0])
    news_separated = TextMiner.separar_noticias(text_extracted)
    json_output = TextMiner.formatear_json(fecha, news_separated)
    FilesHelpers.save_news_in_json(json_output)