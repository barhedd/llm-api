import json
from fastapi import APIRouter, Depends, WebSocket
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func
from datetime import datetime
from typing import List
from app.database import get_db
from app.schemas.endpoints.news_details_schema import NewsDetailsRequest, NewsDetailsResponse
from app.utils import files_helpers as FilesHelpers
from app.services import news_processor_service as NewsProcessorService
from app.repositories import analysis_repository as AnalysisRepository
from app.repositories import news_repository as NewsRepository
from app.services import extract_news_service as TextMiner
from app.utils import date_helpers as DateHelpers
from app import models

router = APIRouter()

@router.websocket("/ws/process")
async def process_rights_ws(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()

    try:
        payload = await websocket.receive_json()

        fechas = payload.get("dates", [])
        derechos = payload.get("rights", [])

        # Validación de presencia y tipo
        if not isinstance(fechas, list) or not fechas:
            await websocket.send_json({
                "type": "error",
                "message": "El campo 'dates' es obligatorio y debe ser una lista no vacía."
            })
            return

        if not isinstance(derechos, list) or not derechos:
            await websocket.send_json({
                "type": "error",
                "message": "El campo 'rights' es obligatorio y debe ser una lista no vacía."
            })
            return

        # Validación de formato de fechas
        for f in fechas:
            try:
                datetime.strptime(f, "%Y-%m-%d")
            except ValueError:
                await websocket.send_json({
                    "type": "error",
                    "message": f"La fecha '{f}' no tiene el formato válido YYYY-MM-DD."
                })
                return
            
        fecha_inicio, fecha_fin = fechas[0], fechas[1]
        dates_rango = DateHelpers.generar_rango_fechas(fecha_inicio, fecha_fin)
            
        await websocket.send_json({"type": "status", "message": "Iniciando minado de noticias"})
            
        # # Leer PDFs de la carpeta "newspaper"
        # pdf_files = TextMiner.leer_pdf("newspaper")
        # await websocket.send_json({
        #     "type": "progress",
        #     "etapa": "Minado de noticias",
        #     "message": "PDF leídos",
        #     "progreso": 4
        # })

        # await websocket.send_json({"type": "status", "message": "Extrayendo texto de PDFs"})

        # # Extraer texto de los PDFs
        # text_extracted = TextMiner.extraer_texto_pdf(pdfs=pdf_files)
        # await websocket.send_json({
        #     "type": "progress",
        #     "etapa": "Minado de noticias",
        #     "message": "Texto extraído de PDFs",
        #     "progreso": 12
        # })

        # print("DEBUG text_extracted:", text_extracted)

        # await websocket.send_json({"type": "status", "message": "Separando y formateando noticias mediante IA"})
        
        # # Extraer fecha del primer elemento del texto extraído
        # fecha = TextMiner.extraer_fecha_pdf(text_extracted[1])
        
        # # Separar noticias utilizando IA
        # news_separated = TextMiner.separar_noticias(text_extracted)
        # await websocket.send_json({
        #     "type": "progress",
        #     "etapa": "Minado de noticias",
        #     "message": "Noticias separadas por IA",
        #     "progreso": 25
        # })

        # # Formatear noticias en JSON
        # json_output = TextMiner.formatear_json(fecha, news_separated)

        # # Guardar noticias en un archivo JSON
        # news_filepath = FilesHelpers.save_news_in_json(json_output)
        # await websocket.send_json({
        #     "type": "progress",
        #     "etapa": "minado",
        #     "message": "Noticias formateadas en JSON",
        #     "progreso": 30
        # })

        # Ejecutar el análisis de noticias
        await websocket.send_json({"type": "status", "message": "Iniciando análisis de noticias"})

        resultados, noticias_ids = await NewsProcessorService.process_news_batch(
            db=db,
            news_filepath="resultados/news.json",
            dates=dates_rango,
            rights=derechos,
            websocket=websocket
        )

        await websocket.send_json({
            "type": "result",
            "resultados": [r.dict() for r in resultados],
            "noticias": noticias_ids
        })

    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "message": f"Error inesperado: {str(e)}"
        })

    finally:
        await websocket.close()


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