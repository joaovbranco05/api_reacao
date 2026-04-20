import reflex as rx
import os
from dotenv import load_dotenv
from .ischolar_client import IScholarClient, IScholarConfig
from .validators import parse_nota
from .auth import AuthState
from .batch_excel_nomes import parse_excel_bytes_named
from .ischolar_resolver import IScholarResolver, norm



load_dotenv()

def get_client() -> IScholarClient:
    codigo = os.getenv("ISCHOLAR_CODIGO_ESCOLA")
    token = os.getenv("ISCHOLAR_TOKEN_ACESSO")

    if not codigo or not token:
        raise ValueError("Configure ISCHOLAR_CODIGO_ESCOLA e ISCHOLAR_TOKEN_ACESSO no .env")

    cfg = IScholarConfig(codigo_escola=codigo, token_acesso=token)
    return IScholarClient(cfg)


class NotaState(rx.State):
    id_matricula: str = ""
    id_disciplina: str = ""
    id_avaliacao: str = ""
    valor: str = ""
    status: str = ""

    def set_id_matricula(self, v: str):
        self.id_matricula = v

    def set_id_disciplina(self, v: str):
        self.id_disciplina = v

    def set_id_avaliacao(self, v: str):
        self.id_avaliacao = v

    def set_valor(self, v: str):
        self.valor = v

    async def enviar_nota(self):
        
        self.status = "⏳ Preparando envio..."
        try:
            auth = await self.get_state(AuthState)
            if not getattr(auth, "logged_in", False):
                self.status = "Faça login para lançar notas."
                return

            
            self.status = f"⏳ Validando nota (raw={self.valor!r})..."

            valor_float = parse_nota(self.valor) 

            
            try:
                id_matricula = int(str(self.id_matricula).strip())
                id_disciplina = int(str(self.id_disciplina).strip())
                id_avaliacao = int(str(self.id_avaliacao).strip())
            except Exception:
                self.status = "❌ IDs inválidos: verifique se matrícula/disciplina/avaliação são números."
                return

            self.status = "⏳ Enviando para o iScholar..."

            client = get_client()
            resp = client.lancar_nota(
                id_matricula=id_matricula,
                id_disciplina=id_disciplina,
                id_avaliacao=id_avaliacao,
                id_professor=int(auth.professor_id),
                valor=valor_float,
            )

            
            if isinstance(resp, dict) and resp.get("status") == "sucesso":
                self.status = "✅ Nota lançada com sucesso!"
            else:
                self.status = f"API recusou: {resp}"

        except Exception as e:
            self.status = f"ERRO ({type(e).__name__}): {e}"


class BatchState(rx.State):
    status: str = ""
    resultados: list[dict] = []

    async def processar_excel(self, files: list[rx.UploadFile]):
        self.status = "⏳ Lendo planilha..."
        self.resultados = []

        try:
            auth = await self.get_state(AuthState)
            if not getattr(auth, "logged_in", False):
                self.status = "Faça login para lançar notas."
                return

            if not files:
                self.status = "Nenhum arquivo enviado."
                return

            f = files[0]
            if not f.filename.lower().endswith(".xlsx"):
                self.status = "Envie um arquivo .xlsx"
                return

            xlsx_bytes = await f.read()
            rows = parse_excel_bytes_named(xlsx_bytes)

            codigo = os.getenv("ISCHOLAR_CODIGO_ESCOLA")
            token = os.getenv("ISCHOLAR_TOKEN_ACESSO")

            if not codigo or not token:
                self.status = "Falta ISCHOLAR_CODIGO_ESCOLA ou ISCHOLAR_TOKEN_ACESSO no .env"
                return

            resolver = IScholarResolver(codigo_escola=codigo, token=token, unidade="")  
            client = get_client()

            total = len(rows)
            ok = 0
            self.status = f"📄 {total} linhas lidas. Resolvendo IDs e enviando..."

            for i, r in enumerate(rows, start=1):
                try:
                    
                    valor_float = parse_nota(r.nota)

                    
                    id_matricula, id_turma = resolver.resolve_matricula_e_turma(r.aluno_nome, r.turma_nome)

                    
                    disc = resolver.resolve_disciplina(id_turma, r.materia_nome)
                    id_disciplina = int(disc["id_disciplina"])

                    
                    prof_obj = disc.get("professores") or {}
                    prof_nome_vinc = (prof_obj.get("nome_professor") or "").strip()
                    prof_id_vinc = prof_obj.get("id_professor")

                    
                    def _norm_local(s: str) -> str:
                        from unidecode import unidecode
                        return unidecode((s or "").strip().lower())

                    if prof_id_vinc and prof_nome_vinc and (
                        _norm_local(r.professor_nome) in _norm_local(prof_nome_vinc)
                        or _norm_local(prof_nome_vinc) in _norm_local(r.professor_nome)
                    ):
                        id_professor = int(prof_id_vinc)
                    else:
                        id_professor = resolver.resolve_professor_id_por_matricula(id_matricula, r.professor_nome)

                    
                    id_avaliacao = resolver.resolve_avaliacao_id(id_turma, r.avaliacao_nome)

                   
                    resp = client.lancar_nota(
                        id_matricula=id_matricula,
                        id_disciplina=id_disciplina,
                        id_avaliacao=id_avaliacao,
                        id_professor=id_professor,
                        valor=valor_float,
                    )

                    if isinstance(resp, dict) and resp.get("status") == "sucesso":
                        ok += 1
                        self.resultados.append({"linha": i, "status": "sucesso", "mensagem": resp.get("mensagem", "")})
                    else:
                        self.resultados.append({"linha": i, "status": "erro", "mensagem": f"API recusou: {resp}"})

                except Exception as e:
                    self.resultados.append({"linha": i, "status": "erro", "mensagem": f"{type(e).__name__}: {e}"})

                self.status = f"🚀 Enviando... {i}/{total} | OK: {ok} | ERRO: {i-ok}"

            self.status = f"✅ Finalizado! OK: {ok} | ERRO: {total-ok}"

        except Exception as e:
            self.status = f"❌ Falha no lote ({type(e).__name__}): {e}"



