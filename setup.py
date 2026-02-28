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
      - DATABASE_PROVIDER=postgresql
      - DATABASE_CONNECTION_URI=postgresql://evolution:evolution@evolution-db:5432/evolution
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


def _aguardar_evolution_api(url, apikey, tentativas=60):
    """Aguarda a Evolution API ficar pronta (polling). Padrão: até 2 minutos."""
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


def _aguardar_e_verificar(url, apikey):
    """
    Aguarda a Evolution API com rodadas de espera.
    Se não responder na primeira rodada, oferece esperar mais.
    """
    if _aguardar_evolution_api(url, apikey, tentativas=60):
        print("  ✅ Evolution API está rodando e respondendo!")
        return True

    # Primeira rodada falhou, oferece esperar mais
    print("  ⚠️  Evolution API ainda não respondeu após 2 minutos.")
    print("     Na primeira vez a imagem Docker pode demorar para inicializar.")

    while True:
        print("\n    1. Esperar mais 2 minutos")
        print("    2. Continuar o setup mesmo assim")
        print("    3. Sair do setup\n")
        escolha = perguntar("Escolha", "1")

        if escolha == "1":
            print("\n  ⏳ Aguardando mais...")
            if _aguardar_evolution_api(url, apikey, tentativas=60):
                print("  ✅ Evolution API está rodando e respondendo!")
                return True
            print("  ⚠️  Ainda sem resposta.")
        elif escolha == "2":
            return False
        elif escolha == "3":
            print("\n  Dica: verifique os logs com 'docker logs evolution-api'")
            sys.exit(1)
        else:
            print("  Opção inválida.")


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
    print("     (na primeira vez pode demorar enquanto o container inicializa)\n")

    _aguardar_e_verificar(url, apikey)

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
        instance_key = _criar_instancia_com_retry(url, global_key, instance_name)

    return instance_name, instance_key


