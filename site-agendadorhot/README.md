# ✈️ Telegram Story Scheduler

Aplicação web completa para agendar e publicar stories no Telegram automaticamente via **MTProto** (utilizando a biblioteca **Telethon** e a chamada oficial `stories.sendStory`), com backend em **FastAPI**, persistência em **SQLite (SQLAlchemy)**, tarefas agendadas com **APScheduler** no fuso horário `America/Fortaleza` e interface web moderna em **Modo Escuro**.

---

## 🌟 Funcionalidades

1. **Conexão Segura da Conta MTProto**
   - Conexão direta de conta de usuário do Telegram (indispensável, pois a Bot API não publica stories).
   - Fluxo completo de login: envio de código (Telegram/SMS) e suporte a **Verificação em Duas Etapas (2FA)**.
   - **Criptografia simétrica com Fernet**: a string de sessão do Telethon é salva 100% criptografada no banco SQLite. Nenhuma credencial fica em texto puro.
   - Indicador visual em tempo real de conta conectada, nome, telefone e selo de **Telegram Premium**.
   - Botão para desconectar e revogar a sessão com segurança.

2. **Agendamento e Publicação Automática de Stories**
   - **Upload de Mídia**: Suporte a fotos (`JPG`, `PNG`, `WEBP`) e vídeos (`MP4`, `MOV`) com validação de tamanho (até 50MB) e pré-visualização instantânea na interface.
   - **Legenda Completa**: Campo de texto com contador de caracteres (até 2048 caracteres).
   - **Fuso Horário Oficial**: Todo o agendamento opera no fuso horário **America/Fortaleza (UTC-3)** com bloqueio de datas/horários passados.
   - **Duração do Story**: Opções de `6h` (21600s), `12h` (43200s), `24h` (86400s) e **`48h` (172800s)** para contas com Telegram Premium.
   - **Fixar no Perfil**: Switch dedicado "Fixar no perfil". Quando ativado, envia o parâmetro `pinned=True` na requisição `stories.sendStory`, mantendo o story em destaque no perfil mesmo após a expiração.
   - **Privacidade Personalizada**: Escolha entre Todos (Público), Meus Contatos ou Amigos Próximos.
   - **Gerenciamento**: Edição de legenda, alteração de horário, cancelamento e exclusão de stories agendados.

3. **Painel de Controle e Auditoria em Tempo Real**
   - Lista organizada de stories filtrável por: *Todos*, *Agendados*, *Publicados* e *Com Erro*.
   - Exibição de cards com miniatura da mídia, status, data e hora no fuso de Fortaleza, tag de duração e tag de fixado no perfil.
   - **Histórico e Logs Detalhados**: Modal com o resultado de cada tentativa de publicação e mensagens de erro traduzidas.
   - **Retentativa Automática**: Caso ocorra falha (ex: oscilação de rede ou erro temporário do Telegram), o sistema reexecuta a publicação automaticamente até 3 vezes (com intervalo de 60 segundos).
   - **Tolerância a Falhas e Reinicialização**: O APScheduler recarrega todos os agendamentos pendentes do SQLite automaticamente caso o servidor seja reiniciado.

---

## 📁 Estrutura do Projeto

```text
telegram-story-scheduler/
├── .env                      # Variáveis de ambiente sensíveis (ignorado pelo Git)
├── .env.example              # Exemplo com variáveis vazias para configuração
├── .gitignore                # Proteção de credenciais, uploads e sessões
├── requirements.txt          # Dependências do projeto Python
├── pytest.ini                # Configurações do executor de testes pytest
├── README.md                 # Documentação detalhada e guia de uso
├── test_schedule_2min.py     # Script para testar agendamento de 2 minutos com pinned=True
│
├── app/
│   ├── __init__.py
│   ├── config.py             # Leitura do .env, timezone (America/Fortaleza) e constantes
│   ├── database.py           # Conexão SQLite e gerador de sessões SQLAlchemy
│   ├── models.py             # Modelos TelegramAccount, ScheduledStory e StoryLog
│   ├── schemas.py            # Validações e esquemas Pydantic V2
│   ├── security.py           # Criptografia e descriptografia Fernet para sessões
│   ├── telegram_client.py    # Cliente MTProto Telethon, login, 2FA e stories.sendStory
│   ├── scheduler.py          # APScheduler, execução periódica, retentativas e recuperação
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py           # Endpoints de login, código, 2FA, status e logout
│   │   ├── stories.py        # Endpoints de criação, listagem, edição, cancelamento e remoção
│   │   └── logs.py           # Endpoints de auditoria e logs globais
│   │
│   └── static/               # Frontend SPA (Modo Escuro)
│       ├── index.html        # Interface completa com formulário e painel de stories
│       ├── css/
│       │   └── style.css     # Estilos modernos, responsivos e tema escuro elegante
│       └── js/
│           └── app.js        # Lógica de upload, relógio Fortaleza, polling e modais
│
├── data/                     # Diretório de armazenamento do banco SQLite (scheduler.db)
├── uploads/                  # Diretório de armazenamento das mídias dos stories
└── tests/                    # Suíte completa de testes automatizados
    ├── __init__.py
    ├── conftest.py           # Fixtures de inicialização do banco de dados
    ├── test_crypto.py        # Testes de criptografia de sessão Fernet
    ├── test_api.py           # Testes de endpoints FastAPI e validação de regras de negócio
    ├── test_scheduler.py     # Testes de retentativa, execução e recarga do agendador
    └── test_2min_scheduled_flow.py # Teste do fluxo completo de 2 minutos com pinned=True
```

