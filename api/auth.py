import os
from fastapi import APIRouter, Request, Response
from pydantic import BaseModel

router = APIRouter(prefix="/api")


def _load_professor_logins() -> dict[str, str]:
    """
    Lê do .env:
    PROFESSOR_LOGINS=65:123,70:abc456
    e retorna {"65":"123", "70":"abc456"}
    """
    raw = (os.getenv("PROFESSOR_LOGINS") or "").strip()
    d: dict[str, str] = {}
    if not raw:
        return d
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        pid, pwd = pair.split(":", 1)
        d[pid.strip()] = pwd.strip()
    return d


class LoginRequest(BaseModel):
    professor_id: str
    senha: str


# Armazena sessões simples em memória (suficiente para uso local)
_sessions: dict[str, int] = {}


@router.post("/login")
async def login(req: LoginRequest, response: Response):
    logins = _load_professor_logins()
    pid = req.professor_id.strip()
    pwd = req.senha

    if not pid or not pwd:
        return {"status": "erro", "mensagem": "Preencha ID e senha."}

    if pid not in logins or logins[pid] != pwd:
        return {"status": "erro", "mensagem": "ID ou senha inválidos."}

    # Cria sessão via cookie
    session_id = f"session_{pid}"
    _sessions[session_id] = int(pid)
    response.set_cookie(key="session_id", value=session_id, httponly=True)

    return {"status": "sucesso", "professor_id": int(pid)}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(key="session_id")
    return {"status": "sucesso"}


@router.get("/me")
async def me(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in _sessions:
        return {"logged_in": False}

    return {"logged_in": True, "professor_id": _sessions[session_id]}


def get_professor_id(request: Request) -> int | None:
    """Helper para obter professor_id da sessão atual."""
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in _sessions:
        return None
    return _sessions[session_id]
