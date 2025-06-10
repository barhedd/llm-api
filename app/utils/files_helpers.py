import os
import csv
import json
from datetime import datetime
from typing import List, Dict, Any

from app.core import config

def read_news_by_date(date: str) -> List[str]:
    news = []
    if not os.path.exists(config.NEWS_PATH):
        return news
    for file in os.listdir(config.NEWS_PATH):
        if file.startswith(date):
            path = os.path.join(config.NEWS_PATH, file)
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content:
                    news.append(content)
    return news

def read_news_from_json_by_date(date: str) -> List[Dict[str, str]]:
    noticias_filtradas = []
    if not os.path.exists(config.NEWS_JSON_FILE):
        return noticias_filtradas

    with open(config.NEWS_JSON_FILE, "r", encoding="utf-8") as f:
        try:
            all_news = json.load(f)
        except json.JSONDecodeError:
            print("❌ Error al cargar el JSON de noticias.")
            return []

    for noticia in all_news:
        if noticia.get("fecha") == date:
            noticias_filtradas.append(noticia)

    return noticias_filtradas

def save_results_in_csv(resultados: List[dict]):
    nuevo_archivo = not os.path.exists(config.CSV_FILE)

    with open(config.CSV_FILE, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["fecha", "respuesta_cruda"])
        if nuevo_archivo:
            writer.writeheader()

        for resultado in resultados:
            writer.writerow({
                "fecha": resultado["fecha"],
                "respuesta_cruda": resultado["respuesta_cruda"]
            })

def save_news_in_json(json_output: List[Dict[str, Any]]):
    timestamp = datetime.now().strftime("%Y-%m-%d")
    # filename = f"noticias.json-{timestamp}.json"
    filename = f"news.json"
    os.makedirs("resultados", exist_ok=True)
    filepath = os.path.join("resultados", filename)

    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(json_output, file, ensure_ascii=False, indent=2)