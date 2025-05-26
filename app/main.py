import os
import re
import json
import csv
import time
import socket
import requests
import subprocess
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy.orm import Session
from app import services, models, schemas
from .database import SessionLocal, engine

from app.routers import router as api_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # o especificá ["http://localhost:5173"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

DIRECTORIO_NOTICIAS = "noticias"
OLLAMA_API_URL = "http://localhost:11434/api/generate"
OLLAMA_HOST = "localhost"
OLLAMA_PORT = 11434
MODEL_NAME = "gemma2:9b"
CSV_FILE = "resultados_derechos.csv"

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

def cargar_noticias_desde_archivos() -> list[str]:
    noticias = []

    if not os.path.exists(DIRECTORIO_NOTICIAS):
        return noticias
    for nombre_archivo in os.listdir(DIRECTORIO_NOTICIAS):
        if nombre_archivo.endswith('.txt'):
            ruta_completa = os.path.join(DIRECTORIO_NOTICIAS, nombre_archivo)
            with open(ruta_completa, 'r', encoding='utf-8') as archivo:
                contenido = archivo.read().strip()
                if contenido:
                    noticias.append(contenido)

    return noticias

def crear_diccionario_ubicaciones() -> List[dict]:
    lista_distritos = [
        "Atiquizaya, Ahuachapán Norte, Ahuachapán",
        "El Refugio, Ahuachapán Norte, Ahuachapán",
        "San Lorenzo, Ahuachapán Norte, Ahuachapán",
        "Turín, Ahuachapán Norte, Ahuachapán",
        "Ahuachapán, Ahuachapán Centro, Ahuachapán",
        "Apaneca, Ahuachapán Centro, Ahuachapán",
        "Concepción de Ataco, Ahuachapán Centro, Ahuachapán",
        "Tacuba, Ahuachapán Centro, Ahuachapán",
        "Guaymango, Ahuachapán Sur, Ahuachapán",
        "Jujutla, Ahuachapán Sur, Ahuachapán",
        "San Francisco Menéndez, Ahuachapán Sur, Ahuachapán",
        "San Pedro Puxtla, Ahuachapán Sur, Ahuachapán",
        "Dolores, Cabañas Este, Cabañas",
        "Guacotecti, Cabañas Este, Cabañas",
        "San Isidro, Cabañas Este, Cabañas",
        "Sensuntepeque, Cabañas Este, Cabañas",
        "Victoria, Cabañas Este, Cabañas",
        "Cinquera, Cabañas Oeste, Cabañas",
        "Ilobasco, Cabañas Oeste, Cabañas",
        "Jutiapa, Cabañas Oeste, Cabañas",
        "Tejutepeque, Cabañas Oeste, Cabañas",
        "Citalá, Chalatenango Norte, Chalatenango",
        "La Palma, Chalatenango Norte, Chalatenango",
        "San Ignacio, Chalatenango Norte, Chalatenango",
        "Agua Caliente, Chalatenango Centro, Chalatenango",
        "Dulce Nombre de María, Chalatenango Centro, Chalatenango",
        "El Paraíso, Chalatenango Centro, Chalatenango",
        "La Reina, Chalatenango Centro, Chalatenango",
        "Nueva Concepción, Chalatenango Centro, Chalatenango",
        "San Fernando, Chalatenango Centro, Chalatenango",
        "San Francisco Morazán, Chalatenango Centro, Chalatenango",
        "San Rafael, Chalatenango Centro, Chalatenango",
        "Santa Rita, Chalatenango Centro, Chalatenango",
        "Tejutla, Chalatenango Centro, Chalatenango",
        "Arcatao, Chalatenango Sur, Chalatenango",
        "Azacualpa, Chalatenango Sur, Chalatenango",
        "San José Cancasque, Chalatenango Sur, Chalatenango",
        "Chalatenango, Chalatenango Sur, Chalatenango",
        "Comalapa, Chalatenango Sur, Chalatenango",
        "Concepción Quezaltepeque, Chalatenango Sur, Chalatenango",
        "El Carrizal, Chalatenango Sur, Chalatenango",
        "La Laguna, Chalatenango Sur, Chalatenango",
        "Las Flores, Chalatenango Sur, Chalatenango",
        "Las Vueltas, Chalatenango Sur, Chalatenango",
        "Nombre de Jesús, Chalatenango Sur, Chalatenango",
        "Nueva Trinidad, Chalatenango Sur, Chalatenango",
        "Ojos de Agua, Chalatenango Sur, Chalatenango",
        "Potonico, Chalatenango Sur, Chalatenango",
        "San Antonio de la Cruz, Chalatenango Sur, Chalatenango",
        "San Antonio Los Ranchos, Chalatenango Sur, Chalatenango",
        "San Francisco Lempa, Chalatenango Sur, Chalatenango",
        "San Isidro Labrador, Chalatenango Sur, Chalatenango",
        "San Luis del Carmen, Chalatenango Sur, Chalatenango",
        "San Miguel de Mercedes, Chalatenango Sur, Chalatenango",
        "Oratorio de Concepción, Cuscatlán Norte, Cuscatlán",
        "San Bartolomé Perulapía, Cuscatlán Norte, Cuscatlán",
        "San José Guayabal, Cuscatlán Norte, Cuscatlán",
        "San Pedro Perulapán, Cuscatlán Norte, Cuscatlán",
        "Suchitoto, Cuscatlán Norte, Cuscatlán",
        "Candelaria, Cuscatlán Sur, Cuscatlán",
        "Cojutepeque, Cuscatlán Sur, Cuscatlán",
        "El Carmen, Cuscatlán Sur, Cuscatlán",
        "El Rosario, Cuscatlán Sur, Cuscatlán",
        "Monte San Juan, Cuscatlán Sur, Cuscatlán",
        "San Cristóbal, Cuscatlán Sur, Cuscatlán",
        "San Rafael Cedros, Cuscatlán Sur, Cuscatlán",
        "San Ramón, Cuscatlán Sur, Cuscatlán",
        "Santa Cruz Analquito, Cuscatlán Sur, Cuscatlán",
        "Santa Cruz Michapa, Cuscatlán Sur, Cuscatlán",
        "Tenancingo, Cuscatlán Sur, Cuscatlán",
        "Quezaltepeque, La Libertad Norte, La Libertad",
        "San Matías, La Libertad Norte, La Libertad",
        "San Pablo Tacachico, La Libertad Norte, La Libertad",
        "Ciudad Arce, La Libertad Centro, La Libertad",
        "San Juan Opico, La Libertad Centro, La Libertad",
        "Colón, La Libertad Oeste, La Libertad",
        "Jayaque, La Libertad Oeste, La Libertad",
        "Sacacoyo, La Libertad Oeste, La Libertad",
        "Talnique, La Libertad Oeste, La Libertad",
        "Tepecoyo, La Libertad Oeste, La Libertad",
        "Antiguo Cuscatlán, La Libertad Este, La Libertad",
        "Huizúcar, La Libertad Este, La Libertad",
        "Nuevo Cuscatlán, La Libertad Este, La Libertad",
        "San José Villanueva, La Libertad Este, La Libertad",
        "Zaragoza, La Libertad Este, La Libertad",
        "Chiltiupán, La Libertad Costa, La Libertad",
        "Jicalapa, La Libertad Costa, La Libertad",
        "La Libertad, La Libertad Costa, La Libertad",
        "Tamanique, La Libertad Costa, La Libertad",
        "Teotepeque, La Libertad Costa, La Libertad",
        "Comasagua, La Libertad Sur, La Libertad",
        "Santa Tecla, La Libertad Sur, La Libertad",
        "Cuyultitán, La Paz Oeste, La Paz",
        "Olocuilta, La Paz Oeste, La Paz",
        "San Francisco Chinameca, La Paz Oeste, La Paz",
        "San Juan Talpa, La Paz Oeste, La Paz",
        "San Luis Talpa, La Paz Oeste, La Paz",
        "San Pedro Masahuat, La Paz Oeste, La Paz",
        "Tapalhuaca, La Paz Oeste, La Paz",
        "El Rosario, La Paz Centro, La Paz",
        "Jerusalén, La Paz Centro, La Paz",
        "Mercedes La Ceiba, La Paz Centro, La Paz",
        "Paraíso de Osorio, La Paz Centro, La Paz",
        "San Antonio Masahuat, La Paz Centro, La Paz",
        "San Emigdio, La Paz Centro, La Paz",
        "San Juan Tepezontes, La Paz Centro, La Paz",
        "San Luis La Herradura, La Paz Centro, La Paz",
        "San Miguel Tepezontes, La Paz Centro, La Paz",
        "San Pedro Nonualco, La Paz Centro, La Paz",
        "Santa María Ostuma, La Paz Centro, La Paz",
        "Santiago Nonualco, La Paz Centro, La Paz",
        "San Juan Nonualco, La Paz Este, La Paz",
        "San Rafael Obrajuelo, La Paz Este, La Paz",
        "Zacatecoluca, La Paz Este, La Paz",
        "Anamorós, La Unión Norte, La Unión",
        "Bolívar, La Unión Norte, La Unión",
        "Concepción de Oriente, La Unión Norte, La Unión",
        "El Sauce, La Unión Norte, La Unión",
        "Lislique, La Unión Norte, La Unión",
        "Nueva Esparta, La Unión Norte, La Unión",
        "Pasaquina, La Unión Norte, La Unión",
        "Polorós, La Unión Norte, La Unión",
        "San José, La Unión Norte, La Unión",
        "Santa Rosa de Lima, La Unión Norte, La Unión",
        "Conchagua, La Unión Sur, La Unión",
        "El Carmen, La Unión Sur, La Unión",
        "Intipucá, La Unión Sur, La Unión",
        "La Unión, La Unión Sur, La Unión",
        "Meanguera del Golfo, La Unión Sur, La Unión",
        "San Alejo, La Unión Sur, La Unión",
        "Yayantique, La Unión Sur, La Unión",
        "Yucuaiquín, La Unión Sur, La Unión",
        "Arambala, Morazán Norte, Morazán",
        "Cacaopera, Morazán Norte, Morazán",
        "Corinto, Morazán Norte, Morazán",
        "El Rosario, Morazán Norte, Morazán",
        "Joateca, Morazán Norte, Morazán",
        "Jocoaitique, Morazán Norte, Morazán",
        "Meanguera, Morazán Norte, Morazán",
        "Perquín, Morazán Norte, Morazán",
        "San Fernando, Morazán Norte, Morazán",
        "San Isidro, Morazán Norte, Morazán",
        "Torola, Morazán Norte, Morazán",
        "Chilanga, Morazán Sur, Morazán",
        "Delicias de Concepción, Morazán Sur, Morazán",
        "El Divisadero, Morazán Sur, Morazán",
        "Gualococti, Morazán Sur, Morazán",
        "Guatajiagua, Morazán Sur, Morazán",
        "Jocoro, Morazán Sur, Morazán",
        "Lolotiquillo, Morazán Sur, Morazán",
        "Osicala, Morazán Sur, Morazán",
        "San Carlos, Morazán Sur, Morazán",
        "San Francisco Gotera, Morazán Sur, Morazán",
        "San Simón, Morazán Sur, Morazán",
        "Sensembra, Morazán Sur, Morazán",
        "Sociedad, Morazán Sur, Morazán",
        "Yamabal, Morazán Sur, Morazán",
        "Yoloaiquín, Morazán Sur, Morazán",
        "Carolina, San Miguel Norte, San Miguel",
        "Chapeltique, San Miguel Norte, San Miguel",
        "Ciudad Barrios, San Miguel Norte, San Miguel",
        "Nuevo Edén de San Juan, San Miguel Norte, San Miguel",
        "San Antonio, San Miguel Norte, San Miguel",
        "San Gerardo, San Miguel Norte, San Miguel",
        "San Luis de la Reina, San Miguel Norte, San Miguel",
        "Sesori, San Miguel Norte, San Miguel",
        "Chirilagua, San Miguel Centro, San Miguel",
        "Comacarán, San Miguel Centro, San Miguel",
        "Moncagua, San Miguel Centro, San Miguel",
        "Quelepa, San Miguel Centro, San Miguel",
        "San Miguel, San Miguel Centro, San Miguel",
        "Uluazapa, San Miguel Centro, San Miguel",
        "Chinameca, San Miguel Oeste, San Miguel",
        "El Tránsito, San Miguel Oeste, San Miguel",
        "Lolotique, San Miguel Oeste, San Miguel",
        "Nueva Guadalupe, San Miguel Oeste, San Miguel",
        "San Jorge, San Miguel Oeste, San Miguel",
        "San Rafael Oriente, San Miguel Oeste, San Miguel",
        "Aguilares, San Salvador Norte, San Salvador",
        "El Paisnal, San Salvador Norte, San Salvador",
        "Guazapa, San Salvador Norte, San Salvador",
        "Apopa, San Salvador Oeste, San Salvador",
        "Nejapa, San Salvador Oeste, San Salvador",
        "Ayutuxtepeque, San Salvador Centro, San Salvador",
        "Cuscatancingo, San Salvador Centro, San Salvador",
        "Delgado, San Salvador Centro, San Salvador",
        "Mejicanos, San Salvador Centro, San Salvador",
        "San Salvador, San Salvador Centro, San Salvador",
        "Ilopango, San Salvador Este, San Salvador",
        "San Martín, San Salvador Este, San Salvador",
        "Soyapango, San Salvador Este, San Salvador",
        "Tonacatepeque, San Salvador Este, San Salvador",
        "Panchimalco, San Salvador Sur, San Salvador",
        "Rosario de Mora, San Salvador Sur, San Salvador",
        "San Marcos, San Salvador Sur, San Salvador",
        "Santiago Texacuangos, San Salvador Sur, San Salvador",
        "Santo Tomás, San Salvador Sur, San Salvador",
        "Apastepeque, San Vicente Norte, San Vicente",
        "San Esteban Catarina, San Vicente Norte, San Vicente",
        "San Ildefonso, San Vicente Norte, San Vicente",
        "San Lorenzo, San Vicente Norte, San Vicente",
        "San Sebastián, San Vicente Norte, San Vicente",
        "Santa Clara, San Vicente Norte, San Vicente",
        "Santo Domingo, San Vicente Norte, San Vicente",
        "Guadalupe, San Vicente Sur, San Vicente",
        "San Cayetano Istepeque, San Vicente Sur, San Vicente",
        "San Vicente, San Vicente Sur, San Vicente",
        "Tecoluca, San Vicente Sur, San Vicente",
        "Tepetitán, San Vicente Sur, San Vicente",
        "Verapaz, San Vicente Sur, San Vicente",
        "Masahuat, Santa Ana Norte, Santa Ana",
        "Metapán, Santa Ana Norte, Santa Ana",
        "Santa Rosa Guachipilín, Santa Ana Norte, Santa Ana",
        "Texistepeque, Santa Ana Norte, Santa Ana",
        "Santa Ana, Santa Ana Centro, Santa Ana",
        "Coatepeque, Santa Ana Este, Santa Ana",
        "El Congo, Santa Ana Este, Santa Ana",
        "Candelaria de la Frontera, Santa Ana Oeste, Santa Ana",
        "Chalchuapa, Santa Ana Oeste, Santa Ana",
        "El Porvenir, Santa Ana Oeste, Santa Ana",
        "San Antonio Pajonal, Santa Ana Oeste, Santa Ana",
        "San Sebastián Salitrillo, Santa Ana Oeste, Santa Ana",
        "Santiago de la Frontera, Santa Ana Oeste, Santa Ana",
        "Juayúa, Sonsonate Norte, Sonsonate",
        "Nahuizalco, Sonsonate Norte, Sonsonate",
        "Salcoatitán, Sonsonate Norte, Sonsonate",
        "Santa Catarina Masahuat, Sonsonate Norte, Sonsonate",
        "Nahulingo, Sonsonate Centro, Sonsonate",
        "San Antonio del Monte, Sonsonate Centro, Sonsonate",
        "Santo Domingo de Guzmán, Sonsonate Centro, Sonsonate",
        "Sonsonate, Sonsonate Centro, Sonsonate",
        "Sonzacate, Sonsonate Centro, Sonsonate",
        "Armenia, Sonsonate Este, Sonsonate",
        "Caluco, Sonsonate Este, Sonsonate",
        "Cuisnahuat, Sonsonate Este, Sonsonate",
        "Izalco, Sonsonate Este, Sonsonate",
        "San Julián, Sonsonate Este, Sonsonate",
        "Santa Isabel Ishuatán, Sonsonate Este, Sonsonate",
        "Acajutla, Sonsonate Oeste, Sonsonate",
        "Alegría, Usulután Norte, Sonsonate",
        "Berlín, Usulután Norte, Sonsonate",
        "El Triunfo, Usulután Norte, Sonsonate",
        "Estanzuelas, Usulután Norte, Sonsonate",
        "Jucuapa, Usulután Norte, Sonsonate",
        "Mercedes Umaña, Usulután Norte, Sonsonate",
        "Nueva Granada, Usulután Norte, Sonsonate",
        "San Buenaventura, Usulután Norte, Sonsonate",
        "Santiago de María, Usulután Norte, Sonsonate",
        "California, Usulután Este, Sonsonate",
        "Concepción Batres, Usulután Este, Sonsonate",
        "Ereguayquín, Usulután Este, Sonsonate",
        "Jucuarán, Usulután Este, Sonsonate",
        "Ozatlán, Usulután Este, Sonsonate",
        "San Dionisio, Usulután Este, Sonsonate",
        "Santa Elena, Usulután Este, Sonsonate",
        "Santa María, Usulután Este, Sonsonate",
        "Tecapán, Usulután Este, Sonsonate",
        "Usulután, Usulután Este, Sonsonate",
        "Jiquilisco, Usulután Oeste, Sonsonate",
        "Puerto El Triunfo, Usulután Oeste, Sonsonate",
        "San Agustín, Usulután Oeste, Sonsonate",
        "San Francisco Javier, Usulután Oeste, Sonsonate"
    ]

    ubicaciones_es = [
        {
            "distrito": partes[0].strip(),
            "municipio": partes[1].strip(),
            "departamento": partes[2].strip()
        }
        for partes in (elemento.split(",") for elemento in lista_distritos)
    ]

    return ubicaciones_es

