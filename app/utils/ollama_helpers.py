import socket
import subprocess

from app.core import config

def is_ollama_running(host=config.OLLAMA_HOST, port=config.OLLAMA_PORT):
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False

def verify_and_run_ollama():
    if not is_ollama_running():
        print("🟡 Ollama no está corriendo. Intentando levantarlo...")
        try:
            subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for i in range(10):
                if is_ollama_running():
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