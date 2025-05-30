import re
import requests
import json
from typing import List
from collections import defaultdict

from app.utils import ollama_helpers as OllamaHelpers
from app.data import locations as Locations
from app.core import config, prompts

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