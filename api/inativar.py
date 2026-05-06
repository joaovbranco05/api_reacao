"""
Router FastAPI — Inativação de Matrículas em Lote (API EAD WebService).

Endpoint: POST /api/inativar-lote
Entrada  : arquivo .xlsx com colunas "Nome do Aluno" e "Nome do Curso"
Saída    : JSON com resultados + planilha de log disponível para download

Fluxo por linha:
    1. Lê nome do aluno e nome do curso da planilha
    2. Consulta getMatriculas (paginado) para achar o MatriculaID ativo
    3. Chama POST /web_service/situacao com Situacao=I
    4. Registra resultado (sucesso / erro)
"""
from __future__ import annotations

import io
import logging
import os
from datetime import datetime

import openpyxl
from fastapi import APIRouter, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from unidecode import unidecode

from api.auth import get_professor_id
from core.ead_client import EADClient
from core.ead_resolver import EADResolver

logger = logging.getLogger("api.inativar")
logging.basicConfig(level=logging.DEBUG)

router = APIRouter(prefix="/api")

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

def _norm(s: str) -> str:
    return unidecode(str(s or "").strip().lower())


def _get_ead_client() -> EADClient:
    return EADClient(
        base_url=os.getenv("EAD_BASE_URL"),
        username=os.getenv("EAD_USERNAME"),
        password=os.getenv("EAD_PASSWORD"),
        api_key=os.getenv("EAD_API_KEY"),
    )


def _parse_xlsx(xlsx_bytes: bytes) -> list[dict[str, str]]:
    """
    Lê o .xlsx e retorna lista de dicts com chaves 'nome_aluno' e 'nome_curso'.

    Estratégia de detecção de colunas:
    - Linha 1 é tratada como cabeçalho.
    - Procura (case-insensitive, sem acento) por variações de "nome do aluno" e "nome do curso".
    """
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_bytes), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))

    if not rows:
        raise ValueError("Planilha vazia.")

    header = [_norm(str(c)) for c in rows[0]]

    # Detectar índice da coluna de aluno
    aluno_idx = _find_col(header, [
        "nome do aluno", "nome aluno", "aluno", "nome_aluno", "student", "nome"
    ])
    # Detectar índice da coluna de curso
    curso_idx = _find_col(header, [
        "nome do curso", "nome curso", "curso", "nome_curso", "course", "disciplina"
    ])

    if aluno_idx is None:
        raise ValueError(
            f"Coluna 'Nome do Aluno' não encontrada. "
            f"Cabeçalhos detectados: {rows[0]}"
        )
    if curso_idx is None:
        raise ValueError(
            f"Coluna 'Nome do Curso' não encontrada. "
            f"Cabeçalhos detectados: {rows[0]}"
        )

    result = []
    for row in rows[1:]:
        # Ignora linhas completamente vazias
        if all(c is None or str(c).strip() == "" for c in row):
            continue
        nome_aluno = str(row[aluno_idx] or "").strip()
        nome_curso = str(row[curso_idx] or "").strip()
        if nome_aluno or nome_curso:
            result.append({"nome_aluno": nome_aluno, "nome_curso": nome_curso})

    return result


def _find_col(header: list[str], candidates: list[str]) -> int | None:
    for cand in candidates:
        if cand in header:
            return header.index(cand)
    # Busca por substring
    for cand in candidates:
        for i, h in enumerate(header):
            if cand in h or h in cand:
                return i
    return None


