# Whisper API

API de transcrição de áudio com Whisper large-v3, com integração WhatsApp via Evolution API para transcrição automática de áudios recebidos.

## 🚀 O que faz?

- **Transcrição de áudios via WhatsApp**: recebe áudios no seu número, transcreve com Whisper e envia a transcrição para um número destino — com o nome de quem mandou e de onde (grupo ou conversa privada).
- **API REST de transcrição**: endpoints para transcrever áudios diretamente via upload.
- **Correção com IA**: opcionalmente corrige o texto transcrito com Qwen3.
- **Envio por email**: transcrição em lote com envio dos resultados por Gmail.

## ⚡ Setup Rápido

```bash
# 1. Clone e instale as dependências
git clone <URL_DO_REPOSITORIO>
cd whisper-api
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. Rode o setup interativo (configura Evolution API + WhatsApp + .env)
python setup.py

# 3. Inicie o servidor
pm2 start ecosystem.config.js
```

O `setup.py` guia você por todo o processo: conexão com a Evolution API, criação de instância, QR Code no terminal, configuração do webhook e geração do `.env`.

**📖 Guia completo:** [docs/SETUP.md](docs/SETUP.md) — inclui como instalar a Evolution API do zero.

## 📡 Endpoints

### WhatsApp (Evolution API)

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/webhook/evolution` | POST | Recebe eventos da Evolution API (webhook) |
| `/webhook/evolution/status` | GET | Health check do webhook |

### Transcrição direta

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/` | GET | Health check da API |
| `/transcrever/` | POST | Transcrição simples de áudio |
| `/transcrever-e-corrigir/` | POST | Transcrição + correção com Qwen3 |
| `/transcrever-e-enviar/` | POST | Transcrição em lote + envio por email |

## 🔧 Variáveis de Ambiente

Copie o `.env.example` para `.env` ou rode `python setup.py`:

```bash
cp .env.example .env
```

| Variável | Descrição |
|----------|-----------|
| `EVOLUTION_API_URL` | URL da Evolution API (ex: `http://localhost:8080`) |
| `EVOLUTION_API_GLOBAL_KEY` | API Key global do servidor Evolution |
| `EVOLUTION_API_KEY` | API Key da instância (hash) |
| `EVOLUTION_INSTANCE` | Nome da instância |
| `NUMERO_DESTINO` | Número que recebe as transcrições (DDI+DDD+número) |
| `WEBHOOK_URL` | URL pública deste servidor |
| `WEBHOOK_TOKEN` | Token secreto para autenticar o webhook |
| `APP_SENHA_GOOGLE` | Senha de app do Gmail (para envio de email) |

## 🏃 Rodando

### Com PM2 (produção)

```bash
pm2 start ecosystem.config.js
pm2 logs whisper-api
```

### Com uvicorn (desenvolvimento)

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 🆕 Transcrição em Lote com Envio de Email

### Endpoint: `/transcrever-e-enviar/`

Permite enviar **múltiplos áudios** simultaneamente, transcrever todos na ordem enviada e receber os resultados via **email** (Gmail SMTP).

#### Características:

✅ Transcrição de múltiplos áudios em uma única requisição  
✅ Processamento ordenado (na ordem enviada)  
✅ Correção opcional com IA (Qwen3)  
✅ Envio automático via email Gmail  
✅ Relatório HTML formatado  
✅ Tracking de tempo de processamento  

#### Parâmetros:

| Parâmetro | Tipo | Obrigatório | Descrição |
|-----------|------|-------------|-----------|
| `arquivos` | List[File] | ✅ Sim | Lista de arquivos de áudio |
| `destinatario` | String | ✅ Sim | Email para enviar os resultados |
| `corrigir` | Boolean | ❌ Não | Aplicar correção com Qwen3 (padrão: false) |

#### Exemplos de Uso:

**Com curl (sem correção):**
```bash
curl -X POST http://localhost:8000/transcrever-e-enviar/ \
  -F "arquivos=@audio1.mp3" \
  -F "arquivos=@audio2.mp3" \
  -F "arquivos=@audio3.wav" \
  -F "destinatario=seu@email.com"
```

**Com curl (com correção):**
```bash
curl -X POST http://localhost:8000/transcrever-e-enviar/ \
  -F "arquivos=@audio1.mp3" \
  -F "arquivos=@audio2.mp3" \
  -F "destinatario=seu@email.com" \
  -F "corrigir=true"
```

**Com Python requests:**
```python
import requests

files = [
    ('arquivos', open('audio1.mp3', 'rb')),
    ('arquivos', open('audio2.mp3', 'rb')),
]
data = {
    'destinatario': 'seu@email.com',
    'corrigir': False
}

response = requests.post(
    'http://localhost:8000/transcrever-e-enviar/',
    files=files,
    data=data
)

print(response.json())
```

#### Resposta (Exemplo):

```json
{
  "status": "sucesso",
  "total_arquivos": 2,
  "email_enviado": true,
  "mensagem_email": "Email enviado com sucesso",
  "resultados": [
    {
      "número": 1,
      "arquivo": "audio1.mp3",
      "transcricao": "Olá, esta é a primeira transcrição",
      "corrigida": false,
      "duracao_segundos": 15.42
    },
    {
      "número": 2,
      "arquivo": "audio2.mp3",
      "transcricao": "Segunda transcrição finalizada",
      "corrigida": false,
      "duracao_segundos": 8.21
    }
  ],
  "horario_inicio": "14:30:45",
  "horario_fim": "14:31:12",
  "duracao_total_segundos": 27.63
}
```

#### Configuração do Email:

Veja a seção de variáveis de ambiente acima (`APP_SENHA_GOOGLE`).

Para gerar a Senha do App no Gmail:
1. Ative a autenticação de 2 fatores na sua conta Google
2. Acesse [Google App Passwords](https://myaccount.google.com/apppasswords)
3. Selecione "Mail" e copie a senha gerada para o `.env`

## 📄 Licença

MIT License