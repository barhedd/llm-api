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
    detailed_analysis = []

    # pdf_files = TextMiner.leer_pdf("newspaper")
    # text_extracted = TextMiner.extraer_texto_pdf(pdfs=pdf_files)

    # print("DEBUG text_extracted:", text_extracted)

    # fecha = TextMiner.extraer_fecha_pdf(text_extracted[1])
    # news_separated = TextMiner.separar_noticias(text_extracted)
    # json_output = TextMiner.formatear_json(fecha, news_separated)
    # FilesHelpers.save_news_in_json(json_output)

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

            # 💾 Verificar si ya existe la noticia
            noticia_existente = db.query(models.News).filter_by(
                headline=noticia["titular"],
                news_date=noticia["fecha"]
            ).first()

            analisis_previos = []
            derechos_previos = set()

            if noticia_existente:
                # ✅ Buscar todos los análisis asociados a esa noticia
                analisis_asociados = db.query(models.Analysis).filter_by(
                    id_news=noticia_existente.id_news
                ).order_by(models.Analysis.analysis_date.desc()).all()

                for analisis in analisis_asociados:
                    derechos_en_analisis = db.query(models.AnalysisRight).join(models.Right).filter(
                        models.AnalysisRight.id_analysis == analisis.id_analysis
                    ).with_entities(models.Right.right).all()

                    derechos_set = set(d[0] for d in derechos_en_analisis)

                    if derechos_set:
                        derechos_previos |= derechos_set
                        analisis_previos.append((analisis, derechos_set))

            # Determinar qué derechos ya han sido analizados
            derechos_solicitados = set(data.rights)
            derechos_existentes = derechos_previos & derechos_solicitados
            derechos_nuevos = derechos_solicitados - derechos_previos

            analisis = []

            # ✅ Recuperar derechos ya analizados
            if derechos_existentes:
                for analisis_previo, derechos_en_analisis in analisis_previos:
                    if derechos_en_analisis & derechos_existentes:
                        contenido = json.loads(analisis_previo.content)
                        analisis += [item for item in contenido if item["derecho"] in derechos_existentes]

            # ✅ Ejecutar LLM solo para los derechos nuevos
            if derechos_nuevos:
                prompt = NewsProcessorService.build_prompt(noticia, date, list(derechos_nuevos))
                respuesta_str = NewsProcessorService.get_ollama_response(prompt)

                try:
                    nuevos_items = json.loads(respuesta_str)
                    analisis += nuevos_items

                    # 💾 Guardar noticia solo si no existía
                    if not noticia_existente:
                        noticia_guardada = NewsService.save_news(
                            db,
                            headline=noticia["titular"],
                            content=noticia["contenido"],
                            news_date=datetime.strptime(noticia["fecha"], "%Y-%m-%d")
                        )
                    else:
                        noticia_guardada = noticia_existente

                    # 💾 Guardar nuevo análisis con derechos nuevos
                    analisis_guardado = AnalysisService.save_analysis(
                        db,
                        content=json.dumps(nuevos_items, ensure_ascii=False),
                        news_id=noticia_guardada.id_news,
                        analysis_date=datetime.now()
                    )

                    derechos_db = db.query(models.Right).filter(models.Right.right.in_(derechos_nuevos)).all()
                    derechos_ids = [d.id_right for d in derechos_db]

                    AnalysisRightService.link_rights_to_analysis(
                        db,
                        analysis_id=analisis_guardado.id_analysis,
                        rights_ids=derechos_ids
                    )

                except Exception as e:
                    print("❌ Error al parsear JSON:", e)
                    analisis += [{"derecho": d, "cantidad": 0, "lugares": []} for d in derechos_nuevos]

            # 📊 Acumular conteo total por derecho
            for item in analisis:
                derecho = item["derecho"]
                if derecho in conteo_total:
                    conteo_total[derecho]["cantidad"] += item["cantidad"]
                    conteo_total[derecho]["lugares"].extend(item["lugares"])

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

    # 💾 Guardar CSV si es necesario
    FilesHelpers.save_results_in_csv(all_results)

    return JSONResponse(content={
        "resultados": [{"fecha": r["fecha"], "conteo": r["conteo"]} for r in all_results]
    })

# @router.post("/extract")
# def extract_news(folder_name : str):
#     pdf_files = TextMiner.leer_pdf(folder_name)
#     text_extracted = TextMiner.extraer_texto_pdf(pdfs=pdf_files)
#     fecha = TextMiner.extraer_fecha_pdf(text_extracted[0])
#     news_separated = TextMiner.separar_noticias(text_extracted)
#     json_output = TextMiner.formatear_json(fecha, news_separated)
#     FilesHelpers.save_news_in_json(json_output)

@router.post("/extract")
def extract_news():
    pdf_files = TextMiner.leer_pdf("newspaper")
    text_extracted = TextMiner.extraer_texto_pdf(pdfs=pdf_files)

    print("DEBUG text_extracted:", text_extracted)

    fecha = TextMiner.extraer_fecha_pdf(text_extracted[1])
    news_separated = TextMiner.separar_noticias(text_extracted)
    json_output = TextMiner.formatear_json(fecha, news_separated)
    FilesHelpers.save_news_in_json(json_output)