def _build_output_xlsx(resultados: list[dict]) -> bytes:
    """Gera planilha Excel de log com os resultados do processamento."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Resultado Inativação"

    headers = ["#", "Nome do Aluno", "Nome do Curso", "MatriculaID", "Status", "Mensagem"]
    ws.append(headers)

    # Estilos de cabeçalho
    from openpyxl.styles import Font, PatternFill, Alignment
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill("solid", fgColor="1a1a2e")
    for cell in ws[1]:
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")

    # Estilos por status
    fill_ok = PatternFill("solid", fgColor="d4edda")
    fill_err = PatternFill("solid", fgColor="f8d7da")
    fill_warn = PatternFill("solid", fgColor="fff3cd")

    for r in resultados:
        row_data = [
            r.get("linha", ""),
            r.get("nome_aluno", ""),
            r.get("nome_curso", ""),
            r.get("matricula_id", ""),
            r.get("status", ""),
            r.get("mensagem", ""),
        ]
        ws.append(row_data)
        row_idx = ws.max_row
        status = str(r.get("status", "")).lower()
        fill = fill_ok if status == "inativado" else (fill_warn if "aviso" in status else fill_err)
        for cell in ws[row_idx]:
            cell.fill = fill

    # Ajuste automático de largura de colunas
    col_widths = [5, 35, 40, 15, 15, 60]
    for col, width in zip(ws.columns, col_widths):
        ws.column_dimensions[col[0].column_letter].width = width

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ──────────────────────────────────────────────
# Endpoint principal
# ──────────────────────────────────────────────

@router.post("/inativar-lote")
async def inativar_lote(request: Request, file: UploadFile = File(...)):
    """
    Recebe uma planilha .xlsx com colunas 'Nome do Aluno' e 'Nome do Curso'
    e inativa as matrículas correspondentes na API EAD.
    """
    professor_id = get_professor_id(request)
    if professor_id is None:
        return {"status": "erro", "mensagem": "Faça login para usar esta função."}

    if not file.filename.lower().endswith(".xlsx"):
        return {"status": "erro", "mensagem": "Envie um arquivo .xlsx"}

    try:
        xlsx_bytes = await file.read()
        rows = _parse_xlsx(xlsx_bytes)
    except ValueError as ve:
        return {"status": "erro", "mensagem": str(ve)}
    except Exception as exc:
        return {"status": "erro", "mensagem": f"Erro ao ler planilha: {exc}"}

    if not rows:
        return {"status": "erro", "mensagem": "Planilha sem dados (apenas cabeçalho?)."}

    # Verificar configuração EAD no .env
    try:
        client = _get_ead_client()
    except ValueError as ve:
        return {"status": "erro", "mensagem": str(ve)}

    resolver = EADResolver(client)

    total = len(rows)
    ok = 0
    erros = 0
    resultados: list[dict] = []

    logger.info("=== Iniciando inativação em lote: %d linhas ===", total)

    for i, row in enumerate(rows, start=1):
        nome_aluno = row["nome_aluno"]
        nome_curso = row["nome_curso"]
        resultado: dict = {
            "linha": i,
            "nome_aluno": nome_aluno,
            "nome_curso": nome_curso,
            "matricula_id": "",
            "status": "",
            "mensagem": "",
        }

        logger.debug("\n%s\nLinha %d: aluno='%s', curso='%s'", "=" * 60, i, nome_aluno, nome_curso)

        try:
            if not nome_aluno:
                raise ValueError("Nome do aluno em branco.")
            if not nome_curso:
                raise ValueError("Nome do curso em branco.")

            # 1. Resolver MatriculaID
            resolved = resolver.resolve(nome_aluno=nome_aluno, nome_curso=nome_curso)
            matricula_id = resolved["matricula_id"]
            resultado["matricula_id"] = matricula_id
            logger.debug("Linha %d: MatriculaID=%s encontrado", i, matricula_id)

            # 2. Inativar
            resp = client.set_situacao(matricula_id=matricula_id, situacao="I")
            logger.debug("Linha %d: resposta inativação=%s", i, resp)

            # Interpretar resposta da API EAD
            # A API pode retornar sucesso com código 200 e body variando
            resp_status = str(resp.get("status") or resp.get("Status") or "").lower()
            resp_msg = (
                resp.get("mensagem")
                or resp.get("message")
                or resp.get("Message")
                or resp.get("msg")
                or str(resp)
            )

            if resp_status in ("sucesso", "success", "ok", "1", "true") or resp.get("MatriculaID"):
                ok += 1
                resultado["status"] = "Inativado"
                resultado["mensagem"] = f"MatriculaID {matricula_id} inativado com sucesso. API: {resp_msg}"
            else:
                erros += 1
                resultado["status"] = "Erro API"
                resultado["mensagem"] = f"API recusou inativação do MatriculaID {matricula_id}: {resp}"

        except ValueError as ve:
            erros += 1
            resultado["status"] = "Não encontrado"
            resultado["mensagem"] = str(ve)
            logger.warning("Linha %d: %s", i, ve)

        except Exception as exc:
            erros += 1
            resultado["status"] = "Erro"
            resultado["mensagem"] = f"{type(exc).__name__}: {exc}"
            logger.exception("Linha %d: erro inesperado", i)

        resultados.append(resultado)

    logger.info("=== Inativação concluída: OK=%d | ERRO=%d ===", ok, erros)

    return {
        "status": "sucesso",
        "total": total,
        "ok": ok,
        "erros": erros,
        "resultados": resultados,
    }


@router.post("/inativar-lote/download")
async def inativar_lote_download(request: Request, file: UploadFile = File(...)):
    """
    Mesmo processamento do endpoint acima, mas retorna diretamente
    o arquivo Excel de resultado para download.
    """
    professor_id = get_professor_id(request)
    if professor_id is None:
        return {"status": "erro", "mensagem": "Faça login para usar esta função."}

    if not file.filename.lower().endswith(".xlsx"):
        return {"status": "erro", "mensagem": "Envie um arquivo .xlsx"}

    try:
        xlsx_bytes = await file.read()
        rows = _parse_xlsx(xlsx_bytes)
    except ValueError as ve:
        return {"status": "erro", "mensagem": str(ve)}

    if not rows:
        return {"status": "erro", "mensagem": "Planilha sem dados."}

    try:
        client = _get_ead_client()
    except ValueError as ve:
        return {"status": "erro", "mensagem": str(ve)}

    resolver = EADResolver(client)
    resultados: list[dict] = []

    for i, row in enumerate(rows, start=1):
        nome_aluno = row["nome_aluno"]
        nome_curso = row["nome_curso"]
        resultado: dict = {
            "linha": i,
            "nome_aluno": nome_aluno,
            "nome_curso": nome_curso,
            "matricula_id": "",
            "status": "",
            "mensagem": "",
        }
        try:
            if not nome_aluno:
                raise ValueError("Nome do aluno em branco.")
            if not nome_curso:
                raise ValueError("Nome do curso em branco.")
            resolved = resolver.resolve(nome_aluno=nome_aluno, nome_curso=nome_curso)
            matricula_id = resolved["matricula_id"]
            resultado["matricula_id"] = matricula_id
            resp = client.set_situacao(matricula_id=matricula_id, situacao="I")
            resp_status = str(resp.get("status") or resp.get("Status") or "").lower()
            resp_msg = (
                resp.get("mensagem") or resp.get("message") or resp.get("Message") or str(resp)
            )
            if resp_status in ("sucesso", "success", "ok", "1", "true") or resp.get("MatriculaID"):
                resultado["status"] = "Inativado"
                resultado["mensagem"] = f"Inativado com sucesso. API: {resp_msg}"
            else:
                resultado["status"] = "Erro API"
                resultado["mensagem"] = f"API recusou: {resp}"
        except ValueError as ve:
            resultado["status"] = "Não encontrado"
            resultado["mensagem"] = str(ve)
        except Exception as exc:
            resultado["status"] = "Erro"
            resultado["mensagem"] = f"{type(exc).__name__}: {exc}"
        resultados.append(resultado)

    xlsx_out = _build_output_xlsx(resultados)
    filename = f"resultado_inativacao_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return StreamingResponse(
        io.BytesIO(xlsx_out),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
