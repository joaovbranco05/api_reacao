"""
Cliente para a API EAD WebService (IESDE / PortalAVA).

Autenticação: HTTP Digest (MD5) + Header EAD-API-KEY
Formato de resposta: JSON (/format/json suffix ou form-param format=json)
Corpo das requisições: multipart/form-data
"""
from __future__ import annotations

import os
import logging
import requests
from requests.auth import HTTPDigestAuth

logger = logging.getLogger("core.ead_client")


class EADClient:
    """
    Encapsula as chamadas à API EAD WebService.

    Parâmetros lidos do .env (ou passados no construtor):
        EAD_BASE_URL   – URL base, ex: https://ead.portalava.com.br
        EAD_USERNAME   – WS_USERNAME (hash SHA-1)
        EAD_PASSWORD   – WS_PASSWORD (hash SHA-1)
        EAD_API_KEY    – EAD-API-KEY
    """

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        api_key: str | None = None,
    ):
        self.base_url = (base_url or os.getenv("EAD_BASE_URL", "")).rstrip("/")
        self.username = username or os.getenv("EAD_USERNAME", "")
        self.password = password or os.getenv("EAD_PASSWORD", "")
        self.api_key = api_key or os.getenv("EAD_API_KEY", "")

        if not self.base_url:
            raise ValueError(
                "EAD_BASE_URL não configurado. "
                "Adicione ao .env: EAD_BASE_URL=https://ead.portalava.com.br"
            )
        if not self.username or not self.password:
            raise ValueError(
                "EAD_USERNAME e EAD_PASSWORD não configurados no .env."
            )
        if not self.api_key:
            raise ValueError("EAD_API_KEY não configurado no .env.")

    # ------------------------------------------------------------------
    # Helpers internos
    # ------------------------------------------------------------------

    def _auth(self) -> HTTPDigestAuth:
        return HTTPDigestAuth(self.username, self.password)

    def _headers(self) -> dict[str, str]:
        return {"EAD-API-KEY": self.api_key}

    def _post_json(self, path: str, data: dict) -> dict:
        """
        POST com form-data para um endpoint /format/json.
        Retorna o dict JSON da resposta.
        Lança requests.HTTPError se status HTTP != 2xx.
        """
        url = f"{self.base_url}{path}"
        logger.debug("POST %s | data=%s", url, data)
        resp = requests.post(
            url,
            auth=self._auth(),
            headers=self._headers(),
            data=data,          # multipart/form-data
            timeout=30,
        )
        logger.debug("Response %s: %.500s", resp.status_code, resp.text)
        resp.raise_for_status()
        try:
            return resp.json()
        except Exception:
            # Fallback para respostas XML (ex: o endpoint /situacao retorna XML)
            text = resp.text.strip()
            if text.startswith("<"):
                import xml.etree.ElementTree as ET
                try:
                    root = ET.fromstring(text)
                    return {child.tag: child.text for child in root}
                except Exception:
                    pass
            return {"status": resp.status_code, "raw": text}

    # ------------------------------------------------------------------
    # Endpoints de consulta
    # ------------------------------------------------------------------

    def get_matriculas(
        self,
        situacao: str = "A",
        pagina: int = 1,
        registros_pagina: int = 200,
        nome: str | None = None,
        cpf: str | None = None,
    ) -> dict:
        """
        GET /web_service/getMatriculas/format/json
        Filtra por Situacao=A (ativo) para localizar matrículas ativas.
        Suporta paginação (registros_pagina / pagina).
        """
        payload: dict = {
            "Situacao": situacao,
            "pagina": pagina,
            "registros_pagina": registros_pagina,
        }
        if nome:
            payload["Nome"] = nome
        if cpf:
            payload["CPF"] = cpf
        return self._post_json("/web_service/getMatriculas/format/json", payload)

    def get_cursos(self) -> dict:
        """
        GET /web_service/getCursos/format/json
        Retorna todos os cursos disponíveis.
        """
        return self._post_json("/web_service/getCursos/format/json", {})

    # ------------------------------------------------------------------
    # Endpoint de alteração de situação
    # ------------------------------------------------------------------

    def set_situacao(self, matricula_id: int | str, situacao: str = "I") -> dict:
        """
        POST /web_service/situacao
        Altera a situação de uma matrícula.

        situacao: 'A' (ativo) | 'I' (inativo)
        """
        payload = {
            "MatriculaID": str(matricula_id),
            "Situacao": situacao,
        }
        return self._post_json("/web_service/situacao", payload)
