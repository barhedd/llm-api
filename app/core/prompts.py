from string import Template

BASE_PROMPT = Template("""
A continuación tienes un conjunto de noticias del día ${fecha}. Cada noticia está numerada:

${lista_noticias}

Tu tarea es analizar *cada noticia por separado* y clasificarla según los siguientes derechos humanos:
${lista_derechos}

Esta es la lista oficial y completa de distritos de El Salvador:
${lista_distritos}

INSTRUCCIONES MUY ESTRICTAS:
- Para cada noticia, identifica los derechos humanos aplicables *únicamente* de la lista proporcionada.
- Debes trabajar con cada temática de derechos humanos propoporcionada.
- Luego, extrae el lugar o lugares *exactos* donde ocurre la noticia, *pero solo si aparece exactamente como está en la lista de distritos.*
- No adivines lugares. No infieras lugares. No escribas nombres que no estén en el texto original.
- Si no encuentras una coincidencia exacta entre la noticia y la lista de distritos, no escribas ningún lugar.
- Si y solo un derecho no tiene mención en ninguna noticia, inclúyelo con "cantidad": 0 y "lugares": [].
- Nunca uses valores null. Siempre incluye todas las claves: "derecho", "cantidad" y "lugares".
- Devuélveme la respuesta exclusivamente en formato JSON (sin explicaciones ni texto adicional), con esta estructura:
[{"derecho": "derecho", "cantidad": numero_de_noticias_relacionadas, "lugares": ["nombre_del_lugar", ...]}]
""")

EXTRACT_DATA_PROMPT = Template('''
Separa el texto en cada artículo informativo que presenta, la salida DEBE ser un arreglo de JSON, donde cada item contenga una clave de "titular" y "contenido". \n
[\n
  {\n
    "titular": "Aquí va el titular",\n
    "contenido": "Aquí va el contenido"\n
  }\n
]\n
TODO debe ir en español.\n
NO omitas texto.\n
NO agregues explicaciones.\n
SOLO devuelve el JSON.\n
No discrimines reportajes objetivos sobre temas controversiales.\n
Texto:\n
''')
