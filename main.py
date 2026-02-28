import whisper
import os
import glob
from typing import Optional
from fastapi import FastAPI, File, UploadFile, Request, BackgroundTasks, HTTPException
import uuid
from datetime import datetime
import shutil
from llama_cpp import Llama
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv

# Carrega variáveis de ambiente
load_dotenv()

app = FastAPI()

# --- CARREGAMENTO DO MODELO ---
print("🔄 Carregando modelo Whisper large-v3...")
MODELO_WHISPER = whisper.load_model("large-v3")
print("✅ Modelo Whisper carregado com sucesso!")

MODELO_QWEN: Optional[Llama] = None
ERRO_MODELO_QWEN: Optional[str] = None

# Configuração de email
EMAIL_REMETENTE = "hakanluiz96@gmail.com"
SENHA_GOOGLE = os.getenv("APP_SENHA_GOOGLE")

# Configuração do webhook Evolution API
WEBHOOK_TOKEN = os.getenv("WEBHOOK_TOKEN", "")


def carregar_modelo_qwen():
    global MODELO_QWEN, ERRO_MODELO_QWEN

    arquivos_modelo = glob.glob("*Qwen3-4B*Q4_K_M.gguf")
    if not arquivos_modelo:
        ERRO_MODELO_QWEN = "Modelo Qwen3 não encontrado no diretório do projeto."
        print(f"⚠️  {ERRO_MODELO_QWEN}")
        return

    modelo_gguf = os.path.abspath(arquivos_modelo[0])
    print(f"🔄 Carregando modelo Qwen3 ({arquivos_modelo[0]})...")
    print(f"   Caminho: {modelo_gguf}")

    try:
        MODELO_QWEN = Llama(
            model_path=modelo_gguf,
            n_ctx=8192,
            n_threads=6,
            verbose=True
        )
        print("✅ Modelo Qwen3 carregado com sucesso!")
    except Exception as exc:
        MODELO_QWEN = None
        ERRO_MODELO_QWEN = str(exc)
        print("⚠️  Falha ao carregar o Qwen3. API seguirá ativa sem correção de texto.")
        print(f"   Detalhes: {ERRO_MODELO_QWEN}")
        print("   Dica: atualize para `llama-cpp-python>=0.3.16` e reinstale as dependências.")


carregar_modelo_qwen()

# --- CONFIGURAÇÕES ---
# ARQUIVO_AUDIO = "teste6.ogg"

@app.get("/")
async def root():
    return f"API EM FUNCIONAMENTO - {datetime.now()}"


# ============================================
# ENDPOINTS - EVOLUTION API (WEBHOOK WHATSAPP)
# ============================================


