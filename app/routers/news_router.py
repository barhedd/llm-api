import json
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func
from datetime import datetime
from typing import List

# NUEVAS IMPORTACIONES
from app.database import get_db
from app.schemas.endpoints.news_details_schema import NewsDetailsRequest, NewsDetailsResponse
from app.schemas.endpoints.process_news_schema import ProcessNewsRequest, ProcessNewsResponse, ProcessResult, RightCount
from app.utils import files_helpers as FilesHelpers
from app.services import news_processor_service as NewsProcessorService
from app.services import fine_tune_service as FineTuneService
from app.repositories import analysis_right_repository as AnalysisRightService
from app.repositories import analysis_repository as AnalysisService
from app.repositories import news_repository as NewsService
from app.services import extract_news_service as TextMiner
from app import models

router = APIRouter()

@router.post("/process", response_model=ProcessNewsResponse)
def process_rights(data: ProcessNewsRequest, db: Session = Depends(get_db)):
    all_results = []
    all_news_id = []

    # 📌 Extraer datos de los PDFs
    pdf_files = TextMiner.leer_pdf("newspaper")
    text_extracted = TextMiner.extraer_texto_pdf(pdfs=pdf_files)

    print("DEBUG text_extracted:", text_extracted)

    fecha = TextMiner.extraer_fecha_pdf(text_extracted[1])
    news_separated = TextMiner.separar_noticias(text_extracted)
    json_output = TextMiner.formatear_json(fecha, news_separated)
    FilesHelpers.save_news_in_json(json_output)

    # Aplicar Fine-Tunning
    FineTuneService.fine_tune_llm()

    for date in data.dates:
        news_list = FilesHelpers.read_news_from_json_by_date(date)

        if not news_list:
            all_results.append({
                "fecha": date,
                "conteo": [{"derecho": d, "cantidad": 0, "lugares": [""]} for d in data.rights],
                "respuesta_cruda": "No hay noticias disponibles para esta fecha."
            })
            continue

        # 📊 Inicializar el conteo de derechos
        conteo_total = {d: {"cantidad": 0, "lugares": []} for d in data.rights}

        for noticia in news_list:
            print("DEBUG noticia:", noticia)

            # 💾 Verificar si la noticia existe en la BD
            noticia_existente = db.query(models.News).filter_by(
                headline=noticia["titular"],
                news_date=noticia["fecha"]
            ).first()

            analisis_previos = []
            derechos_previos = set()

            if noticia_existente:
                all_news_id.append(noticia_existente.id_news)

                # ✅ Buscar análisis previos asociados
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

            # 🔍 Identificar derechos ya analizados y nuevos
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

            # ✅ Ejecutar LLM para nuevos derechos
            if derechos_nuevos:
                prompt = NewsProcessorService.build_prompt(noticia, date, list(derechos_nuevos))
                respuesta_str = NewsProcessorService.get_ollama_response(prompt)

                try:
                    nuevos_items = json.loads(respuesta_str)
                    analisis += nuevos_items

                    # 💾 Guardar noticia si no existía
                    if not noticia_existente:
                        noticia_guardada = NewsService.save_news(
                            db,
                            headline=noticia["titular"],
                            content=noticia["contenido"],
                            news_date=datetime.strptime(noticia["fecha"], "%Y-%m-%d")
                        )
                        all_news_id.append(noticia_guardada.id_news)
                    else:
                        noticia_guardada = noticia_existente

                    # 💾 Guardar análisis con derechos nuevos
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

            # 📊 Acumular conteo por derecho
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

    # 📌 Validar que `all_results` no esté vacío
    if not all_results:
        all_results.append({
            "fecha": "Sin datos",
            "conteo": [{"derecho": d, "cantidad": 0, "lugares": []} for d in data.rights]
        })

    resultados = [
        ProcessResult(
            fecha=r["fecha"],
            conteo=[
                RightCount(
                    derecho=item["derecho"],
                    cantidad=item["cantidad"],
                    lugares=list(set(item["lugares"]))
                ) for item in r["conteo"]
            ]
        ) for r in all_results
    ]

    print("DEBUG: ", all_news_id)
    
    noticias = [str(n_id) for n_id in set(all_news_id)] if all_news_id else []

    return ProcessNewsResponse(resultados=resultados, noticias=noticias)

# @router.post("/extract")
# def extract_news():
#     pdf_files = TextMiner.leer_pdf("newspaper")
#     text_extracted = TextMiner.extraer_texto_pdf(pdfs=pdf_files)

#     print("DEBUG text_extracted:", text_extracted)

#     fecha = TextMiner.extraer_fecha_pdf(text_extracted[1])
#     news_separated = TextMiner.separar_noticias(text_extracted)
#     json_output = TextMiner.formatear_json(fecha, news_separated)
#     FilesHelpers.save_news_in_json(json_output)


@router.post("/details", response_model=List[NewsDetailsResponse])
def obtener_detalle_noticias(payload: NewsDetailsRequest, db: Session = Depends(get_db)):
    # Subconsulta que calcula row_number
    analysis_subquery = (
        db.query(
            models.Analysis.id_news.label("id_news"),
            models.Analysis.content.label("analysis_content"),
            func.row_number().over(
                partition_by=models.Analysis.id_news,
                order_by=models.Analysis.analysis_date.desc()
            ).label("rn")
        )
        .subquery()
    )

    # Alias de la subconsulta
    LatestAnalysis = aliased(analysis_subquery)

    # Filtrar dentro de otra subconsulta que se limite a rn = 1
    latest_analysis_only = (
        db.query(
            LatestAnalysis.c.id_news,
            LatestAnalysis.c.analysis_content
        )
        .filter(LatestAnalysis.c.rn == 1)
        .subquery()
    )

    # Consulta principal
    query = (
        db.query(
            models.News.id_news,
            models.News.headline,
            models.News.content,
            models.News.news_date,
            latest_analysis_only.c.analysis_content
        )
        .outerjoin(
            latest_analysis_only,
            latest_analysis_only.c.id_news == models.News.id_news
        )
        .filter(models.News.id_news.in_(payload.ids))
    )

    rows = query.all()
    resultado = []

    for row in rows:
        filtered = []

        if row.analysis_content:
            try:
                parsed = json.loads(row.analysis_content)
                filtered = [
                    d for d in parsed
                    if d.get("derecho") in payload.rights
                ]
            except json.JSONDecodeError:
                pass  # puedes registrar el error si deseas

        resultado.append(NewsDetailsResponse(
            id_news=row.id_news,
            headline=row.headline,
            content=row.content,
            news_date=row.news_date,
            filtered_analysis=filtered
        ))

    return resultado