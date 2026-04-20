import os
import logging
from fastapi import APIRouter, Request, UploadFile, File
from unidecode import unidecode

from api.auth import get_professor_id
from core.ischolar_client import IScholarClient, IScholarConfig
from core.ischolar_resolver import IScholarResolver, norm
from core.validators import parse_nota
from core.batch_excel_nomes import parse_excel_bytes_named

logger = logging.getLogger("api.notas")
logging.basicConfig(level=logging.DEBUG)

router = APIRouter(prefix="/api")


def _get_client() -> IScholarClient:
    codigo = os.getenv("ISCHOLAR_CODIGO_ESCOLA")
    token = os.getenv("ISCHOLAR_TOKEN_ACESSO")
    if not codigo or not token:
        raise ValueError("Configure ISCHOLAR_CODIGO_ESCOLA e ISCHOLAR_TOKEN_ACESSO no .env")
    cfg = IScholarConfig(codigo_escola=codigo, token_acesso=token)
    return IScholarClient(cfg)


def _norm_local(s: str) -> str:
    return unidecode((s or "").strip().lower())


def _resolve_professor_from_disc(disc: dict, professor_nome: str) -> int | None:
    """
    Tenta resolver o id_professor a partir dos dados da disciplina.
    O campo 'professores' pode ser: dict, list de dicts, ou ausente.
    """
    prof_data = disc.get("professores")

    logger.debug("=== PROFESSOR RESOLUTION ===")
    logger.debug(f"  Professor buscado na planilha: '{professor_nome}'")
    logger.debug(f"  Campo 'professores' da disciplina (tipo={type(prof_data).__name__}): {prof_data}")

    # Normalizar para lista
    if isinstance(prof_data, dict):
        prof_list = [prof_data]
    elif isinstance(prof_data, list):
        prof_list = prof_data
    else:
        prof_list = []

    logger.debug(f"  Lista de professores normalizada ({len(prof_list)} itens): {prof_list}")

    for prof_obj in prof_list:
        prof_nome_vinc = (prof_obj.get("nome_professor") or "").strip()
        prof_id_vinc = prof_obj.get("id_professor")

        nome_planilha_norm = _norm_local(professor_nome)
        nome_vinc_norm = _norm_local(prof_nome_vinc)

        logger.debug(f"  Comparando: planilha='{nome_planilha_norm}' vs vinculado='{nome_vinc_norm}' (id={prof_id_vinc})")

        if prof_id_vinc and prof_nome_vinc and (
            nome_planilha_norm in nome_vinc_norm
            or nome_vinc_norm in nome_planilha_norm
        ):
            logger.debug(f"  ✅ Match encontrado! id_professor={prof_id_vinc}")
            return int(prof_id_vinc)

    logger.debug("  ❌ Nenhum match encontrado na lista de professores da disciplina")
    return None


@router.post("/lote")
async def enviar_lote(request: Request, file: UploadFile = File(...)):
    professor_id = get_professor_id(request)
    if professor_id is None:
        return {"status": "erro", "mensagem": "Faça login para lançar notas."}

    if not file.filename.lower().endswith(".xlsx"):
        return {"status": "erro", "mensagem": "Envie um arquivo .xlsx"}

    try:
        xlsx_bytes = await file.read()
        rows = parse_excel_bytes_named(xlsx_bytes)

        codigo = os.getenv("ISCHOLAR_CODIGO_ESCOLA")
        token = os.getenv("ISCHOLAR_TOKEN_ACESSO")

        if not codigo or not token:
            return {"status": "erro", "mensagem": "Falta ISCHOLAR_CODIGO_ESCOLA ou ISCHOLAR_TOKEN_ACESSO no .env"}

        resolver = IScholarResolver(codigo_escola=codigo, token=token, unidade="")
        client = _get_client()

        total = len(rows)
        ok = 0
        resultados = []

        for i, r in enumerate(rows, start=1):
            try:
                logger.debug(f"\n{'='*60}")
                logger.debug(f"LINHA {i}: aluno='{r.aluno_nome}', turma='{r.turma_nome}', "
                           f"professor='{r.professor_nome}', materia='{r.materia_nome}', "
                           f"avaliacao='{r.avaliacao_nome}', nota='{r.nota}'")

                valor_float = parse_nota(r.nota)
                id_matricula, id_turma = resolver.resolve_matricula_e_turma(r.aluno_nome, r.turma_nome)
                logger.debug(f"  id_matricula={id_matricula}, id_turma={id_turma}")

                disc = resolver.resolve_disciplina(id_turma, r.materia_nome)
                id_disciplina = int(disc["id_disciplina"])
                logger.debug(f"  id_disciplina={id_disciplina}")
                logger.debug(f"  Disciplina completa: {disc}")

                # Tentar resolver professor pela disciplina
                id_professor_resolved = _resolve_professor_from_disc(disc, r.professor_nome)

                # Fallback: buscar por endpoint de professores
                if id_professor_resolved is None:
                    logger.debug("  Usando fallback: resolve_professor_id_por_matricula")
                    id_professor_resolved = resolver.resolve_professor_id_por_matricula(
                        id_matricula, r.professor_nome
                    )
                    logger.debug(f"  Fallback retornou: id_professor={id_professor_resolved}")

                id_avaliacao = resolver.resolve_avaliacao_id(id_turma, r.avaliacao_nome)
                logger.debug(f"  id_avaliacao={id_avaliacao}")
                logger.debug(f"  >>> Enviando nota: matricula={id_matricula}, disciplina={id_disciplina}, "
                           f"avaliacao={id_avaliacao}, professor={id_professor_resolved}, valor={valor_float}")

                resp = client.lancar_nota(
                    id_matricula=id_matricula,
                    id_disciplina=id_disciplina,
                    id_avaliacao=id_avaliacao,
                    id_professor=id_professor_resolved,
                    valor=valor_float,
                )

                logger.debug(f"  Resposta API: {resp}")

                if isinstance(resp, dict) and resp.get("status") == "sucesso":
                    ok += 1
                    resultados.append({"linha": i, "status": "sucesso", "mensagem": resp.get("mensagem", "")})
                else:
                    resultados.append({"linha": i, "status": "erro", "mensagem": f"API recusou: {resp}"})

            except Exception as e:
                logger.exception(f"  ERRO na linha {i}")
                resultados.append({"linha": i, "status": "erro", "mensagem": f"{type(e).__name__}: {e}"})

        return {
            "status": "sucesso",
            "total": total,
            "ok": ok,
            "erros": total - ok,
            "resultados": resultados,
        }

    except Exception as e:
        return {"status": "erro", "mensagem": f"Falha no lote ({type(e).__name__}): {e}"}