def extraer_lugares_candidatos(noticias: List[str]) -> List[str]:
    texto_total = noticias.lower()
    ubicaciones = crear_diccionario_ubicaciones()
    coincidencias = []

    for ubicacion in ubicaciones:
        for clave in ["distrito"]:
            valor = ubicacion["distrito"].lower()
            if re.search(rf'\b{re.escape(valor)}\b', texto_total):
                coincidencias.append(ubicacion["distrito"])
                break

    return coincidencias

def construir_prompt(derechos: List[str], noticias: List[str], fecha: str) -> str:
    lista_noticias = "\n\n".join([f"Noticia {i+1}:\n{n}" for i, n in enumerate(noticias)])
    lista_derechos = "\n".join(f"- {d}" for d in derechos)
    lista_distritos = extraer_lugares_candidatos(lista_noticias)
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

def esta_ollama_levantado(host=OLLAMA_HOST, port=OLLAMA_PORT):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False

def verificar_y_levantar_ollama():
    if not esta_ollama_levantado():
        print("🟡 Ollama no está corriendo. Intentando levantarlo...")
        try:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for i in range(10):
                if esta_ollama_levantado():
                    print("✅ Ollama levantado correctamente.")
                    return True
                time.sleep(1)
            print("❌ No se pudo levantar Ollama después de varios intentos.")
            return False
        except Exception as e:
            print("❌ Error al intentar levantar Ollama:", e)
            return False
    else:
        print("✅ Ollama ya está corriendo.")
        return True

