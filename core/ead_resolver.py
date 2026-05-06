"""
Resolver para a API EAD WebService.

Responsabilidade: dado o nome do aluno e o nome do curso (como vêm da planilha),
localizar o MatriculaID ativo correspondente via consultas paginadas à API.

Estratégia:
1. Buscar matrículas ativas paginadas filtrando por nome (quando suportado pela API).
2. Normalizar strings (remove acentos, lowercase) para comparação tolerante a erros.
3. Fazer correspondência fuzzy (difflib) para nomes ligeiramente diferentes.
4. Retornar o MatriculaID + metadados encontrados.
"""
from __future__ import annotations

import logging
from difflib import get_close_matches
from unidecode import unidecode

from core.ead_client import EADClient

logger = logging.getLogger("core.ead_resolver")


def norm(s: str) -> str:
    """Normaliza string: remove acentos, lowercase, strip."""
    return unidecode(str(s or "").strip().lower())


class EADResolver:
    """
    Resolve nomes de aluno + curso → MatriculaID ativo na API EAD.

    Uso:
        resolver = EADResolver(client)
        result = resolver.resolve(nome_aluno="João Silva", nome_curso="Enfermagem EAD")
        # result = {"matricula_id": 12345, "nome": "João Silva", "curso": "Enfermagem EAD", ...}
    """

    def __init__(self, client: EADClient):
        self.client = client
        # Cache de matrículas para evitar múltiplos GETs na mesma sessão
        self._cache: list[dict] | None = None

    # ------------------------------------------------------------------
    # Carregamento de matrículas (com paginação)
    # ------------------------------------------------------------------

    def _load_all_active(self) -> list[dict]:
        """
        Carrega TODAS as matrículas ativas via paginação.
        Resultado é cacheado em memória para a sessão de processamento.

        A API EAD pode retornar:
          - Uma lista JSON diretamente: [{...}, {...}]
          - Um dict com chave "dados" / "registros" / "result": {"dados": [...]}
        Ambos os formatos são tratados aqui.
        Além disso, a API pode ignorar o filtro Situacao no servidor;
        por isso filtramos Situacao='A' no lado do cliente também.
        """
        if self._cache is not None:
            return self._cache

        logger.info("Carregando matrículas ativas da API EAD...")
        all_records: list[dict] = []
        
        try:
            # A API EAD muitas vezes ignora a paginação e retorna TODOS os
            # registros de uma vez. Faremos apenas uma requisição para evitar loops infinitos.
            resp = self.client.get_matriculas(
                situacao="A",
                pagina=1,
                registros_pagina=10000,
            )
        except Exception as exc:
            logger.error("Erro ao buscar matrículas na API: %s", exc)
            raise

        # ── Normalizar o formato da resposta ────────────────────────
        if isinstance(resp, list):
            registros = resp
        elif isinstance(resp, dict):
            registros = (
                resp.get("dados")
                or resp.get("registros")
                or resp.get("result")
                or resp.get("data")
                or []
            )
            if not isinstance(registros, list):
                if isinstance(registros, dict):
                    registros = list(registros.values())
                else:
                    registros = []
        else:
            registros = []

        # ── Filtro client-side por Situacao='A' ─────────────────────
        antes = len(registros)
        registros = [
            r for r in registros
            if isinstance(r, dict)
            and str(r.get("Situacao") or r.get("situacao") or "A").upper() == "A"
        ]
        depois = len(registros)
        
        if antes != depois:
            logger.debug(
                "Recebidos %d registros, %d ativos após filtro client-side",
                antes, depois,
            )
        else:
            logger.debug("Recebidos %d registros ativos", len(registros))

        all_records.extend(registros)

        logger.info("Total de matrículas ativas carregadas: %d", len(all_records))
        self._cache = all_records
        return self._cache


    # ------------------------------------------------------------------
    # Helpers de matching
    # ------------------------------------------------------------------

    @staticmethod
    def _best_match(target: str, candidates: list[str], cutoff: float = 0.82) -> str | None:
        """Retorna o candidato mais próximo ou None."""
        t = norm(target)
        # Busca exata primeiro
        if t in candidates:
            return t
        close = get_close_matches(t, candidates, n=1, cutoff=cutoff)
        return close[0] if close else None

    # ------------------------------------------------------------------
    # Interface pública
    # ------------------------------------------------------------------

    def resolve(self, nome_aluno: str, nome_curso: str) -> dict:
        """
        Busca o MatriculaID ativo para o par (nome_aluno, nome_curso).

        Retorna um dict com:
            matricula_id : int
            cpf          : str
            nome_aluno   : str  (como veio da API)
            nome_curso   : str  (como veio da API)
            raw          : dict (registro bruto da API)

        Lança ValueError com mensagem descritiva em caso de falha.
        """
        all_mats = self._load_all_active()

        if not all_mats:
            raise ValueError(
                "A API EAD não retornou nenhuma matrícula ativa. "
                "Verifique as credenciais no .env."
            )

        # ---- 1. Identificar quais campos a API usa para nome e curso ----
        # A API EAD pode variar os nomes dos campos. Inspecionamos o primeiro
        # registro para descobrir os campos disponíveis.
        sample = all_mats[0]
        logger.debug("Campos disponíveis no registro EAD: %s", list(sample.keys()))

        nome_field = _detect_field(sample, ["Nome", "nome", "NomeAluno", "nome_aluno", "Aluno", "aluno"])
        curso_field = _detect_field(sample, ["NomeCurso", "nome_curso", "Curso", "curso", "CursoNome", "DescCurso"])
        id_field = _detect_field(sample, ["MatriculaID", "matricula_id", "Matricula", "ID", "id"])
        cpf_field = _detect_field(sample, ["CPF", "cpf", "Cpf"])

        if not nome_field:
            raise ValueError(
                f"Não foi possível detectar o campo de nome do aluno nos dados da API. "
                f"Campos disponíveis: {list(sample.keys())}"
            )
        if not id_field:
            raise ValueError(
                f"Não foi possível detectar o campo MatriculaID nos dados da API. "
                f"Campos disponíveis: {list(sample.keys())}"
            )

        # ---- 2. Construir mapa nome_norm → lista de registros ----
        nome_map: dict[str, list[dict]] = {}
        for reg in all_mats:
            nome_api = str(reg.get(nome_field) or "")
            k = norm(nome_api)
            if k:
                nome_map.setdefault(k, []).append(reg)

        # ---- 3. Localizar o aluno por nome ----
        nome_key = self._best_match(nome_aluno, list(nome_map.keys()), cutoff=0.82)
        if not nome_key:
            poss = _top_similar(norm(nome_aluno), list(nome_map.keys()), n=5)
            raise ValueError(
                f"Aluno não encontrado na API EAD: '{nome_aluno}'. "
                f"Candidatos mais próximos: {poss}"
            )

        candidatos = nome_map[nome_key]

        # ---- 4. Dentre os candidatos, filtrar pelo curso ----
        if curso_field:
            curso_map: dict[str, dict] = {}
            for reg in candidatos:
                curso_api = str(reg.get(curso_field) or "")
                k = norm(curso_api)
                if k:
                    curso_map[k] = reg  # último vence se duplicado

            curso_key = self._best_match(nome_curso, list(curso_map.keys()), cutoff=0.78)
            if not curso_key:
                poss_cursos = [str(r.get(curso_field, "")) for r in candidatos]
                raise ValueError(
                    f"Curso '{nome_curso}' não encontrado para o aluno '{nome_aluno}'. "
                    f"Cursos ativos encontrados: {poss_cursos}"
                )
            reg_final = curso_map[curso_key]
        else:
            # API não retornou campo de curso — pegar primeiro candidato e avisar
            logger.warning(
                "Campo de curso não detectado na API. Usando primeiro registro para '%s'.",
                nome_aluno,
            )
            if len(candidatos) > 1:
                raise ValueError(
                    f"Aluno '{nome_aluno}' possui {len(candidatos)} matrículas ativas mas "
                    f"o campo de curso não foi detectado na resposta da API. "
                    f"Campos disponíveis: {list(candidatos[0].keys())}"
                )
            reg_final = candidatos[0]

        # ---- 5. Extrair MatriculaID ----
        matricula_id_raw = reg_final.get(id_field)
        if not matricula_id_raw:
            raise ValueError(
                f"MatriculaID vazio no registro encontrado: {reg_final}"
            )

        return {
            "matricula_id": int(matricula_id_raw),
            "cpf": str(reg_final.get(cpf_field, "")) if cpf_field else "",
            "nome_aluno": str(reg_final.get(nome_field, "")),
            "nome_curso": str(reg_final.get(curso_field, "")) if curso_field else "",
            "raw": reg_final,
        }

    def invalidate_cache(self):
        """Limpa o cache de matrículas (útil para reprocessar após inativações)."""
        self._cache = None


# ------------------------------------------------------------------
# Funções utilitárias
# ------------------------------------------------------------------

def _detect_field(record: dict, candidates: list[str]) -> str | None:
    """Retorna o primeiro campo candidato que existe no registro."""
    for c in candidates:
        if c in record:
            return c
    return None


def _top_similar(target: str, keys: list[str], n: int = 5) -> list[str]:
    """Retorna os n candidatos mais próximos (sem cutoff mínimo) para sugestões de erro."""
    from difflib import SequenceMatcher
    scored = sorted(
        keys,
        key=lambda k: SequenceMatcher(None, target, k).ratio(),
        reverse=True,
    )
    return scored[:n]
