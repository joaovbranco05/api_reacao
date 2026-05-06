# API Reação - Sistema de Notas iScholar

Este projeto é uma ferramenta de automação e integração para o sistema iScholar, permitindo o lançamento de notas de forma simplificada e em lote via interface web.

## Como a Aplicação Funciona

A aplicação é composta por um backend em **FastAPI** (Python) e um frontend web moderno. Ela serve como um intermediário entre o usuário e a API do iScholar para facilitar tarefas repetitivas.

### Principais Funcionalidades:
- **Autenticação**: Gerenciada através de configurações no arquivo `.env` e validação com o iScholar.
- **Lançamento em Lote**: Processamento de planilhas Excel para envio massivo de notas ao sistema.
- **Interface Web**: Interface amigável acessível via navegador local (localhost).
- **Automação de Inicialização**: Ao abrir o executável ou o script, o navegador padrão é aberto automaticamente na página do sistema.

---

## Guia de Instalação e Criação do Executável (.exe)

Siga os passos abaixo após realizar o `git clone` do repositório.

### 1. Pré-requisitos
- **Python 3.10 ou superior** instalado.
- Certifique-se de marcar a opção **"Add Python to PATH"** durante a instalação do Python no Windows.

### 2. Configuração do Ambiente

Abra o terminal na pasta do projeto e execute os seguintes comandos:

#### Criar Ambiente Virtual (VENV):
```powershell
python -m venv .venv
```

#### Ativar Ambiente Virtual:
- **No PowerShell**:
  ```powershell
  .venv\Scripts\activate
  ```

#### Instalar Dependências:
```powershell
pip install -r requirements.txt
```

### 3. Configurar Variáveis de Ambiente
Crie um arquivo chamado `.env` na raiz do projeto (mesma pasta do `main.py`) com o seguinte conteúdo de exemplo:

```env
ISCHOLAR_CODIGO_ESCOLA=SUA_ESCOLA
ISCHOLAR_TOKEN_ACESSO=SEU_TOKEN
PROFESSOR_LOGINS=usuario1:senha1,usuario2:senha2
```

### 4. Criar o Executável (.exe)

Para gerar o arquivo final `.exe`, utilize o **PyInstaller** com o arquivo `.spec` já configurado:

```powershell
pyinstaller app.spec
```

#### O que este comando faz?
- **Bundle**: Empacota o código Python e todas as bibliotecas em um único arquivo.
- **Assets**: Inclui a pasta `static` (HTML/CSS/JS) dentro do executável.
- **Configuração**: Utiliza as definições do `app.spec` para evitar janelas de erro e otimizar o tamanho.

### 5. Onde encontrar o Executável?
Após o término da compilação, o executável estará disponível em:
`dist/API_Reacao.exe`

> **Nota Importante**: O executável **precisa** do arquivo `.env` na mesma pasta para funcionar corretamente (para ler as credenciais da escola).

---

## Como Executar em Desenvolvimento (Sem compilar)

Se você deseja apenas rodar a aplicação para testar:

1. Simplesmente execute o arquivo `iniciar.bat` (dando dois cliques nele).
2. O script cuidará de criar o ambiente virtual, instalar as dependências e iniciar o servidor.
3. Acesse `http://localhost:8000` no seu navegador.
