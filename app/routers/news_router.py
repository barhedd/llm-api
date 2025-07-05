from collections import defaultdict
import json
from uuid import uuid4
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, aliased
from sqlalchemy import func
from datetime import datetime
from typing import List
from app.database import get_db
from app.models.analysis import Analysis
from app.models.analysis_detail import AnalysisDetail
from app.schemas.endpoints.news_details_schema import NewsDetailsRequest, NewsDetailsResponse
from app.schemas.endpoints.process_news_schema import ProcessNewsRequest, ProcessNewsResponse, ProcessResult, RightCount
from app.utils import files_helpers as FilesHelpers
from app.services import news_processor_service as NewsProcessorService
from app.repositories import analysis_right_repository as AnalysisRightService
from app.repositories import analysis_repository as AnalysisService
from app.repositories import news_repository as NewsService
from app.services import extract_news_service as TextMiner
from app import models
from collections import defaultdict

router = APIRouter()

@router.post("/process", response_model=ProcessNewsResponse)
def process_rights(data: ProcessNewsRequest, db: Session = Depends(get_db)):
    resultados_por_fecha = defaultdict(lambda: defaultdict(lambda: {"cantidad": 0, "lugares": set()}))
    noticias_analizadas_ids = set()

    for date in data.dates:
        news_list = FilesHelpers.read_news_from_json_by_date(date)

        for news_item in news_list:
            headline = news_item["titular"]
            content = news_item["contenido"]
            fecha = news_item["fecha"]

            # Paso 1: Determinar si hay derechos faltantes
            news_entity, analysis, missing_rights = NewsProcessorService.get_missing_rights_for_news(
                db=db,
                headline=headline,
                date=fecha,
                requested_right_names=data.rights
            )

            # CASO: ya fueron analizados todos los derechos solicitados
            if not missing_rights:
                print(f"ℹ️ Todos los derechos ya fueron analizados para: {headline}")

                if analysis and analysis.content:
                    try:
                        existing_results = json.loads(analysis.content)
                        for item in existing_results:
                            if item["derecho"] in data.rights:
                                resultados_por_fecha[fecha][item["derecho"]]["cantidad"] += item["cantidad"]
                                resultados_por_fecha[fecha][item["derecho"]]["lugares"].update(item["lugares"])
                        noticias_analizadas_ids.add(str(news_entity.id_news))
                    except Exception as e:
                        print(f"⚠️ Error al procesar análisis existente para: {headline}: {e}")
                continue

            # Paso 2: Establecer contenido si es nuevo
            if not news_entity.content:
                news_entity.content = content

            # Paso 3: Crear Analysis si no existe
            if not analysis:
                analysis = Analysis(
                    id_analysis=uuid4(),
                    content="[]",  # se actualizará más adelante
                    analysis_date=datetime.now(),
                    id_news=news_entity.id_news
                )
                db.add(analysis)
                db.flush()

            # Paso 4: Construir prompt y llamar al LLM
            prompt = NewsProcessorService.build_prompt(
                noticia=news_item,
                fecha=fecha,
                derechos=[r.right for r in missing_rights]
            )

            response_json_str = NewsProcessorService.get_ollama_response(prompt)

            try:
                parsed_results = json.loads(response_json_str)

                # Agregar a resultados agrupados por fecha
                for item in parsed_results:
                    derecho = item["derecho"]
                    cantidad = item["cantidad"]
                    lugares = item["lugares"]

                    resultados_por_fecha[fecha][derecho]["cantidad"] += cantidad
                    resultados_por_fecha[fecha][derecho]["lugares"].update(lugares)

                noticias_analizadas_ids.add(str(news_entity.id_news))
            except Exception as e:
                print(f"❌ No se pudo decodificar la respuesta JSON para: {headline}")
                continue

            # Paso 5: Guardar detalles del análisis
            for item in parsed_results:
                right_match = next((r for r in missing_rights if r.right == item["derecho"]), None)
                if not right_match:
                    print(f"⚠️ Derecho inesperado devuelto por LLM: {item['derecho']}")
                    continue

                detail = AnalysisDetail(
                    id_detail=uuid4(),
                    id_analysis=analysis.id_analysis,
                    id_right=right_match.id_right,
                    count=item["cantidad"],
                    places=json.dumps(item["lugares"], ensure_ascii=False)
                )
                db.add(detail)

            db.flush()  # Asegura que los detalles estén visibles para la consulta siguiente

            # Paso 6: Reconstruir content desde analysis_detail
            content_json = NewsProcessorService.build_analysis_content_from_details(db, analysis.id_analysis)
            print("🔍 Nuevo contenido para analysis.content:\n", content_json)
            analysis.content = content_json

    db.commit()  # aplica todos los cambios

    # Paso 7: Formatear los datos al modelo de respuesta
    response_data = []

    for fecha, derechos_dict in resultados_por_fecha.items():
        conteo = [
            RightCount(
                derecho=derecho,
                cantidad=detalle["cantidad"],
                lugares=sorted(list(detalle["lugares"]))
            )
            for derecho, detalle in derechos_dict.items()
        ]

        response_data.append(ProcessResult(
            fecha=fecha,
            conteo=conteo
        ))

    return ProcessNewsResponse(
        resultados=response_data,
        noticias=list(noticias_analizadas_ids)
    )

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