#!/usr/bin/env python3
"""Script ejecutor para MedSemiotics Teaching Copilot en modo 100% LOCAL.

Este script inicia el servidor FastAPI en http://127.0.0.1:8000 de forma puramente local,
sin requerir Google Cloud Run, Secret Manager ni credenciales en la nube.
"""

import os
import sys

def main() -> None:
    # Configurar entorno de desarrollo local por defecto
    os.environ.setdefault("MEDSEMIOTICS_API_TOKEN", "local-dev-token")
    os.environ.setdefault("MEDSEMIOTICS_CONFIG_ROOT", "config")

    print("=" * 70)
    print("🚀 MedSemiotics Teaching Copilot — Servidor LOCAL")
    print("=" * 70)
    print("📍 URL del Servidor Local : http://127.0.0.1:8000")
    print("🔑 Token de API Local     : local-dev-token")
    print("📂 Directorio de Config  : config/")
    print("=" * 70)
    print("💡 Endpoints disponibles:")
    print("   - Health Check        : GET http://127.0.0.1:8000/health")
    print("   - Semestre Activo     : GET http://127.0.0.1:8000/v1/semester")
    print("   - Estado de Cursos    : GET http://127.0.0.1:8000/v1/courses/NEURO/state")
    print("   - Guía Próximo Tema   : GET http://127.0.0.1:8000/v1/courses/NEURO/next-topic")
    print("=" * 70 + "\n")

    try:
        import uvicorn
        uvicorn.run("medsemiotics.api.app:app", host="127.0.0.1", port=8000, reload=True)
    except ImportError:
        print("❌ Error: uvicorn no está instalado. Instálalo con 'pip install uvicorn'")
        sys.exit(1)

if __name__ == "__main__":
    main()