def obtener_respuesta_ollama(prompt: str):
    if not verificar_y_levantar_ollama():
        return "[]"
    
    payload = {"model": MODEL_NAME, "prompt": prompt, "temperature": 0, "top_p": 1, "stop": ["\n\n"]}
    response = requests.post(OLLAMA_API_URL, json=payload)

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

def guardar_resultados_en_csv(resultados: List[dict]):
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
                "conteo": [{"derecho": d, "cantidad": 0, "lugares": [""]} for d in datos.derechos],
                "respuesta_cruda": "No hay noticias disponibles para esta fecha."
            })
            continue

        prompt = construir_prompt(datos.derechos, noticias, fecha)
        respuesta_str = obtener_respuesta_ollama(prompt)

        try:
            conteo = json.loads(respuesta_str)
        except Exception as e:
            print("❌ Error al parsear JSON:", e)
            conteo = [{"derecho": d, "cantidad": 0, "lugar": [""]} for d in datos.derechos]

        resultados.append({
            "fecha": fecha,
            "conteo": conteo,
            "respuesta_cruda": respuesta_str
        })

    guardar_resultados_en_csv(resultados)

    return JSONResponse(content={
        "resultados": [
            {"fecha": r["fecha"], "conteo": r["conteo"]}
            for r in resultados
        ]
    })
