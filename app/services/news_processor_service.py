import re
import httpx
import json
from uuid import uuid4
from datetime import datetime
from typing import List, Set
from sqlalchemy.orm import Session
from collections import defaultdict
from fastapi import WebSocket, WebSocketDisconnect
from app.services import fine_tune_service as FineTuneService
from app.models.analysis import Analysis
from app.models.analysis_detail import AnalysisDetail
from app.models.news import News
from app.models.right import Right
from app.schemas.endpoints.process_news_schema import ProcessResult, RightCount
from app.utils import ollama_helpers as OllamaHelpers
from app.data import locations as Locations
from app.core import config, prompts
from app.utils import files_helpers as FilesHelpers
from typing import List, Tuple, Optional

async def process_news_batch(
    db: Session,
    dates: List[str],
    rights: List[str],
    websocket: Optional[WebSocket] = None
) -> Tuple[List[ProcessResult], List[str]]:
    resultados_por_fecha = defaultdict(lambda: defaultdict(lambda: {"cantidad": 0, "lugares": set()}))
    noticias_analizadas_ids: Set[str] = set()

    # ✅ Obtener todas las noticias de todas las fechas
    all_news = FilesHelpers.read_news_by_dates(dates)
    total_news = len(all_news)
    progress_actual = 0.0
    progress_per_news = 100 / total_news

    async def enviar_progreso(etapa: str, progreso_global: float):
        if websocket:
            await websocket.send_json({
                "type": "progress",
                "etapa": etapa,
                "progreso": round(progreso_global, 2)
            })

    for idx, news_item in enumerate(all_news):
        # Verificar si el cliente sigue conectado
        try:
            await websocket.send_json({"type": "ping"})
        except WebSocketDisconnect:
            if websocket:
                await websocket.send_json({
                    "type": "error",
                    "message": "El cliente ha cerrado la conexión. El procesamiento ha sido cancelado."
                })
            return resultados_por_fecha, list(noticias_analizadas_ids)

        progress_local = 0.0
        headline = news_item["titular"]
        content = news_item["contenido"]
        fecha = news_item["fecha"]

        # 1. Cargando titulares
        progress_local += progress_per_news * 0.05
        await enviar_progreso("Cargando titulares", progress_actual + progress_local)

        # 2. Determinar derechos faltantes
        news_entity, analysis, missing_rights = get_missing_rights_for_news(
            db=db,
            headline=headline,
            date=fecha,
            requested_right_names=rights
        )

        progress_local += progress_per_news * 0.15
        await enviar_progreso("Determinando derechos", progress_actual + progress_local)

        if not missing_rights:
            if analysis and analysis.content:
                try:
                    existing_results = json.loads(analysis.content)
                    for item in existing_results:
                        if item["derecho"] in rights:
                            resultados_por_fecha[fecha][item["derecho"]]["cantidad"] += item["cantidad"]
                            resultados_por_fecha[fecha][item["derecho"]]["lugares"].update(item["lugares"])
                    noticias_analizadas_ids.add(str(news_entity.id_news))
                except Exception as e:
                    if websocket:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Error al leer análisis previo para '{headline}': {str(e)}"
                        })
            progress_actual += progress_per_news
            await enviar_progreso("Ya analizada previamente", progress_actual)
            continue

        if not news_entity.content:
            news_entity.content = content

        if not analysis:
            analysis = Analysis(
                id_analysis=uuid4(),
                content="[]",
                analysis_date=datetime.now(),
                id_news=news_entity.id_news
            )
            db.add(analysis)
            db.flush()

        # 3. Fine tuning
        if websocket:
            await websocket.send_json({
                "type": "status",
                "message": f"Enviando a LLM: {headline[:60]}",
                "fecha": fecha
            })

        FineTuneService.fine_tune_llm()
        progress_local += progress_per_news * 0.20
        await enviar_progreso("Fine tuning", progress_actual + progress_local)

        # 4. Llamada al LLM
        prompt = build_prompt(noticia=news_item, fecha=fecha, derechos=[r.right for r in missing_rights])
        response_json_str = await get_ollama_response_async(prompt)
        progress_local += progress_per_news * 0.50
        await enviar_progreso("Llamada a LLM", progress_actual + progress_local)

        try:
            parsed_results = json.loads(response_json_str)
            for item in parsed_results:
                resultados_por_fecha[fecha][item["derecho"]]["cantidad"] += item["cantidad"]
                resultados_por_fecha[fecha][item["derecho"]]["lugares"].update(item["lugares"])
            noticias_analizadas_ids.add(str(news_entity.id_news))
        except Exception as e:
            if websocket:
                await websocket.send_json({
                    "type": "error",
                    "message": f"❌ Error al interpretar respuesta del LLM para '{headline}': {str(e)}"
                })
            continue

        for item in parsed_results:
            right_match = next((r for r in missing_rights if r.right == item["derecho"]), None)
            if not right_match:
                continue
            detail = AnalysisDetail(
                id_detail=uuid4(),
                id_analysis=analysis.id_analysis,
                id_right=right_match.id_right,
                count=item["cantidad"],
                places=json.dumps(item["lugares"], ensure_ascii=False)
            )
            db.add(detail)

        db.flush()
        analysis.content = build_analysis_content_from_details(db, analysis.id_analysis)

        # 5. Guardando resultados
        progress_local += progress_per_news * 0.10
        progress_actual += progress_local
        await enviar_progreso("Guardando resultados", progress_actual)

    db.commit()

    resultados_finales = []
    for fecha, derechos_dict in resultados_por_fecha.items():
        conteo = [
            RightCount(
                derecho=derecho,
                cantidad=detalle["cantidad"],
                lugares=sorted(list(detalle["lugares"]))
            )
            for derecho, detalle in derechos_dict.items()
        ]
        resultados_finales.append(ProcessResult(fecha=fecha, conteo=conteo))

    if websocket:
        await websocket.send_json({
            "type": "result",
            "resultados": [r.dict() for r in resultados_finales],
            "noticias": list(noticias_analizadas_ids)
        })

    return resultados_finales, list(noticias_analizadas_ids)

