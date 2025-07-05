import re
from uuid import uuid4
import requests
import json
from typing import List
from app.models.analysis import Analysis
from app.models.analysis_detail import AnalysisDetail
from app.models.news import News
from app.models.right import Right
from app.utils import ollama_helpers as OllamaHelpers
from app.data import locations as Locations
from app.core import config, prompts
from sqlalchemy.orm import Session
from typing import List, Tuple, Optional
from datetime import datetime

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

def get_ollama_response(prompt: str):
    if not OllamaHelpers.verify_and_run_ollama():
        return "[]"
    
    payload = {"model": config.MODEL_NAME, "prompt": prompt, "temperature": 0, "top_p": 1, "stop": ["\n\n"]}
    response = requests.post(config.OLLAMA_API_URL, json=payload)

    print("\n📤 Respuesta cruda del LLM:\n", response.text, "\n")

    if not response.text.strip():
        print("❌ La respuesta del LLM está vacía.")
        return "[]"

    try:
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