import re
import requests
import json
from typing import List

from app.utils import ollama_helpers as OllamaHelpers
from app.data import locations as Locations
from app.core import config

def build_prompt(derechos: List[str], noticias: List[str], fecha: str) -> str:
    lista_noticias = "\n\n".join([f"Noticia {i+1}:\n{n}" for i, n in enumerate(noticias)])
    lista_derechos = "\n".join(f"- {d}" for d in derechos)
    lista_distritos = get_candidates_locations(lista_noticias)
    prompt = (
        f"A continuación tienes un conjunto de noticias del día {fecha}. Cada noticia está numerada:\n\n"
        f"{lista_noticias}\n\n"
        f"Tu tarea es analizar *cada noticia por separado* y clasificarla según los siguientes derechos humanos:\n"
        f"{lista_derechos}\n\n"
        f"Esta es la lista oficial y completa de distritos de El Salvador:\n"
        f"{lista_distritos}\n\n"
        f"INSTRUCCIONES MUY ESTRICTAS:\n"
        f"- Para cada noticia, identifica los derechos humanos aplicables *únicamente* de la lista proporcionada.\n"
        f"- Debes trabajar con cada temática de derechos humanos propoporcionada.\n"
        f"- Luego, extrae el lugar o lugares *exactos* donde ocurre la noticia, *pero solo si aparece exactamente como está en la lista de distritos.*\n"
        f"- No adivines lugares. No infieras lugares. No escribas nombres que no estén en el texto original.\n"
        f"- Si no encuentras una coincidencia exacta entre la noticia y la lista de distritos, no escribas ningún lugar.\n"
        f"- Si y solo un derecho no tiene mención en ninguna noticia, inclúyelo con \"cantidad\": 0 y \"lugares\": [].\n"
        f"- Nunca uses valores null. Siempre incluye todas las claves: \"derecho\", \"cantidad\" y \"lugares\".\n"
        f"- Devuélveme la respuesta exclusivamente en formato JSON (sin explicaciones ni texto adicional), con esta estructura:\n"
        f'[{{"derecho": "derecho", "cantidad": numero_de_noticias_relacionadas, "lugares": ["nombre_del_lugar", ...]}}, ...]'
    )
    return prompt

def get_candidates_locations(noticias: List[str]) -> List[str]:
    texto_total = noticias.lower()
    ubicaciones = Locations.get_el_salvador_locations()
    coincidencias = []

    for ubicacion in ubicaciones:
        for clave in ["distrito"]:
            valor = ubicacion["distrito"].lower()
            if re.search(rf'\b{re.escape(valor)}\b', texto_total):
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