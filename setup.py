#!/usr/bin/env python3
"""
Setup interativo para configurar a integração Whisper API + Evolution API.

Guia o usuário por todo o processo:
1. Dados de conexão com a Evolution API
2. Criação da instância WhatsApp
3. Conexão via QR Code (exibido no terminal)
4. Configuração do webhook
5. Número destino para transcrições
6. Geração do arquivo .env

Uso:
    python setup.py
"""

import os
import sys
import time
import json
import secrets
import subprocess
import shutil
import requests

# Tenta importar qrcode para renderizar QR no terminal
try:
    import qrcode
    TEM_QRCODE = True
except ImportError:
    TEM_QRCODE = False


# ============================================
# UTILIDADES
# ============================================

def limpar_tela():
    os.system("clear" if os.name != "nt" else "cls")


def banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🎙️  WHISPER API — Setup Interativo                         ║
║                                                              ║
║   Configuração da integração com WhatsApp (Evolution API)    ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
""")


def passo(numero, total, titulo):
    print(f"\n{'─'*60}")
    print(f"  📌 Passo {numero}/{total}: {titulo}")
    print(f"{'─'*60}\n")


def perguntar(prompt, padrao=None, obrigatorio=True):
    """Faz uma pergunta ao usuário com valor padrão opcional."""
    sufixo = f" [{padrao}]" if padrao else ""
    while True:
        resposta = input(f"  → {prompt}{sufixo}: ").strip()
        if not resposta and padrao:
            return padrao
        if not resposta and obrigatorio:
            print("  ⚠️  Este campo é obrigatório. Tente novamente.")
            continue
        return resposta


def confirmar(prompt):
    """Pede confirmação sim/não."""
    while True:
        resposta = input(f"  → {prompt} (s/n): ").strip().lower()
        if resposta in ("s", "sim", "y", "yes"):
            return True
        if resposta in ("n", "nao", "não", "no"):
            return False
        print("  ⚠️  Responda 's' ou 'n'.")


def testar_conexao(url, apikey):
    """Testa a conexão com a Evolution API."""
    try:
        response = requests.get(
            f"{url}/instance/fetchInstances",
            headers={"apikey": apikey},
            timeout=10,
        )
        return response.status_code == 200, response
    except requests.ConnectionError:
        return False, None
    except Exception as e:
        return False, str(e)


# ============================================
# PASSOS DO SETUP
# ============================================

TOTAL_PASSOS = 6

DOCKER_COMPOSE_TEMPLATE = """services:
  evolution-api:
    image: atendai/evolution-api:v2.2.3
    container_name: evolution-api
    restart: always
    ports:
      - "{porta}:8080"
    environment:
      - AUTHENTICATION_TYPE=apikey
      - AUTHENTICATION_API_KEY={apikey}
      - AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES=true
      - SERVER_PORT=8080
      - SERVER_URL=http://localhost:{porta}
      - DATABASE_PROVIDER=sqlite
      - DATABASE_CONNECTION_URI=file:./data/evolution.db
      - LOG_LEVEL=WARN
      - LOG_COLOR=true
    volumes:
      - evolution_data:/evolution/data
      - evolution_instances:/evolution/instances

volumes:
  evolution_data:
  evolution_instances:
