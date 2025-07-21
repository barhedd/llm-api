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
from app.models import analysis as AnalysisModel
from app.models import news as NewsModel

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
            
        # Leer PDFs de la carpeta "newspaper"
        pdf_files = TextMiner.leer_pdf("newspaper")
        await websocket.send_json({
            "type": "progress",
            "etapa": "Minado de noticias",
            "message": "PDF leídos",
            "progreso": 4
        })

        await websocket.send_json({"type": "status", "message": "Extrayendo texto de PDFs"})

        # Extraer texto de los PDFs
        text_extracted = TextMiner.extraer_texto_pdf(pdfs=pdf_files)
        await websocket.send_json({
            "type": "progress",
            "etapa": "Minado de noticias",
            "message": "Texto extraído de PDFs",
            "progreso": 12
        })

        print("DEBUG text_extracted:", text_extracted)

        await websocket.send_json({"type": "status", "message": "Separando y formateando noticias mediante IA"})
        
        # Extraer fecha del primer elemento del texto extraído
        fecha = TextMiner.extraer_fecha_pdf(text_extracted[1])
        
        # Separar noticias utilizando IA
        news_separated = TextMiner.separar_noticias(text_extracted)
        await websocket.send_json({
            "type": "progress",
            "etapa": "Minado de noticias",
            "message": "Noticias separadas por IA",
            "progreso": 25
        })

        # Formatear noticias en JSON
        json_output = TextMiner.formatear_json(fecha, news_separated)

        # Guardar noticias en un archivo JSON
        news_filepath = FilesHelpers.save_news_in_json(json_output)
        await websocket.send_json({
            "type": "progress",
            "etapa": "minado",
            "message": "Noticias formateadas en JSON",
            "progreso": 30
        })

        # Ejecutar el análisis de noticias
        await websocket.send_json({"type": "status", "message": "Iniciando análisis de noticias"})

        resultados, noticias_ids = await NewsProcessorService.process_news_batch(
            db=db,
            news_filepath=news_filepath,
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
    """
    Devuelve los detalles de noticias con su análisis asociado,
    filtrando solo los derechos solicitados.
    """

    # Consulta directa: News JOIN Analysis (uno a uno)
    query = (
        db.query(
            NewsModel.News.id_news,
            NewsModel.News.headline,
            NewsModel.News.content,
            NewsModel.News.news_date,
            AnalysisModel.Analysis.content.label("analysis_content")
        )
        .outerjoin(AnalysisModel.Analysis, NewsModel.News.id_news == AnalysisModel.Analysis.id_news)
        .filter(NewsModel.News.id_news.in_(payload.ids))
    )

    rows = query.all()
    resultado = []

    for row in rows:
        filtered_analysis = []

        if row.analysis_content:
            try:
                parsed = json.loads(row.analysis_content)
                filtered_analysis = [
                    item for item in parsed
                    if item.get("derecho") in payload.rights
                ]
            except json.JSONDecodeError:
                # Si el análisis no es JSON válido, lo ignoramos
                pass

        resultado.append(NewsDetailsResponse(
            id_news=row.id_news,
            headline=row.headline,
            content=row.content,
            news_date=row.news_date,
            filtered_analysis=filtered_analysis
        ))

    return resultado