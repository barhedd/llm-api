BASE_PROMPT = (
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