def redirecting_to_login():
    return rx.center(
        rx.text("Redirecionando para login..."),
        height="100vh",
        on_mount=rx.redirect("/login"),
    )


def index():
    return rx.cond(
        AuthState.is_logged_in,
        rx.center(
            rx.vstack(
                rx.hstack(
                    rx.hstack(rx.text("Professor ID:"), rx.text(AuthState.professor_id)),
                    rx.button("Sair", on_click=AuthState.logout),
                    justify="between",
                    width="420px",
                ),
                rx.heading("Lançar nota individual"),
                rx.input(
                    placeholder="ID Matrícula",
                    value=NotaState.id_matricula,
                    on_change=NotaState.set_id_matricula,
                ),
                rx.input(
                    placeholder="ID Disciplina",
                    value=NotaState.id_disciplina,
                    on_change=NotaState.set_id_disciplina,
                ),
                rx.input(
                    placeholder="ID Avaliação",
                    value=NotaState.id_avaliacao,
                    on_change=NotaState.set_id_avaliacao,
                ),
                rx.input(
                    placeholder="Nota (0 a 10)",
                    value=NotaState.valor,
                    on_change=NotaState.set_valor,
                ),
                rx.button("Enviar Nota", on_click=NotaState.enviar_nota),
                rx.text(NotaState.status),
                rx.link("👉 Lançar notas em lote (Excel)", href="/lote"),
                spacing="3",
                width="420px",
            )
        ),
        redirecting_to_login(),
    )


def batch_page():
    return rx.cond(
        AuthState.is_logged_in,
        rx.center(
            rx.vstack(
                rx.vstack(
                    rx.hstack(rx.text("Professor ID:"), rx.text(AuthState.professor_id)),
                    rx.button("Sair", on_click=AuthState.logout),
                    justify="between",
                    width="900px",
                ),
                rx.heading("Lançar notas em lote (Excel)"),
                rx.upload(
                    rx.vstack(
                        rx.text("Arraste o arquivo Excel aqui ou clique para selecionar"),
                        rx.text("Formato: .xlsx com colunas: nome do aluno, nome da turma, nome do professor, nome da materia, nome da avaliacao, nota")
,
                    ),
                    accept={"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": [".xlsx"]},
                    max_files=1,
                    on_drop=BatchState.processar_excel,
                ),
                rx.text(BatchState.status),
                rx.cond(
                    BatchState.resultados.length() > 0,
                    rx.table.root(
                        rx.table.header(
                            rx.table.row(
                                rx.table.column_header_cell("Linha"),
                                rx.table.column_header_cell("Status"),
                                rx.table.column_header_cell("Mensagem"),
                            )
                        ),
                        rx.table.body(
                            rx.foreach(
                                BatchState.resultados,
                                lambda r: rx.table.row(
                                    rx.table.cell(r["linha"]),
                                    rx.table.cell(r["status"]),
                                    rx.table.cell(r["mensagem"]),
                                ),
                            )
                        ),
                        width="900px",
                    ),
                ),
                rx.link("⬅ Voltar para lançamento individual", href="/"),
                spacing="4",
                width="950px",
            )
        ),
        redirecting_to_login(),
    )


def login_page():
    return rx.center(
        rx.vstack(
            rx.heading("Login do Professor"),
            rx.input(
                placeholder="ID do professor (ex: 65)",
                value=AuthState.professor_id_input,
                on_change=AuthState.set_professor_id_input,
            ),
            rx.input(
                placeholder="Senha",
                type_="password",
                value=AuthState.senha_input,
                on_change=AuthState.set_senha_input,
            ),
            rx.button("Entrar", on_click=AuthState.login),
            rx.cond(AuthState.auth_error != "", rx.text(AuthState.auth_error)),
            width="360px",
            spacing="3",
        ),
        height="100vh",
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(batch_page, route="/lote")
app.add_page(login_page, route="/login")