"""


def _verificar_docker():
    """Verifica se Docker e Docker Compose estão instalados."""
    docker_ok = shutil.which("docker") is not None
    # Docker Compose pode ser plugin (docker compose) ou standalone (docker-compose)
    compose_ok = False
    compose_cmd = None

    if docker_ok:
        # Tenta 'docker compose' (plugin v2)
        try:
            result = subprocess.run(
                ["docker", "compose", "version"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                compose_ok = True
                compose_cmd = ["docker", "compose"]
        except Exception:
            pass

    if not compose_ok:
        # Tenta 'docker-compose' (standalone)
        if shutil.which("docker-compose"):
            compose_ok = True
            compose_cmd = ["docker-compose"]

    return docker_ok, compose_ok, compose_cmd


def _aguardar_evolution_api(url, apikey, tentativas=30):
    """Aguarda a Evolution API ficar pronta (polling)."""
    for i in range(tentativas):
        try:
            resp = requests.get(
                f"{url}/instance/fetchInstances",
                headers={"apikey": apikey},
                timeout=5,
            )
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        if i % 5 == 0:
            print(f"     Aguardando... ({i + 1}/{tentativas})")
        time.sleep(2)
    return False


def passo_1_evolution_api():
    """Verifica se a Evolution API existe ou instala via Docker."""
    passo(1, TOTAL_PASSOS, "Evolution API")

    print("  Você já tem a Evolution API instalada e rodando?\n")
    print("    1. Sim, já tenho rodando")
    print("    2. Não, quero que o setup instale automaticamente (Docker)\n")

    escolha = perguntar("Escolha", "1")

    if escolha == "2":
        return _instalar_evolution_api()
    else:
        return _conectar_evolution_existente()


def _conectar_evolution_existente():
    """Coleta dados de conexão com uma Evolution API já existente."""
    print("\n  Informe os dados de acesso à sua Evolution API.\n")

    url = perguntar("URL da Evolution API", "http://localhost:8080")
    url = url.rstrip("/")

    global_key = perguntar("API Key global (AUTHENTICATION_API_KEY do .env do servidor)")

    print("\n  🔄 Testando conexão...")
    ok, resp = testar_conexao(url, global_key)

    if ok:
        print("  ✅ Conexão com a Evolution API bem-sucedida!")
    else:
        print("  ❌ Não foi possível conectar na Evolution API.")
        print(f"     URL: {url}")
        if not confirmar("Deseja continuar mesmo assim?"):
            print("\n  Corrija a URL/chave e tente novamente.")
            sys.exit(1)

    return url, global_key


def _instalar_evolution_api():
    """Instala a Evolution API via Docker Compose."""
    print("\n  🐳 Vamos instalar a Evolution API via Docker.\n")

    # 1. Verifica Docker
    docker_ok, compose_ok, compose_cmd = _verificar_docker()

    if not docker_ok:
        print("  ❌ Docker não encontrado no sistema.")
        print("     Instale o Docker primeiro: https://docs.docker.com/engine/install/")
        print("\n     Após instalar, rode este setup novamente.")
        sys.exit(1)

    if not compose_ok:
        print("  ❌ Docker Compose não encontrado.")
        print("     Instale: https://docs.docker.com/compose/install/")
        sys.exit(1)

    print(f"  ✅ Docker encontrado")
    print(f"  ✅ Docker Compose encontrado ({' '.join(compose_cmd)})\n")

    # 2. Pede configurações
    porta = perguntar("Porta para a Evolution API", "8080")
    apikey = perguntar(
        "Crie uma API Key global (senha para acessar a Evolution API)",
        secrets.token_urlsafe(24),
    )

    url = f"http://localhost:{porta}"

    # 3. Define diretório de instalação
    diretorio_padrao = os.path.expanduser("~/evolution-api")
    diretorio = perguntar("Diretório de instalação", diretorio_padrao)
    diretorio = os.path.expanduser(diretorio)

    # 4. Cria o diretório
    os.makedirs(diretorio, exist_ok=True)
    compose_file = os.path.join(diretorio, "docker-compose.yml")

    if os.path.exists(compose_file):
        if not confirmar(f"docker-compose.yml já existe em {diretorio}. Sobrescrever?"):
            print("\n  Usando o docker-compose.yml existente.")
        else:
            _escrever_compose(compose_file, porta, apikey)
    else:
        _escrever_compose(compose_file, porta, apikey)

    # 5. Sobe o container
    print(f"\n  🚀 Subindo a Evolution API...\n")

    try:
        result = subprocess.run(
            compose_cmd + ["up", "-d"],
            cwd=diretorio,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            print(f"  ❌ Erro ao subir o container:")
            print(f"     {result.stderr[:500]}")
            if not confirmar("Deseja continuar o setup mesmo assim?"):
                sys.exit(1)
        else:
            print("  ✅ Container iniciado!")
            # Mostra o output se tiver algo útil
            if result.stdout.strip():
                for line in result.stdout.strip().split("\n")[:5]:
                    print(f"     {line}")

    except subprocess.TimeoutExpired:
        print("  ⚠️  Timeout ao subir o container (pode ainda estar baixando a imagem).")
        print("     Isso é normal na primeira vez — a imagem tem ~500MB.")
        print("     Verifique com: docker ps")
    except Exception as e:
        print(f"  ❌ Erro: {e}")
        if not confirmar("Continuar mesmo assim?"):
            sys.exit(1)

    # 6. Aguarda ficar pronto
    print(f"\n  ⏳ Aguardando a Evolution API ficar pronta em {url}...")

    if _aguardar_evolution_api(url, apikey):
        print("  ✅ Evolution API está rodando e respondendo!")
    else:
        print("  ⚠️  Evolution API ainda não respondeu.")
        print("     Pode estar iniciando. Verifique com:")
        print(f"     docker logs evolution-api")
        if not confirmar("Continuar o setup?"):
            sys.exit(1)

    print(f"\n  📋 Resumo da instalação:")
    print(f"     URL:       {url}")
    print(f"     API Key:   {apikey[:15]}...")
    print(f"     Diretório: {diretorio}")
    print(f"     Compose:   {compose_file}")

    return url, apikey


def _escrever_compose(path, porta, apikey):
    """Escreve o docker-compose.yml formatado."""
    conteudo = DOCKER_COMPOSE_TEMPLATE.format(porta=porta, apikey=apikey)
    with open(path, "w") as f:
        f.write(conteudo)
    print(f"  📄 docker-compose.yml gerado em: {path}")


def passo_2_instancia(url, global_key):
    """Cria (ou usa existente) uma instância na Evolution API."""
    passo(2, TOTAL_PASSOS, "Instância WhatsApp")

    # Verifica instâncias existentes
    print("  🔍 Verificando instâncias existentes...\n")
    try:
        resp = requests.get(
            f"{url}/instance/fetchInstances",
            headers={"apikey": global_key},
            timeout=10,
        )
        instancias = resp.json() if resp.status_code == 200 else []
    except Exception:
        instancias = []

    instance_name = None
    instance_key = None

    if instancias:
        print(f"  Instâncias encontradas ({len(instancias)}):\n")
        for i, inst in enumerate(instancias, 1):
            nome = inst.get("instance", {}).get("instanceName", inst.get("instanceName", "?"))
            status = inst.get("instance", {}).get("status", "?")
            print(f"    {i}. {nome} (status: {status})")

        print(f"\n    0. Criar nova instância\n")

        escolha = perguntar("Escolha uma opção (número)", "0")

        if escolha != "0":
            try:
                idx = int(escolha) - 1
                inst = instancias[idx]
                instance_name = inst.get("instance", {}).get("instanceName", inst.get("instanceName"))
                # Tenta pegar a apikey da instância
                instance_key = inst.get("instance", {}).get("token", "")
                if not instance_key:
                    instance_key = perguntar("API Key desta instância (hash)")
                print(f"\n  ✅ Usando instância existente: {instance_name}")
            except (ValueError, IndexError):
                print("  ⚠️  Opção inválida, criando nova instância...")
                escolha = "0"

    if not instance_name:
        # Criar nova instância
        instance_name = perguntar("Nome da nova instância", "whisper-bot")

        print(f"\n  🔄 Criando instância '{instance_name}'...")

        try:
            payload = {
                "instanceName": instance_name,
                "qrcode": True,
                "integration": "WHATSAPP-BAILEYS",
            }

            resp = requests.post(
                f"{url}/instance/create",
                json=payload,
                headers={
                    "apikey": global_key,
                    "Content-Type": "application/json",
                },
                timeout=30,
            )

            if resp.status_code in (200, 201):
                data = resp.json()
                instance_key = data.get("hash", data.get("apikey", ""))

                if not instance_key:
                    # Pode estar em estrutura diferente
                    instance_data = data.get("instance", {})
                    instance_key = instance_data.get("token", "")

                print(f"  ✅ Instância '{instance_name}' criada com sucesso!")
                if instance_key:
                    print(f"  🔑 API Key da instância: {instance_key[:10]}...")
                else:
                    print("  ⚠️  Não foi possível obter a API key automaticamente.")
                    instance_key = perguntar("Cole a API Key da instância (hash)")
            else:
                print(f"  ❌ Erro ao criar instância: {resp.status_code}")
                print(f"     {resp.text[:200]}")
                instance_key = perguntar("Crie manualmente e cole a API Key aqui")

        except Exception as e:
            print(f"  ❌ Erro: {e}")
            instance_key = perguntar("Crie manualmente e cole a API Key aqui")

    return instance_name, instance_key


def passo_3_conectar(url, instance_name, instance_key):
    """Conecta a instância via QR Code."""
    passo(3, TOTAL_PASSOS, "Conectar WhatsApp (QR Code)")

    # Verifica se já está conectado
    try:
        resp = requests.get(
            f"{url}/instance/connectionState/{instance_name}",
            headers={"apikey": instance_key},
            timeout=10,
        )
        state = resp.json().get("instance", {}).get("state", resp.json().get("state", ""))
        if state == "open":
            print("  ✅ WhatsApp já está conectado!")
            return
    except Exception:
        pass

    print("  Vamos gerar o QR Code para você escanear com o WhatsApp.\n")

    try:
        resp = requests.get(
            f"{url}/instance/connect/{instance_name}",
            headers={"apikey": instance_key},
            timeout=30,
        )

        if resp.status_code == 200:
            data = resp.json()
            # O QR code pode vir como base64 de imagem ou como string de dados
            qr_base64 = data.get("base64", "")
            qr_code_str = data.get("code", data.get("pairingCode", ""))

            if qr_base64 and TEM_QRCODE:
                # Extrai os dados do QR a partir do base64
                # Na verdade, precisamos do texto do QR. Vamos tentar pegar do "code"
                pass

            if qr_code_str and TEM_QRCODE:
                # Renderiza QR code como ASCII no terminal
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_L,
                    box_size=1,
                    border=1,
                )
                qr.add_data(qr_code_str)
                qr.make(fit=True)
                print("  📱 Escaneie o QR Code abaixo com o WhatsApp:\n")
                qr.print_ascii(invert=True)
            elif qr_code_str:
                print(f"  📱 Dados do QR Code (use um leitor):\n")
                print(f"  {qr_code_str}")
            elif qr_base64:
                # Salva como arquivo PNG
                import base64 as b64
                img_data = qr_base64
                if "," in img_data:
                    img_data = img_data.split(",", 1)[1]
                with open("qrcode.png", "wb") as f:
                    f.write(b64.b64decode(img_data))
                print("  📱 QR Code salvo em: qrcode.png")
                print("     Abra o arquivo e escaneie com o WhatsApp.")
            else:
                print("  ⚠️  QR Code não retornado pela API.")
                print(f"     Resposta: {json.dumps(data, indent=2)[:500]}")
                print("\n  Tente conectar manualmente pela interface da Evolution API.")
        else:
            print(f"  ❌ Erro ao obter QR Code: {resp.status_code}")
            print(f"     {resp.text[:200]}")

    except Exception as e:
        print(f"  ❌ Erro: {e}")

    # Aguarda o usuário escanear
    print("\n  ⏳ Aguardando conexão... (escaneie o QR Code com o WhatsApp)")
    print("     Pressione Ctrl+C para pular esta verificação.\n")

    try:
        for tentativa in range(60):  # Até 2 minutos
            time.sleep(2)
            try:
                resp = requests.get(
                    f"{url}/instance/connectionState/{instance_name}",
                    headers={"apikey": instance_key},
                    timeout=10,
                )
                state = resp.json().get("instance", {}).get("state", resp.json().get("state", ""))

                if state == "open":
                    print("  ✅ WhatsApp conectado com sucesso!")
                    return

                # Mostra progresso
                if tentativa % 5 == 0:
                    print(f"     Status: {state}... (tentativa {tentativa + 1}/60)")

            except Exception:
                pass

        print("\n  ⏰ Tempo esgotado. Verifique a conexão pela interface da Evolution API.")

    except KeyboardInterrupt:
        print("\n  ⏭️  Verificação pulada. Continue o setup.")


def passo_4_webhook(url, instance_name, instance_key):
    """Configura o webhook na Evolution API."""
    passo(4, TOTAL_PASSOS, "Configuração do Webhook")

    webhook_url = perguntar(
        "URL pública da sua API FastAPI (onde este servidor roda)",
        "http://localhost:8000",
    )
    webhook_url = webhook_url.rstrip("/")

    # Gera um token seguro
    token = secrets.token_urlsafe(32)
    print(f"\n  🔑 Token do webhook gerado: {token[:15]}...")

    # Monta a URL completa do endpoint
    endpoint_url = f"{webhook_url}/webhook/evolution"

    print(f"\n  🔄 Configurando webhook na Evolution API...")
    print(f"     URL: {endpoint_url}")

    try:
        payload = {
            "webhook": {
                "enabled": True,
                "url": endpoint_url,
                "headers": {
                    "Authorization": f"Bearer {token}",
                },
                "byEvents": False,
                "base64": True,
                "events": ["MESSAGES_UPSERT"],
            }
        }

        resp = requests.post(
            f"{url}/webhook/set/{instance_name}",
            json=payload,
            headers={
                "apikey": instance_key,
                "Content-Type": "application/json",
            },
            timeout=15,
        )

        if resp.status_code == 200:
            print("  ✅ Webhook configurado com sucesso!")
        else:
            print(f"  ⚠️  Resposta inesperada: {resp.status_code}")
            print(f"     {resp.text[:200]}")
            print("     Você pode configurar manualmente depois (veja docs/SETUP.md).")

    except Exception as e:
        print(f"  ❌ Erro ao configurar webhook: {e}")
        print("     Você pode configurar manualmente depois (veja docs/SETUP.md).")

    return webhook_url, token


def passo_5_numero_destino():
    """Coleta o número que vai receber as transcrições."""
    passo(5, TOTAL_PASSOS, "Número Destino")

    print("  Para qual número as transcrições dos áudios devem ser enviadas?")
    print("  Use o formato: DDI + DDD + número (sem +, sem espaços)")
    print("  Exemplo: 5511999999999\n")

    numero = perguntar("Número destino")

    # Remove caracteres extras
    numero = numero.replace("+", "").replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

    print(f"\n  ✅ As transcrições serão enviadas para: {numero}")
    return numero


def passo_6_gerar_env(dados):
    """Gera o arquivo .env com todos os dados coletados."""
    passo(6, TOTAL_PASSOS, "Gerando arquivo .env")

    env_content = f"""# ============================================