def get_missing_rights_for_news(
    db: Session,
    headline: str,
    date: str,
    requested_right_names: List[str]
) -> Tuple[Optional[News], Optional[Analysis], List[Right]]:
    """
    Verifica qué derechos aún no han sido analizados para una noticia dada.
    Retorna la noticia (creada o existente), el análisis (creado o existente) y los derechos faltantes.
    """
    parsed_date = datetime.strptime(date, "%Y-%m-%d")

    # 1. Buscar o crear la noticia
    news_entity = (
        db.query(News)
        .filter(News.headline == headline, News.news_date == parsed_date)
        .first()
    )

    if not news_entity:
        news_entity = News(
            id_news=uuid4(),
            headline=headline,
            content="",  # Se llenará luego con el contenido real
            news_date=parsed_date,
        )
        db.add(news_entity)
        db.flush()  # para obtener id_news

    # 2. Buscar análisis existente para esa noticia
    analysis = (
        db.query(Analysis)
        .filter(Analysis.id_news == news_entity.id_news)
        .first()
    )

    # 3. Obtener IDs de derechos solicitados
    rights_requested = (
        db.query(Right)
        .filter(Right.right.in_(requested_right_names))
        .all()
    )

    if not analysis:
        # No hay análisis aún => todos los derechos están pendientes
        return news_entity, None, rights_requested

    # 4. Obtener derechos ya analizados
    analyzed_right_ids = {
        detail.id_right for detail in analysis.details
    }

    # 5. Determinar derechos faltantes
    missing_rights = [
        r for r in rights_requested if r.id_right not in analyzed_right_ids
    ]

    return news_entity, analysis, missing_rights

def build_prompt(noticia: dict, fecha: str, derechos: List[str]) -> str:
    texto = noticia["contenido"]
    lista_noticias = f"1. {texto}"
    lista_derechos = "\n".join(f"- {d}" for d in derechos)
    lista_distritos = get_candidates_locations(texto)

    return prompts.BASE_PROMPT.substitute(
        fecha=fecha,
        lista_noticias=lista_noticias,
        lista_derechos=lista_derechos,
        lista_distritos="\n".join(f"- {d}" for d in lista_distritos)
    )

def get_candidates_locations(noticia: str) -> List[str]:
    ubicaciones = Locations.get_el_salvador_locations()
    coincidencias = []

    for ubicacion in ubicaciones:
        for clave in ["distrito"]:
            valor = ubicacion["distrito"].lower()
            if re.search(rf'\b{re.escape(valor)}\b', noticia):
                coincidencias.append(ubicacion["distrito"])
                break

    return coincidencias

async def get_ollama_response_async(prompt: str) -> str:
    if not OllamaHelpers.verify_and_run_ollama():
        return "[]"

    payload = {
        "model": config.MODEL_NAME,
        "prompt": prompt,
        "temperature": 0,
        "top_p": 1,
        "stop": ["\n\n"]
    }

    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(config.OLLAMA_API_URL, json=payload)

        print("\n📤 Respuesta cruda del LLM:\n", response.text, "\n")

        if not response.text.strip():
            print("❌ La respuesta del LLM está vacía.")
            return "[]"

        lines = response.text.strip().split("\n")
        responses = [json.loads(line)["response"] for line in lines if line.strip()]
        respuesta_final = "".join(responses).strip()

        if isinstance(respuesta_final, list):
            parsed = respuesta_final
        else:
            respuesta_sin_md = respuesta_final.replace("```json", "").replace("```", "").strip()

            match = re.search(r"\[\s*(?:{.*?}\s*,?\s*)+\]", respuesta_sin_md, re.DOTALL)
            if not match:
                print("❌ No se encontró un bloque JSON válido.")
                return "[]"

            bloque_json = match.group(0)
            parsed = json.loads(bloque_json)

        if isinstance(parsed, list) and all(
            isinstance(item, dict) and
            "derecho" in item and
            "cantidad" in item and
            "lugares" in item and
            isinstance(item["lugares"], list)
            for item in parsed):
            return json.dumps(parsed, ensure_ascii=False)
        else:
            print("⚠️ El JSON no tiene la estructura esperada.")
            return "[]"

    except httpx.RequestError as e:
        print(f"❌ Error de red al consultar Ollama: {e}")
        return "[]"
    except Exception as e:
        print("❌ Error procesando respuesta:", e)
        return "[]"
    
def build_analysis_content_from_details(db: Session, analysis_id: str) -> str:
    """
    Reconstruye el JSON de content a partir de analysis_detail para un analysis dado.
    """
    details = (
        db.query(AnalysisDetail)
        .join(Right, Right.id_right == AnalysisDetail.id_right)
        .filter(AnalysisDetail.id_analysis == analysis_id)
        .all()
    )

    resultado = []
    for d in details:
        resultado.append({
            "derecho": d.right.right,
            "cantidad": d.count,
            "lugares": json.loads(d.places) if d.places else []
        })

    return json.dumps(resultado, ensure_ascii=False)