import os
import sys
import webbrowser
import threading
import uvicorn
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

# --- Resolve paths for PyInstaller bundled mode ---
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent

# Load .env from the directory where the .exe is located (or project root in dev)
if getattr(sys, "frozen", False):
    env_path = Path(sys.executable).parent / ".env"
else:
    env_path = BASE_DIR / ".env"

if not env_path.exists():
    print("=" * 60)
    print("   [ERRO CRÍTICO] ARQUIVO .env NÃO ENCONTRADO!   ")
    print("=" * 60)
    print(f"O executável precisa do arquivo .env na mesma pasta para ler as senhas")
    print(f"e a configuração do iScholar. Crie um arquivo '.env' em:")
    print(f"-> {env_path}")
    print("\nCom o seguinte conteúdo:")
    print("ISCHOLAR_CODIGO_ESCOLA=SUA_ESCOLA")
    print("ISCHOLAR_TOKEN_ACESSO=SEU_TOKEN")
    print("PROFESSOR_LOGINS=123:senha1,456:senha2")
    print("\nPressione ENTER para sair...")
    input()
    sys.exit(1)

load_dotenv(env_path)

# --- FastAPI App ---
app = FastAPI(title="API Reação - iScholar")

# Register API routers
from api.auth import router as auth_router
from api.notas import router as notas_router

app.include_router(auth_router)
app.include_router(notas_router)

# Serve static files
static_dir = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root():
    return FileResponse(str(static_dir / "index.html"))


@app.get("/dashboard.html")
async def dashboard():
    return FileResponse(str(static_dir / "dashboard.html"))


@app.get("/lote.html")
async def lote():
    return FileResponse(str(static_dir / "lote.html"))


def open_browser():
    """Abre o navegador após um pequeno delay."""
    import time
    time.sleep(2)
    webbrowser.open("http://localhost:8000")


if __name__ == "__main__":
    print("=" * 50)
    print("  API Reação - Sistema de Notas iScholar")
    print("=" * 50)
    print()
    print("  Abrindo navegador em http://localhost:8000")
    print("  Para parar, feche esta janela ou Ctrl+C.")
    print()

    # Abre navegador em background
    threading.Thread(target=open_browser, daemon=True).start()

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")