# Whisper API - Configuração
# Gerado automaticamente pelo setup.py
# Data: {time.strftime('%d/%m/%Y %H:%M:%S')}
# ============================================

# --- Evolution API ---
EVOLUTION_API_URL={dados['url']}
EVOLUTION_API_GLOBAL_KEY={dados['global_key']}
EVOLUTION_API_KEY={dados['instance_key']}
EVOLUTION_INSTANCE={dados['instance_name']}

# --- WhatsApp ---
NUMERO_DESTINO={dados['numero_destino']}

# --- Webhook ---
WEBHOOK_URL={dados['webhook_url']}
WEBHOOK_TOKEN={dados['webhook_token']}

# --- Email (Gmail SMTP) ---
# Preencha manualmente se quiser usar o envio por email
APP_SENHA_GOOGLE=
"""

    # Verifica se .env já existe
    if os.path.exists(".env"):
        if not confirmar("Arquivo .env já existe. Sobrescrever?"):
            nome_alt = f".env.{int(time.time())}"
            with open(nome_alt, "w") as f:
                f.write(env_content)
            print(f"\n  📄 Salvo como: {nome_alt}")
            return

    with open(".env", "w") as f:
        f.write(env_content)

    print("  ✅ Arquivo .env gerado com sucesso!")


def resumo_final(dados):
    """Exibe resumo e instruções finais."""
    print(f"""
{'═'*60}

  🎉 SETUP CONCLUÍDO COM SUCESSO!