def _criar_instancia_com_retry(url, global_key, instance_name, max_tentativas=5):
    """
    Tenta criar a instância na Evolution API com retries automáticos.
    Se a API ainda estiver subindo, aguarda entre tentativas.
    """
    for tentativa in range(1, max_tentativas + 1):
        print(f"\n  🔄 Criando instância '{instance_name}'... (tentativa {tentativa}/{max_tentativas})")

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
                    instance_data = data.get("instance", {})
                    instance_key = instance_data.get("token", "")

                print(f"  ✅ Instância '{instance_name}' criada com sucesso!")
                if instance_key:
                    print(f"  🔑 API Key da instância: {instance_key[:10]}...")
                else:
                    print("  ⚠️  Não foi possível obter a API key automaticamente.")
                    instance_key = perguntar("Cole a API Key da instância (hash)")
                return instance_key

            else:
                print(f"  ❌ Erro: {resp.status_code} — {resp.text[:200]}")

        except requests.ConnectionError:
            print(f"  ❌ Evolution API não está acessível em {url}")
            print("     O container pode ainda estar iniciando...")
        except Exception as e:
            print(f"  ❌ Erro: {e}")

        # Se não é a última tentativa, oferece opções
        if tentativa < max_tentativas:
            print(f"\n     Aguardando 15 segundos antes de tentar novamente...")
            time.sleep(15)
        else:
            # Última tentativa falhou — dá opções ao usuário
            print(f"\n  ⚠️  Não foi possível criar a instância após {max_tentativas} tentativas.")
            print("\n    1. Tentar mais vezes")
            print("    2. Digitar a API Key manualmente (se criou por fora)")
            print("    3. Sair do setup\n")

            escolha = perguntar("Escolha", "1")

            if escolha == "1":
                return _criar_instancia_com_retry(url, global_key, instance_name, max_tentativas)
            elif escolha == "2":
                return perguntar("API Key da instância (hash)")
            else:
                print("\n  Dica: verifique se a Evolution API está rodando com 'docker logs evolution-api'")
                sys.exit(1)

    # Fallback (não deve chegar aqui)
    return perguntar("API Key da instância (hash)")


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
        data = resp.json()
        state = data.get("instance", {}).get("state", data.get("state", ""))
        if state == "open":
            print("  ✅ WhatsApp já está conectado!")
            return
    except Exception:
        pass

    print("  Vamos gerar o QR Code para você escanear com o WhatsApp.\n")

    qr_exibido = False

    # Tenta obter o QR Code com retries (a instância pode precisar de alguns segundos)
    for tentativa_qr in range(6):
        try:
            resp = requests.get(
                f"{url}/instance/connect/{instance_name}",
                headers={"apikey": instance_key},
                timeout=30,
            )

            if resp.status_code == 200:
                data = resp.json()

                # Debug: mostra a resposta se não encontrar QR
                # A resposta pode ter diversas estruturas dependendo da versão
                qr_base64 = (
                    data.get("base64", "")
                    or data.get("qrcode", {}).get("base64", "")
                    if isinstance(data.get("qrcode"), dict) else data.get("base64", "")
                )
                qr_code_str = (
                    data.get("code", "")
                    or data.get("pairingCode", "")
                    or data.get("qrcode", "")
                    if isinstance(data.get("qrcode"), str) else data.get("code", "")
                )

                # Tenta extrair de qualquer campo que pareça ter dados de QR
                if not qr_base64 and not qr_code_str:
                    # Busca recursivamente por campos que parecem QR
                    for key, val in data.items():
                        if isinstance(val, str):
                            if val.startswith("data:image"):
                                qr_base64 = val
                                break
                            elif len(val) > 50 and "@" not in val:
                                # Pode ser o código do QR
                                qr_code_str = val
                                break
                        elif isinstance(val, dict):
                            for k2, v2 in val.items():
                                if isinstance(v2, str) and v2.startswith("data:image"):
                                    qr_base64 = v2
                                    break

                if qr_base64 or qr_code_str:
                    qr_exibido = _exibir_qr(qr_base64, qr_code_str)
                    if qr_exibido:
                        break
                else:
                    # Sem QR na resposta — pode ser cedo demais
                    if tentativa_qr < 5:
                        print(f"  ⏳ QR Code ainda não disponível, tentando novamente em 5s... ({tentativa_qr + 1}/6)")
                        time.sleep(5)
                    else:
                        print("  ⚠️  QR Code não retornado pela API após várias tentativas.")
                        print(f"     Última resposta: {json.dumps(data, indent=2)[:300]}")
            else:
                print(f"  ⚠️  Resposta {resp.status_code} ao obter QR Code.")
                if tentativa_qr < 5:
                    time.sleep(5)

        except Exception as e:
            print(f"  ❌ Erro ao obter QR Code: {e}")
            if tentativa_qr < 5:
                time.sleep(5)

    if not qr_exibido:
        print("\n  ℹ️  Opções para conectar manualmente:")
        print(f"     curl {url}/instance/connect/{instance_name} -H 'apikey: {instance_key}'")
        print("     Ou acesse a interface web da Evolution API.")

    # Aguarda o usuário escanear
    print("\n  ⏳ Aguardando conexão... (escaneie o QR Code com o WhatsApp)")
    print("     Pressione Ctrl+C para pular esta verificação.\n")

    try:
        for tentativa in range(90):  # Até 3 minutos
            time.sleep(2)
            try:
                resp = requests.get(
                    f"{url}/instance/connectionState/{instance_name}",
                    headers={"apikey": instance_key},
                    timeout=10,
                )
                data = resp.json()
                state = data.get("instance", {}).get("state", data.get("state", ""))

                if state == "open":
                    print("  ✅ WhatsApp conectado com sucesso!")
                    return

                # Mostra progresso
                if tentativa % 5 == 0:
                    print(f"     Status: {state}... (tentativa {tentativa + 1}/90)")

            except Exception:
                pass

        print("\n  ⏰ Tempo esgotado.")
        if not confirmar("Continuar o setup mesmo sem a conexão WhatsApp?"):
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n  ⏭️  Verificação pulada. Continue o setup.")


def _exibir_qr(qr_base64, qr_code_str):
    """Tenta exibir o QR Code no terminal. Retorna True se conseguiu."""
    import base64 as b64

    # Prioridade 1: código do QR como texto → renderiza como ASCII
    if qr_code_str and TEM_QRCODE:
        try:
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
            return True
        except Exception as e:
            print(f"  ⚠️  Erro ao renderizar QR: {e}")

    # Prioridade 2: base64 da imagem → salva como PNG
    if qr_base64:
        try:
            img_data = qr_base64
            if "," in img_data:
                img_data = img_data.split(",", 1)[1]
            with open("qrcode.png", "wb") as f:
                f.write(b64.b64decode(img_data))
            print("  📱 QR Code salvo em: qrcode.png")
            print("     Abra o arquivo e escaneie com o WhatsApp.")
            return True
        except Exception as e:
            print(f"  ⚠️  Erro ao salvar QR como imagem: {e}")

    # Prioridade 3: mostra o texto bruto
    if qr_code_str:
        print(f"  📱 Dados do QR Code (use um leitor externo):\n")
        print(f"  {qr_code_str}")
        return True

    return False


def passo_4_webhook(url, instance_name, instance_key):
    """Configura o webhook na Evolution API."""
    passo(4, TOTAL_PASSOS, "Configuração do Webhook")

    # Tenta descobrir o IP público da VPS para ser o padrão
    ip_publico = "localhost"
    try:
        resp_ip = requests.get("https://api.ipify.org", timeout=3)
        if resp_ip.status_code == 200:
            ip_publico = resp_ip.text.strip()
    except Exception:
        pass

    webhook_url = perguntar(
        "URL da sua API FastAPI (Ex: http://IP_DA_VPS:8000)",
        f"http://{ip_publico}:8000",
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

        if resp.status_code in (200, 201):
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
