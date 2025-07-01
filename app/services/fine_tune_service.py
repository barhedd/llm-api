import json
import requests

from app.utils import ollama_helpers as OllamaHelpers
from app.core import config, prompts
from string import Template

def fine_tune_llm():
    prompt = prompts.FINE_TUNNING_PROMPT

    if isinstance(prompt, Template):
        prompt = prompt.safe_substitute()  # optionally pass variables inside substitute()
    else:
        prompt = str(prompt)

    try:
        payload = {"model": config.MODEL_NAME, "prompt": prompt, "temperature": 0, "top_p": 1, "stop": ["\n\n"]}
        response = requests.post(config.OLLAMA_API_URL, json=payload)
        print(response.text)

        lines = response.text.strip().split("\n")
        responses = [json.loads(line)["response"] for line in lines if line.strip()]
        respuesta_final = "".join(responses).strip()
        print(respuesta_final)
    except Exception as e:
        print("Error al realizar fine-tunning:", e)

    return respuesta_final