{'═'*60}

  Resumo da configuração:

    Evolution API:  {dados['url']}
    Instância:      {dados['instance_name']}
    Webhook:        {dados['webhook_url']}/webhook/evolution
    Destino:        {dados['numero_destino']}

{'─'*60}

  Para iniciar o servidor:

    # Com PM2 (recomendado para produção):
    pm2 start ecosystem.config.js

    # Com uvicorn direto (dev):
    uvicorn main:app --host 0.0.0.0 --port 8000 --reload

{'─'*60}

  Para verificar se está funcionando:

    # Status do webhook:
    curl http://localhost:8000/webhook/evolution/status

    # Logs do PM2:
    pm2 logs whisper-api

{'─'*60}

  📖 Para mais detalhes, veja: docs/SETUP.md

{'═'*60}
""")


# ============================================
# MAIN
# ============================================

def main():
    limpar_tela()
    banner()

    print("  Este assistente vai configurar a integração entre o Whisper API")
    print("  e o WhatsApp via Evolution API.\n")
    print("  O que será configurado:")
    print("    • Evolution API (instala via Docker se necessário)")
    print("    • Instância WhatsApp + QR Code")
    print("    • Webhook para receber áudios")
    print("    • Arquivo .env com todas as variáveis\n")
    print("  Pré-requisitos:")
    print("    • Python 3.10+ com dependências instaladas")
    print("    • Docker (se precisar instalar a Evolution API)")
    print("    • Acesso ao WhatsApp para escanear QR Code\n")

    if not confirmar("Pronto para começar?"):
        print("\n  Até logo! 👋")
        sys.exit(0)

    # Passo 1: Conexão Evolution API
    url, global_key = passo_1_evolution_api()

    # Passo 2: Instância
    instance_name, instance_key = passo_2_instancia(url, global_key)

    # Passo 3: Conectar WhatsApp
    passo_3_conectar(url, instance_name, instance_key)

    # Passo 4: Webhook
    webhook_url, webhook_token = passo_4_webhook(url, instance_name, instance_key)

    # Passo 5: Número destino
    numero_destino = passo_5_numero_destino()

    # Passo 6: Gerar .env
    dados = {
        "url": url,
        "global_key": global_key,
        "instance_name": instance_name,
        "instance_key": instance_key,
        "webhook_url": webhook_url,
        "webhook_token": webhook_token,
        "numero_destino": numero_destino,
    }
    passo_6_gerar_env(dados)

    # Resumo final
    resumo_final(dados)


if __name__ == "__main__":
    main()
