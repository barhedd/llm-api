import os
import re
from datetime import datetime
import json
from typing import List, Dict, Any
import ollama
from tika import parser
from bs4 import BeautifulSoup
from utils import logger as Logger

logger = Logger.setup_logger()

def leer_pdf(folder_name: str) -> List[str]:
    logger.info("************************LEYENDO PDFS************************")
    pdfs = []

    for archivo in os.listdir(folder_name):
        if archivo.endswith(".pdf"):
            pdfs.append(os.path.join(folder_name, archivo))

    logger.info("************************FINALIZANDO PDFS************************")
    return pdfs

def construir_prompts_extraer(instructions: str, text: str) -> str:
    prompt = f"""{instructions}\n: 
    {text}"""
    return prompt

def extraer_texo(prompt: str) -> str:
    response = ollama.chat(
        model='llama3.2-vision',
        messages=[{
            'role': 'user',
            'content': prompt
        }]
    )
    print(response)
    return response.message.content


def extraer_texto_pdf(pdfs: List[str]) -> List[str]:
    logger.info("************************INICIA EXTRACCIÓN TEXTO************************")
    structured_text = []

    parsed = parser.from_file(pdfs[0], xmlContent=True)
    xml = parsed['content']
    soup = BeautifulSoup(xml, 'lxml')
    pages = soup.find_all('div', {'class': 'page'})

    for i, page in enumerate(pages):
        text = page.get_text(separator='\n', strip=True)
        structured_text.append(text)

    logger.info("************************FINALIZA EXTRACCIÓN TEXTO************************")
    return structured_text

def limpiar_texto(texto: str) -> str:
    texto = re.sub(r'[-=~_*]{3,}', '', texto)  
    texto = re.sub(r'\n{2,}', '\n', texto)     
    texto = re.sub(r'[ \t]+', ' ', texto)   
    texto = re.sub(r'\n\s+', '\n', texto)    
    texto = texto.strip()
    texto = re.sub(r'[^a-zA-ZáéíóúÁÉÍÓÚñÑ0-9.,;:\s]', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto)
    return texto

def extraer_fecha_pdf(text : str) -> str:
    logger.info("************************INICIA EXTRACCIÓN FECHA************************")
    pattern = r"(\d{1,2}) de (enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre) de (\d{4})"

    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        dia = int(match.group(1))
        mes_texto = match.group(2).lower()
        anio = int(match.group(3))

        # Diccionario para convertir mes en texto a número
        meses = {
            "enero": 1,
            "febrero": 2,
            "marzo": 3,
            "abril": 4,
            "mayo": 5,
            "junio": 6,
            "julio": 7,
            "agosto": 8,
            "septiembre": 9,
            "octubre": 10,
            "noviembre": 11,
            "diciembre": 12
        }

        mes = meses[mes_texto]

        fecha = datetime(anio, mes, dia)
        strdate = fecha.strftime("%Y-%m-%d")
        print("Fecha extraída:", strdate)
        logger.info(f"Fecha extraída:\n{strdate}")
        logger.info("************************FINALIZA EXTRACCIÓN FECHA************************")
        return strdate
    else:
        print("No se encontró ninguna fecha.")
        return ''

def separar_noticias(news : List[str]) -> List[str]:
    h=0
    logger.info("************************INICIO SEPARACIÓN DE NOTICIAS************************")
    total_pages = len(news)
    size = 2
    json_news = []
    instructions_separate = '''
Separa el texto en cada artículo informativo que presenta, la salida DEBE ser un arreglo de JSON, donde cada item contenga una clave de "titular" y "contenido". \n
[\n
  {\n
    "titular": "Aquí va el titular",\n
    "contenido": "Aquí va el contenido"\n
  }\n
]\n
TODO debe ir en español. \n
NO omitas texto. \n
NO agregues explicaciones. \n
SOLO devuelve el JSON. \n
No discrimines reportajes objetivos sobre temas controversiales.\n
Texto:\n
'''
    logger.info("************************PROCESANDO TEXTO BLOQUE POR BLOQUE************************")
    for i in range(0, total_pages, size):
        h = h + 1
        bloque = news[i:i + size]
        texto_bloque = '\n\n'.join([f'Página #{i+1}\n{p}' for i, p in enumerate(bloque)])
        texto_bloque_clean = limpiar_texto(texto_bloque)
        logger.info(f"************************COMIENZA LLAMADA A GEMMA PARA BLOQUE {h}************************")
        logger.info(f"************************CONSTRUCCIÓN DE PROMPT************************")    
        prompt_separate = construir_prompts_extraer(instructions_separate, texto_bloque_clean)
        print(prompt_separate)
        logger.info(f"Prompt enviado al modelo (bloque {h}):\n{prompt_separate}")
        logger.info(f"************************INICIO EJECUCIÓN DE LA LLAMADA************************")  
        response = extraer_texo(prompt_separate)
        logger.info(f"Respuesta recibida por el modelo (bloque {h}):\n{response}")
        print(response)
        logger.info(f"************************TERMINA LLAMADA A GEMMA PARA BLOQUE {h}************************")
        start_index = response.find("[")
        end_index = response.rfind("]") + 1
        json_message = response[start_index:end_index]
        json_news.append(json_message)

    logger.info("************************SEPARACIÓN TEXTO BLOQUE POR BLOQUE FINALIZADO************************")
    return json_news

def formatear_json(strdate: str, json_news: List[str]) -> List[Dict[str, Any]]:
    logger.info("************************FORMATEO JSON INICIADO************************")
    fecha_str = strdate
    parsed_news = []
    ommited_items = []

    for item in json_news:
        try:
            noticias = json.loads(item) 
            for noticia in noticias:
                if isinstance(noticia, dict):
                    noticia["fecha"] = fecha_str
                    if "contenido" in noticia and isinstance(noticia["contenido"], str):
                        noticia["contenido"] = noticia["contenido"].replace('"', '')
            parsed_news.extend(noticias)
        except json.JSONDecodeError as e:
            print("Error al decodificar este item, será omitido:\n", item)
            ommited_items.append(item)
            continue
    
    logger.info(f"Noticias omitidas por no cumplir con el formato:\n{ommited_items}")
    logger.info(f"Noticias en formato JSON completas:\n{parsed_news}")
    logger.info("************************FORMATEO JSON FINALIZADO************************")
    return parsed_news

def procesar_derechos(folder_name : str):
    
    pdf_files = leer_pdf(folder_name)
    text_extracted = extraer_texto_pdf(pdfs=pdf_files)
    fecha = extraer_fecha_pdf(text_extracted[0])
    news_separated = separar_noticias(text_extracted)
    json_output = formatear_json(fecha, news_separated)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"noticias.json-{timestamp}.json"
    os.makedirs("resultados", exist_ok=True)
    filepath = os.path.join("resultados", filename)

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(json_output, filepath, ensure_ascii=False, indent=2)



