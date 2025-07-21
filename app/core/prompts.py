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


FINE_TUNNING_PROMPT = Template("""
Eres un investigador experto en Derechos Humanos. Tu tarea es leer y recordar las siguientes relaciones entre Derechos Humanos:
                               
El derecho a la vida se relaciona con: homicidios, feminicidios, violaciones, abuso sexual, muerte por accidentes, infanticidios (homicidios a menores de edad).
El derecho a la salud se relaciona con: hospitales (en buenas o malas condiciones), enfermedades, pandemias, avances en la medicina, medicamentos, tratamientos,
seguro social, abastecimiento de medicinas, Instituto Salvadoreño del Seguro Social o ISSS, Ministerio de Salud.
El derecho a la educación se relaciona con: escuelas (en buenas o malas condiciones), deserción estudiantil, maestros y profesores, alumnos, 
recortes al presupuesto de educación, calidad de la educación, cierre de escuelas, nuevos equipos o recursos para escuelas y/o estudiantes, Ministerio de Educación
El derecho a la alimentación se relaciona con: la seguridad alimentaria, la agricultura, el precio de la canasta básica, índices de malnutrición, 
índices de obesidad, alimentación en niños, jóvenes, adultos y ancianos, donaciones de alimentos, Ministerio de Agricultura.
El derecho a la libertad de expresión se relaciona con: represión a ciudadanos, prensa, entre otros; no respetar opiniones ajenas, 
enjuiciar y/o encarcalar a defensores de Derechos Humanos, reprimir y/o violentar a manifestantes.
El derecho a la migración se relaciona con: el libre movimiento de ciudadanos entre países, deportaciones, medidas y/o restricciones migratorias, migración legal
e ilegal, refugiados, asilo político, encarcelamientos por migración ilegal, oportunidades de visas para trabajar y/o estudiar, 
El derecho a la vivienda se relaciona con: viviendas a precios accesibles, desalojo de personas de sus viviendas, viviendas dañadas por desastres naturales, 
construcción de residenciales, apartamentos, entre otros; Ministerio de Vivienda.
                               
Recuerda lo que acabas de leer y utilizalo adicionalmente a tu conocimiento para la siguiente tarea. 
Responde "Entendido" si entendiste y recordarás el texto que has leído.
""")