@app.post("/webhook/evolution")
async def webhook_evolution(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint que recebe eventos da Evolution API.
    Filtra apenas mensagens de áudio, transcreve com Whisper
    e envia a transcrição para o NUMERO_DESTINO via WhatsApp.

    Header obrigatório: Authorization: Bearer {WEBHOOK_TOKEN}
    """
    # Valida autenticação
    if WEBHOOK_TOKEN:
        auth_header = request.headers.get("authorization", "")
        # Aceita tanto "Bearer TOKEN" quanto "TOKEN" direto
        token = auth_header.replace("Bearer ", "").strip()
        if token != WEBHOOK_TOKEN:
            raise HTTPException(status_code=403, detail="Token inválido")

    # Parseia o payload
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Payload JSON inválido")

    # Processa em background (Whisper na CPU pode levar 30s-2min)
    # Responde 200 imediatamente para não travar a Evolution API
    from evolution.webhook_handler import processar_webhook
    from evolution.client import enviar_texto

    background_tasks.add_task(
        processar_webhook,
        data=data,
        fn_transcrever=ouvir_audio,
        fn_enviar_texto=enviar_texto,
    )

    return {"status": "recebido", "processando": True}


@app.get("/webhook/evolution/status")
async def webhook_status():
    """Health check do webhook — útil para verificar se o endpoint está ativo."""
    return {
        "status": "ativo",
        "webhook_token_configurado": bool(WEBHOOK_TOKEN),
        "numero_destino": os.getenv("NUMERO_DESTINO", "não configurado"),
        "evolution_instance": os.getenv("EVOLUTION_INSTANCE", "não configurado"),
        "horario": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
    }


# ============================================
# ENDPOINTS - TRANSCRIÇÃO DIRETA
# ============================================

@app.post("/transcrever/")
async def transcricao(arquivo: UploadFile = File(...)):
    """Endpoint que faz apenas a transcrição do áudio, sem correções."""
    inicio = datetime.now()
    print(f"\n⏱️  Requisição iniciada em: {inicio.strftime('%H:%M:%S')}")
    
    extensao = arquivo.filename.split(".")[-1]
    nome_temporario = f"temp_{uuid.uuid4()}.{extensao}"
    
    try:
        with open(nome_temporario, "wb") as buffer:
            shutil.copyfileobj(arquivo.file, buffer)
            texto_transcrito = ouvir_audio(nome_temporario)

            fim = datetime.now()
            duracao = (fim - inicio).total_seconds()
            print(f"⏱️  Requisição finalizada em: {fim.strftime('%H:%M:%S')}")
            print(f"⏱️  Duração total: {duracao:.2f} segundos\n")

            return {
                "nome_arquivo": arquivo.filename,
                "transcricao": texto_transcrito,
                "horario_inicio": inicio.strftime('%H:%M:%S'),
                "horario_fim": fim.strftime('%H:%M:%S'),
                "duracao_segundos": round(duracao, 2)
            }
        
    except Exception as e:
        fim = datetime.now()
        duracao = (fim - inicio).total_seconds()
        print(f"❌ Erro após {duracao:.2f} segundos\n")
        return {"erro": str(e)}
    
    finally:
        if os.path.exists(nome_temporario):
            os.remove(nome_temporario)
            print(f"🧹 Arquivo temporário removido.")

@app.post("/transcrever-e-corrigir/")
async def transcricao_com_correcao(arquivo: UploadFile = File(...)):
    """Endpoint que faz a transcrição e aplica correção de texto com Qwen3."""
    inicio = datetime.now()
    print(f"\n⏱️  Requisição iniciada em: {inicio.strftime('%H:%M:%S')}")
    
    extensao = arquivo.filename.split(".")[-1]
    nome_temporario = f"temp_{uuid.uuid4()}.{extensao}"
    
    try:
        with open(nome_temporario, "wb") as buffer:
            shutil.copyfileobj(arquivo.file, buffer)
            texto_transcrito = ouvir_audio(nome_temporario)
            texto_corrigido = corrigir_texto(texto_transcrito)

            fim = datetime.now()
            duracao = (fim - inicio).total_seconds()
            print(f"⏱️  Requisição finalizada em: {fim.strftime('%H:%M:%S')}")
            print(f"⏱️  Duração total: {duracao:.2f} segundos\n")

            return {
                "nome_arquivo": arquivo.filename,
                "transcricao_original": texto_transcrito,
                "transcricao_corrigida": texto_corrigido,
                "horario_inicio": inicio.strftime('%H:%M:%S'),
                "horario_fim": fim.strftime('%H:%M:%S'),
                "duracao_segundos": round(duracao, 2)
            }
        
    except Exception as e:
        fim = datetime.now()
        duracao = (fim - inicio).total_seconds()
        print(f"❌ Erro após {duracao:.2f} segundos\n")
        return {"erro": str(e)}
    
    finally:
        if os.path.exists(nome_temporario):
            os.remove(nome_temporario)
            print(f"🧹 Arquivo temporário removido.")

def ouvir_audio(arquivo):
    print(f"\n🎧 Ouvindo (Whisper Large-v3)... ", end="", flush=True)
    result = MODELO_WHISPER.transcribe(arquivo, language='pt')
    texto = result["text"].strip()
    print("✅")
    return texto

def corrigir_texto(texto_bagunçado):
    if MODELO_QWEN is None:
        print("⚠️  Qwen3 indisponível, retornando texto original.")
        if ERRO_MODELO_QWEN:
            print(f"   Motivo: {ERRO_MODELO_QWEN}")
        return texto_bagunçado

    print("✍️  Qwen3 passando a limpo... ", end="", flush=True)
    
    # --- PROMPT: O CORRETOR INVISÍVEL ---
    prompt_sistema = (
        "Você é um Revisor de Texto especialista em Português Brasileiro. "
        "Sua tarefa é corrigir a gramática, a pontuação e a ortografia da transcrição abaixo. "
        "IMPORTANTE:\n"
        "1. MANTENHA O TOM INFORMAL E CONVERSACIONAL. Não deixe o texto robótico ou corporativo.\n"
        "2. Corrija erros fonéticos óbvios (ex: 'frio' -> 'freela', 'mini looker' -> 'Mini PC/NUC').\n"
        "3. Respeite os termos técnicos (Codex, Copilot, MCP, Stack Overflow).\n"
        "4. Apenas devolva o texto corrigido, sem adicionar comentários."
    )

    prompt_final = (
        f"<|im_start|>system\n{prompt_sistema}<|im_end|>\n"
        f"<|im_start|>user\nCorrija este texto mantendo o estilo original:\n\n{texto_bagunçado}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    
    resposta = MODELO_QWEN(
        prompt_final,
        max_tokens=4096,
        temperature=0.3,
        stop=["<|im_end|>"]
    )
    
    saida = resposta['choices'][0]['text'].strip()
    print("✅")
    return saida

def enviar_email_gmail(destinatario: str, assunto: str, corpo_html: str):
    """Envia email via SMTP do Gmail com os resultados das transcrições."""
    try:
        # Configura a conexão SMTP
        servidor_smtp = "smtp.gmail.com"
        porta = 587
        
        # Cria a mensagem
        mensagem = MIMEMultipart("alternative")
        mensagem["From"] = EMAIL_REMETENTE
        mensagem["To"] = destinatario
        mensagem["Subject"] = assunto
        
        # Adiciona o corpo em HTML
        parte_html = MIMEText(corpo_html, "html")
        mensagem.attach(parte_html)
        
        # Conecta e envia
        print(f"\n📧 Conectando ao servidor SMTP do Gmail...")
        with smtplib.SMTP(servidor_smtp, porta) as server:
            server.starttls()  # Inicia a conexão segura
            server.login(EMAIL_REMETENTE, SENHA_GOOGLE)
            print(f"✅ Autenticado com sucesso!")
            
            print(f"📤 Enviando email para {destinatario}...")
            server.send_message(mensagem)
            print(f"✅ Email enviado com sucesso!")
            
        return {"status": "sucesso", "mensagem": "Email enviado com sucesso"}
        
    except smtplib.SMTPAuthenticationError:
        erro = "Erro de autenticação. Verifique a senha do Google."
        print(f"❌ {erro}")
        return {"status": "erro", "mensagem": erro}
    except Exception as e:
        erro = f"Erro ao enviar email: {str(e)}"
        print(f"❌ {erro}")
        return {"status": "erro", "mensagem": erro}

@app.post("/transcrever-e-enviar/")
async def transcrever_e_enviar(
    arquivos: list[UploadFile] = File(...),
    destinatario: str = None,
    corrigir: bool = False
):
    """
    Endpoint que recebe múltiplos áudios, transcreve na ordem enviada
    e envia um email com todos os resultados.
    
    Parâmetros:
    - arquivos: Lista de arquivos de áudio
    - destinatario: Email para enviar os resultados (obrigatório)
    - corrigir: Se True, aplica correção com Qwen3 (padrão: False)
    
    Exemplo com curl:
    curl -X POST http://localhost:8000/transcrever-e-enviar/ \
      -F "arquivos=@audio1.mp3" \
      -F "arquivos=@audio2.mp3" \
      -F "destinatario=seu@email.com" \
      -F "corrigir=false"
    """
    
    if not destinatario:
        return {
            "erro": "Parâmetro 'destinatario' é obrigatório",
            "exemplo": "?destinatario=seu@email.com"
        }
    
    if not arquivos:
        return {"erro": "Nenhum arquivo foi enviado"}
    
    inicio_geral = datetime.now()
    print(f"\n{'='*70}")
    print(f"🚀 PROCESSAMENTO EM LOTE - Múltiplos Áudios")
    print(f"⏱️  Iniciado em: {inicio_geral.strftime('%H:%M:%S')}")
    print(f"📧 Email de destino: {destinatario}")
    print(f"🔧 Correção: {'Sim (Qwen3)' if corrigir else 'Não'}")
    print(f"📦 Quantidade de áudios: {len(arquivos)}")
    print(f"{'='*70}\n")
    
    resultados = []
    
    try:
        # Processa cada áudio na ordem
        for índice, arquivo in enumerate(arquivos, 1):
            print(f"\n📍 [{índice}/{len(arquivos)}] Processando: {arquivo.filename}")
            
            extensao = arquivo.filename.split(".")[-1]
            nome_temporario = f"temp_{uuid.uuid4()}.{extensao}"
            
            try:
                inicio_arquivo = datetime.now()
                
                with open(nome_temporario, "wb") as buffer:
                    shutil.copyfileobj(arquivo.file, buffer)
                    
                    # Transcreve
                    texto_transcrito = ouvir_audio(nome_temporario)
                    
                    # Opcionalmente corrige
                    if corrigir:
                        texto_final = corrigir_texto(texto_transcrito)
                    else:
                        texto_final = texto_transcrito
                    
                    fim_arquivo = datetime.now()
                    duracao_arquivo = (fim_arquivo - inicio_arquivo).total_seconds()
                    
                    resultado_item = {
                        "número": índice,
                        "arquivo": arquivo.filename,
                        "transcricao": texto_final,
                        "corrigida": corrigir,
                        "duracao_segundos": round(duracao_arquivo, 2)
                    }
                    
                    resultados.append(resultado_item)
                    print(f"   ✅ Concluído em {duracao_arquivo:.2f}s")
                    
            except Exception as e:
                print(f"   ❌ Erro: {str(e)}")
                resultados.append({
                    "número": índice,
                    "arquivo": arquivo.filename,
                    "erro": str(e)
                })
            
            finally:
                if os.path.exists(nome_temporario):
                    os.remove(nome_temporario)
        
        # Gera HTML para email
        corpo_html = gerar_html_email(resultados, corrigir)
        
        # Envia email
        print(f"\n{'─'*70}")
        resultado_email = enviar_email_gmail(
            destinatario=destinatario,
            assunto="📝 Transcrição de Áudios Concluída",
            corpo_html=corpo_html
        )
        
        fim_geral = datetime.now()
        duracao_geral = (fim_geral - inicio_geral).total_seconds()
        
        print(f"\n{'='*70}")
        print(f"✅ PROCESSO CONCLUÍDO COM SUCESSO!")
        print(f"⏱️  Finalizado em: {fim_geral.strftime('%H:%M:%S')}")
        print(f"⏱️  Duração total: {duracao_geral:.2f} segundos")
        print(f"{'='*70}\n")
        
        return {
            "status": "sucesso",
            "total_arquivos": len(arquivos),
            "email_enviado": resultado_email.get("status") == "sucesso",
            "mensagem_email": resultado_email.get("mensagem"),
            "resultados": resultados,
            "horario_inicio": inicio_geral.strftime('%H:%M:%S'),
            "horario_fim": fim_geral.strftime('%H:%M:%S'),
            "duracao_total_segundos": round(duracao_geral, 2)
        }
        
    except Exception as e:
        fim_geral = datetime.now()
        duracao_geral = (fim_geral - inicio_geral).total_seconds()
        
        print(f"\n❌ ERRO GERAL: {str(e)}")
        print(f"⏱️  Duração até o erro: {duracao_geral:.2f} segundos\n")
        
        return {
            "status": "erro",
            "erro": str(e),
            "resultados_parciais": resultados,
            "duracao_segundos": round(duracao_geral, 2)
        }

def gerar_html_email(resultados: list, corrigir: bool) -> str:
    """Gera o HTML para o email com os resultados das transcrições."""
    
    itens_html = ""
    for item in resultados:
        if "erro" in item:
            itens_html += f"""
            <div style="margin: 20px 0; padding: 15px; background-color: #ffe6e6; border-left: 4px solid #dc3545; border-radius: 4px;">
                <strong style="color: #dc3545;">❌ {item['arquivo']}</strong>
                <p style="margin: 10px 0; color: #666;"><strong>Erro:</strong> {item['erro']}</p>
            </div>
            """
        else:
            itens_html += f"""
            <div style="margin: 20px 0; padding: 15px; background-color: #e6f3ff; border-left: 4px solid #0066cc; border-radius: 4px;">
                <strong style="color: #0066cc;">✅ Áudio {item['número']}: {item['arquivo']}</strong>
                <p style="margin: 10px 0; color: #666;"><strong>Duração:</strong> {item['duracao_segundos']}s</p>
                <p style="margin: 10px 0; padding: 10px; background-color: white; border-radius: 4px; color: #333;">
                    <strong>Transcrição{'  (Corrigida)' if item.get('corrigida') else ''}:</strong><br/>
                    {item['transcricao']}
                </p>
            </div>
            """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
            }}
            .container {{
                max-width: 800px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                border-radius: 8px;
                margin-bottom: 30px;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
            }}
            .header p {{
                margin: 10px 0 0 0;
                opacity: 0.9;
            }}
            .resumo {{
                background-color: white;
                padding: 15px;
                margin-bottom: 20px;
                border-radius: 4px;
                border-left: 4px solid #667eea;
            }}
            .footer {{
                text-align: center;
                margin-top: 30px;
                color: #999;
                font-size: 12px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>📝 Transcrição de Áudios Concluída</h1>
                <p>Seus áudios foram processados e transcritos com sucesso!</p>
            </div>
            
            <div class="resumo">
                <strong>📊 Resumo do Processamento:</strong>
                <ul style="margin: 10px 0;">
                    <li><strong>Total de áudios:</strong> {len(resultados)}</li>
                    <li><strong>Correção aplicada:</strong> {'Sim (Qwen3 IA)' if corrigir else 'Não'}</li>
                    <li><strong>Data:</strong> {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}</li>
                </ul>
            </div>
            
            <div>
                <strong style="font-size: 18px;">📋 Resultados Detalhados:</strong>
                {itens_html}
            </div>
            
            <div class="footer">
                <p>Este email foi gerado automaticamente pela API Whisper.</p>
                <p>Não responda este email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html
# if __name__ == "__main__":
#     if not os.path.exists(ARQUIVO_AUDIO):
#         print(f"❌ Arquivo '{ARQUIVO_AUDIO}' não encontrado.")
#         sys.exit(1)

#     texto_raw = ouvir_audio(ARQUIVO_AUDIO)
    
#     if texto_raw:
#         print("\n" + "░"*60)
#         print(f"👂 WHISPER DIZ:\n{texto_raw}")
#         print("░"*60 + "\n")
        
#         texto_limpo = corrigir_texto(texto_raw)
        
#         print("\n" + "▓"*60)
#         print("✨ TEXTO CORRIGIDO (Qwen3):")
#         print(texto_limpo)
#         print("▓"*60 + "\n")
#     else:
#         print("❌ Áudio vazio.")
