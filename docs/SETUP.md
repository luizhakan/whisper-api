# 📖 Guia Completo de Setup — Whisper API + WhatsApp

Este guia explica como instalar e configurar tudo do zero: desde a Evolution API até o bot de transcrição de áudios funcionando.

---

## 📋 Índice

1. [Pré-requisitos](#pré-requisitos)
2. [Instalar a Evolution API](#instalar-a-evolution-api)
3. [Setup Rápido (script interativo)](#setup-rápido-script-interativo)
4. [Setup Manual](#setup-manual)
5. [Rodar com PM2](#rodar-com-pm2)
6. [Como funciona](#como-funciona)
7. [Troubleshooting](#troubleshooting)

---

## Pré-requisitos

| Requisito | Versão mínima | Notas |
|-----------|---------------|-------|
| Python | 3.10+ | Com pip |
| Node.js | 18+ | Para PM2 |
| PM2 | qualquer | `npm install -g pm2` |
| Docker + Docker Compose | 20+ | Para a Evolution API |
| WhatsApp | - | Conta ativa para escanear QR code |

---

## Instalar a Evolution API

A Evolution API é o serviço que faz a ponte entre o WhatsApp e a sua aplicação. Ela precisa estar rodando antes de configurar o bot.

### 1. Criar o `docker-compose.yml`

Crie uma pasta para a Evolution API e dentro dela o arquivo:

```yaml
services:
  evolution-api:
    image: atendai/evolution-api:v2.2.3
    container_name: evolution-api
    restart: always
    ports:
      - "8080:8080"
    environment:
      # Autenticação
      - AUTHENTICATION_TYPE=apikey
      - AUTHENTICATION_API_KEY=sua_chave_global_super_secreta_aqui
      - AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES=true

      # Servidor
      - SERVER_PORT=8080
      - SERVER_URL=http://localhost:8080

      # Banco de dados (PostgreSQL)
      - DATABASE_PROVIDER=postgresql
      - DATABASE_CONNECTION_URI=postgresql://evolution:evolution@evolution-db:5432/evolution

      # Logs
      - LOG_LEVEL=WARN
      - LOG_COLOR=true
    volumes:
      - evolution_instances:/evolution/instances
    depends_on:
      evolution-db:
        condition: service_healthy

  evolution-db:
    image: postgres:16-alpine
    container_name: evolution-db
    restart: always
    environment:
      - POSTGRES_USER=evolution
      - POSTGRES_PASSWORD=evolution
      - POSTGRES_DB=evolution
    volumes:
      - evolution_pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U evolution"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  evolution_instances:
  evolution_pgdata:
```

> **IMPORTANTE:** Troque `sua_chave_global_super_secreta_aqui` por uma chave segura. Essa é a `AUTHENTICATION_API_KEY` que você usará no setup.

### 2. Subir o container

```bash
docker compose up -d
```

### 3. Verificar se está rodando

```bash
curl http://localhost:8080/instance/fetchInstances \
  -H "apikey: sua_chave_global_super_secreta_aqui"
```

Deve retornar `[]` (array vazio, nenhuma instância criada ainda).

---

## Setup Rápido (script interativo)

O jeito mais fácil de configurar tudo. O script vai:

- ✅ Testar a conexão com a Evolution API
- ✅ Criar uma instância WhatsApp
- ✅ Exibir o QR Code no terminal para você escanear
- ✅ Configurar o webhook automaticamente (events + base64)
- ✅ Gerar o arquivo `.env` com todos os dados

### Rodar o setup:

```bash
# 1. Instale as dependências (se ainda não fez)
pip install -r requirements.txt

# 2. Rode o setup interativo
python setup.py
```

O script vai guiar você passo a passo. Basta ir respondendo as perguntas.

### O que o setup configura automaticamente:

| Configuração | O que faz |
|---|---|
| Instância | Cria no Evolution API com integração `WHATSAPP-BAILEYS` |
| Webhook | Aponta para `{sua_url}/webhook/evolution` com `base64: true` |
| Eventos | Apenas `MESSAGES_UPSERT` (mensagens recebidas) |
| Auth | Gera token aleatório para proteger o webhook |
| `.env` | Salva todas as variáveis necessárias |

---

## Setup Manual

Se preferir configurar tudo na mão:

### 1. Copiar o `.env.example`

```bash
cp .env.example .env
```

### 2. Criar instância na Evolution API

```bash
curl -X POST http://localhost:8080/instance/create \
  -H "apikey: SUA_GLOBAL_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "instanceName": "whisper-bot",
    "qrcode": true,
    "integration": "WHATSAPP-BAILEYS"
  }'
```

Copie o campo `hash` da resposta — essa é a API Key da instância (`EVOLUTION_API_KEY`).

### 3. Conectar o WhatsApp

```bash
curl http://localhost:8080/instance/connect/whisper-bot \
  -H "apikey: SUA_INSTANCE_KEY"
```

A resposta contém um QR Code em base64. Decodifique e escaneie com o WhatsApp.

### 4. Verificar conexão

```bash
curl http://localhost:8080/instance/connectionState/whisper-bot \
  -H "apikey: SUA_INSTANCE_KEY"
```

Deve retornar `"state": "open"`.

### 5. Configurar o webhook

```bash
curl -X POST http://localhost:8080/webhook/set/whisper-bot \
  -H "apikey: SUA_INSTANCE_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "webhook": {
      "enabled": true,
      "url": "http://SEU_SERVIDOR:8000/webhook/evolution",
      "headers": {
        "Authorization": "Bearer SEU_TOKEN_SECRETO"
      },
      "byEvents": false,
      "base64": true,
      "events": ["MESSAGES_UPSERT"]
    }
  }'
```

### 6. Preencher o `.env`

Edite o arquivo `.env` com os valores que você obteve:

```env
EVOLUTION_API_URL=http://localhost:8080
EVOLUTION_API_GLOBAL_KEY=sua_global_key
EVOLUTION_API_KEY=hash_retornado_na_criacao
EVOLUTION_INSTANCE=whisper-bot
NUMERO_DESTINO=5511999999999
WEBHOOK_URL=http://seu-servidor:8000
WEBHOOK_TOKEN=seu_token_secreto
```

---

## Rodar com PM2

### Instalar PM2 (se necessário)

```bash
npm install -g pm2
```

### Iniciar o servidor

```bash
pm2 start ecosystem.config.js
```

### Comandos úteis

```bash
# Ver logs em tempo real
pm2 logs whisper-api

# Status
pm2 status

# Reiniciar
pm2 restart whisper-api

# Parar
pm2 stop whisper-api

# Iniciar automaticamente no boot
pm2 startup
pm2 save
```

### Rodar sem PM2 (desenvolvimento)

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

---

## Como funciona

```
┌─────────────┐      ┌──────────────────┐      ┌──────────────────┐
│             │      │                  │      │                  │
│  WhatsApp   │─────▶│  Evolution API   │─────▶│  Whisper API     │
│  (áudio)    │      │  (webhook)       │      │  (transcrição)   │
│             │      │                  │      │                  │
└─────────────┘      └──────────────────┘      └────────┬─────────┘
                                                        │
                                                        │ transcrição
                                                        ▼
┌─────────────┐      ┌──────────────────┐      ┌──────────────────┐
│             │      │                  │      │                  │
│  Seu número │◀─────│  Evolution API   │◀─────│  Whisper API     │
│  (destino)  │      │  (sendText)      │      │  (envio)         │
│             │      │                  │      │                  │
└─────────────┘      └──────────────────┘      └──────────────────┘
```

### Fluxo detalhado:

1. Alguém envia um **áudio** para o seu número no WhatsApp (conversa privada ou grupo)
2. A **Evolution API** detecta a mensagem (evento `MESSAGES_UPSERT`)
3. O webhook envia o payload com o áudio em **base64** para sua API
4. O endpoint `POST /webhook/evolution` recebe e valida o token
5. Em **background** (não bloqueia a resposta):
   - Filtra: só processa se for `audioMessage` e `fromMe: false`
   - Decodifica o base64 → salva como `.ogg` temporário
   - **Whisper large-v3** transcreve o áudio para texto
   - Monta a mensagem com nome do remetente e local (grupo ou privado)
   - Envia a transcrição para o `NUMERO_DESTINO` via Evolution API
6. Limpa o arquivo temporário

### Formato da mensagem recebida:

```
João Silva: Bom dia, precisamos conversar sobre o projeto...
```

Se for de um grupo:

```
João Silva (120363025898...): Bom dia, temos reunião às 15h...
```

Se o contato não tem nome salvo:

```
5511999887766: Oi, pode me ligar?
```

---

## Troubleshooting

### Webhook não recebe eventos

1. Verifique se a Evolution API consegue acessar sua URL:
   ```bash
   # Na máquina da Evolution API, teste:
   curl http://SEU_SERVIDOR:8000/webhook/evolution/status
   ```

2. Verifique se o webhook está configurado:
   ```bash
   curl http://localhost:8080/webhook/find/whisper-bot \
     -H "apikey: SUA_INSTANCE_KEY"
   ```

3. Verifique se está escutando o evento correto (`MESSAGES_UPSERT`).

### Erro 403 no webhook

- O token no header `Authorization` não bate com o `WEBHOOK_TOKEN` do `.env`.
- Verifique se o header está correto: `Authorization: Bearer SEU_TOKEN`.

### Transcrição demora muito

- O Whisper large-v3 na CPU pode levar de 30 segundos a vários minutos por áudio.
- O processamento é feito em background — a Evolution API recebe 200 imediatamente.
- Se for inviável, considere usar um modelo menor (edite `main.py`, troque `"large-v3"` por `"medium"` ou `"small"`).

### WhatsApp desconectou

```bash
# Verificar status
curl http://localhost:8080/instance/connectionState/whisper-bot \
  -H "apikey: SUA_INSTANCE_KEY"

# Reconectar (gera novo QR code)
curl http://localhost:8080/instance/connect/whisper-bot \
  -H "apikey: SUA_INSTANCE_KEY"
```

### Áudio não chega no payload (base64 vazio)

- Verifique se o webhook está com `"base64": true`.
- A API tenta um fallback automático via `getBase64FromMediaMessage`, mas se também falhar, o áudio não será processado.

### Logs do PM2

```bash
# Logs em tempo real
pm2 logs whisper-api

# Últimas 100 linhas
pm2 logs whisper-api --lines 100

# Limpar logs
pm2 flush whisper-api
```
