import os
import json
from datetime import datetime
from typing import List, Dict, Any
from uuid import uuid4

def read_news_by_dates(filepath: str, dates: List[str]) -> List[Dict[str, str]]:
    news = []
    if not os.path.exists(filepath):
        return news

    with open(filepath, "r", encoding="utf-8") as f:
        try:
            all_news = json.load(f)
        except json.JSONDecodeError:
            print("❌ Error al cargar el JSON de noticias.")
            return []

    for noticia in all_news:
        if noticia.get("fecha") in dates:
            news.append(noticia)

    return news

def save_news_in_json(json_output: List[Dict[str, Any]]) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d")
    session_id = str(uuid4())
    filename = f"news-{timestamp}-{session_id}.json"
    os.makedirs("resultados", exist_ok=True)
    filepath = os.path.join("resultados", filename)

    with open(filepath, "w", encoding="utf-8") as file:
        json.dump(json_output, file, ensure_ascii=False, indent=2)

    return filepath