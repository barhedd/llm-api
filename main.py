import os
import re
import json
import csv
import requests
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # o especificá ["http://localhost:5173"] por ejemplo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DIRECTORIO_NOTICIAS = "noticias"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
MODEL_NAME = "gemma2:9b"
CSV_FILE = "resultados_derechos.csv"  # Archivo CSV para guardar los resultados

class DatosProcesamiento(BaseModel):
    fechas: List[str]
    derechos: List[str]

def leer_noticias_por_fecha(fecha: str) -> List[str]:
    noticias = []
    if not os.path.exists(DIRECTORIO_NOTICIAS):
        return noticias
    for archivo in os.listdir(DIRECTORIO_NOTICIAS):
        if archivo.startswith(fecha):
            ruta = os.path.join(DIRECTORIO_NOTICIAS, archivo)
            with open(ruta, "r", encoding="utf-8") as f:
                contenido = f.read().strip()
                if contenido:
                    noticias.append(contenido)
    return noticias

def construir_prompt(derechos: List[str], noticias: List[str], fecha: str) -> str:
    lista_noticias = "\n\n".join([f"Noticia {i+1}:\n{n}" for i, n in enumerate(noticias)])
    lista_derechos = "\n".join(f"- {d}" for d in derechos)
    prompt = (
        f"A continuación tienes un conjunto de noticias del día {fecha}. Cada noticia está numerada:\n\n"
        f"{lista_noticias}\n\n"
        f"Tu tarea es analizar **cada noticia por separado** y clasificarla según los siguientes derechos humanos:\n"
        f"{lista_derechos}\n\n"
        f"🧠 INSTRUCCIONES:\n"
        f"- Utiliza tu conocimiento general sobre los derechos humanos para determinar si una noticia está relacionada con alguno de ellos.\n"
        f"- No te limites únicamente a palabras clave. Interpreta el contexto completo de cada noticia.\n"
        f"- Si una noticia está relacionada con más de un derecho, cuéntala una sola vez en cada derecho correspondiente.\n"
        f"- Si una noticia menciona términos como \"muertes\", \"asesinatos\", \"homicidios\", \"feminicidios\", \"osamentas\" o \"fosas clandestinas\", considérala relacionada al derecho a la vida, pero también considera el contexto completo.\n\n"
        f"Devuélveme únicamente un JSON con la siguiente estructura (sin explicaciones ni texto adicional):\n"
        f'[{{"derecho": "nombre_del_derecho", "cantidad": numero_de_noticias_relacionadas}}, ...]'
    )
    return prompt

def obtener_respuesta_ollama(prompt: str):
    payload = {"model": MODEL_NAME, "prompt": prompt}
    response = requests.post(OLLAMA_API_URL, json=payload)

    print("\n📤 Respuesta cruda del LLM:\n", response.text, "\n")

    if not response.text.strip():
        print("❌ La respuesta del LLM está vacía.")
        return "[]"

    try:
        lines = response.text.strip().split("\n")
        responses = [json.loads(line)["response"] for line in lines if line.strip()]
        respuesta_final = "".join(responses)

        # Eliminar marcas markdown como ```json y ```
        respuesta_sin_md = respuesta_final.replace("```json", "").replace("```", "").strip()

        # Usar regex para extraer el primer bloque que parezca una lista JSON
        match = re.search(r"\[\s*{.*?}\s*]", respuesta_sin_md, re.DOTALL)
        if match:
            bloque_json = match.group(0)
            print("\n📤 Bloque JSON extraído:\n", bloque_json, "\n")
            
            # Validar que es un JSON válido
            parsed = json.loads(bloque_json)

            if isinstance(parsed, list) and all(isinstance(item, dict) and "derecho" in item and "cantidad" in item for item in parsed):
                return json.dumps(parsed)  # Devolver como string JSON
            else:
                print("⚠️ El JSON no tiene la estructura esperada.")
                return "[]"
        else:
            print("❌ No se encontró un bloque JSON válido.")
            return "[]"

    except Exception as e:
        print("❌ Error procesando respuesta:", e)
        return "[]"


def guardar_resultados_en_csv(resultados: List[dict]):
    # Verificar si el archivo no existe para agregar encabezado
    nuevo_archivo = not os.path.exists(CSV_FILE)

    with open(CSV_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["fecha", "respuesta_cruda"])
        if nuevo_archivo:
            writer.writeheader()

        for resultado in resultados:
            writer.writerow({
                "fecha": resultado["fecha"],
                "respuesta_cruda": resultado["respuesta_cruda"]
            })


@app.post("/procesar")
def procesar_derechos(datos: DatosProcesamiento):
    resultados = []

    for fecha in datos.fechas:
        noticias = leer_noticias_por_fecha(fecha)

        if not noticias:
            resultados.append({
                "fecha": fecha,
                "conteo": [{"derecho": d, "cantidad": 0} for d in datos.derechos],
                "respuesta_cruda": "No hay noticias disponibles para esta fecha."
            })
            continue

        prompt = construir_prompt(datos.derechos, noticias, fecha)
        respuesta_str = obtener_respuesta_ollama(prompt)

        try:
            conteo = json.loads(respuesta_str)
        except Exception as e:
            print("❌ Error al parsear JSON:", e)
            conteo = [{"derecho": d, "cantidad": 0} for d in datos.derechos]

        resultados.append({
            "fecha": fecha,
            "conteo": conteo,
            "respuesta_cruda": respuesta_str  # Esto se guarda solo en el CSV
        })

    # Guardar únicamente en CSV la respuesta cruda por fecha
    guardar_resultados_en_csv(resultados)

    # Devolver solo la parte que el frontend necesita
    return JSONResponse(content={
        "resultados": [
            {"fecha": r["fecha"], "conteo": r["conteo"]}
            for r in resultados
        ]
    })