---

## 🛠️ Requisitos e Tecnologias

- **Python 3.10+** (testado e compatível com Python 3.15)
- **FastAPI** + **Uvicorn**
- **Telethon** (MTProto Telegram API)
- **SQLAlchemy** + **SQLite**
- **APScheduler** (AsyncIOScheduler)
- **Cryptography** (Fernet)
- **Pillow** (Processamento de imagens)

---

## 🚀 Instalação Passo a Passo

### 1. Clonar ou Acessar a Pasta do Projeto

```bash
cd C:\Users\Administrator\.gemini\antigravity\scratch\telegram-story-scheduler
```

### 2. Criar e Ativar um Ambiente Virtual (Recomendado)

```bash
python -m venv venv

# No Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# No Linux / macOS:
source venv/bin/activate
```

### 3. Instalar as Dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar as Variáveis de Ambiente (.env)

Copie o arquivo `.env.example` para `.env` (ou utilize o arquivo já gerado com as suas credenciais):

```bash
cp .env.example .env
```

O `.env` guarda a chave de criptografia e, opcionalmente, um `TELEGRAM_API_ID`/`TELEGRAM_API_HASH` **padrão**. Cada conta também pode ter o próprio api_id/api_hash, informados na tela de conexão (veja abaixo).

```env
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
ENCRYPTION_KEY=   # gere com: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> **Atenção:** O arquivo `.env` está explicitamente incluído no `.gitignore` para garantir que nenhuma chave sensível seja versionada.

---

## 🖥️ Como Executar a Aplicação

Inicie o servidor backend executando:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Acesse no navegador:
👉 **http://localhost:8000**

A documentação interativa Swagger da API estará disponível em:
👉 **http://localhost:8000/docs**

---

## 📱 Fluxo de Uso Completo

### 1. Conectar uma ou mais contas do Telegram
1. No canto superior direito da página, clique em **+ Conectar Conta**.
2. Digite o telefone internacional (ex: `+5585999999999`) e o **api_id / api_hash** daquela conta (my.telegram.org). Deixe vazios para usar o padrão do `.env`. Repita para cada conta; no agendamento você escolhe qual conta publica.
3. Digite o código de verificação recebido no Telegram ou via SMS.
4. Se sua conta tiver Verificação em Duas Etapas (2FA), digite a senha da nuvem.
5. O status mudará imediatamente para **Conectado**, exibindo seu nome e o selo ⭐ **Premium**.

### 2. Agendar um Story
1. Arraste ou selecione a foto (`JPG`, `PNG`, `WEBP`) ou vídeo (`MP4`).
2. Digite a legenda desejada.
3. Escolha a data e a hora de publicação (o relógio exibe o horário de **America/Fortaleza** em tempo real).
4. Selecione a duração: **6h**, **12h**, **24h** ou **48h (Premium)**.
5. Ative o switch **📌 Fixar no Perfil** (`pinned=True`) para mantê-lo salvo no perfil.
6. Escolha a visibilidade (Público, Contatos ou Amigos Próximos).
7. Clique em **Agendar Publicação Automática**.

O story será publicado no minuto exato agendado pelo **APScheduler**, sem nenhuma intervenção manual.

---

## 🧪 Execução de Testes Automatizados

Para rodar toda a suíte de testes (13 testes automatizados cobrindo API, scheduler, retentativas e criptografia):

```bash
python -m pytest -v
```

### Teste do Agendamento para 2 Minutos com Fixar no Perfil (`test_schedule_2min.py`)

Com o servidor rodando em segundo plano (`http://localhost:8000`), execute:

```bash
python test_schedule_2min.py            # primeira conta conectada
python test_schedule_2min.py --account 2  # conta específica
```

O script:
1. Conecta ao servidor e valida a hora atual no fuso de Fortaleza.
2. Gera automaticamente uma arte de story em proporção 9:16 (1080x1920).
3. Agenda a publicação para exatamente **2 minutos** à frente com `pinned=True` e duração de **48h**.
4. Monitora a publicação a cada 5 segundos exibindo os logs em tempo real até a confirmação de sucesso pelo MTProto.

---

## 🛡️ Segurança e Boas Práticas

- **Criptografia Fernet**: As credenciais e sessões da conta nunca são salvas em texto puro.
- **Tratamento de FloodWait**: Aguarda respeitosamente os limites da API oficial do Telegram caso receba erro `FloodWaitError`.
- **Validação Rigorosa**: Inputs sanitizados, arquivos validados por extensão e tamanho máximo, e horários passados rejeitados com código HTTP 400.
- **Zero Vazamento**: Nenhuma credencial sensível (`API_ID`, `API_HASH` ou `session`) é retornada em endpoints públicos ou exibida no frontend.
