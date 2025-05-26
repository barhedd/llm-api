import os
import csv
from typing import List

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