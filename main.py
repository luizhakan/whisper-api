import whisper
import os
import glob
from typing import Optional
from fastapi import FastAPI, File, UploadFile
import uuid
from datetime import datetime
import shutil
from llama_cpp import Llama

app = FastAPI()

# --- CARREGAMENTO DO MODELO ---
print("🔄 Carregando modelo Whisper large-v3...")
MODELO_WHISPER = whisper.load_model("large-v3")
print("✅ Modelo Whisper carregado com sucesso!")

MODELO_QWEN: Optional[Llama] = None
ERRO_MODELO_QWEN: Optional[str] = None


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
    # texto_raw = ouvir_audio(ARQUIVO_AUDIO)
    return f"API EM FUNCIONAMENTO - {datetime.now()}"

@app.post("/transcrever/")
async def transcricao(arquivo: UploadFile = File(...)):
    extensao = arquivo.filename.split(".")[-1]
    nome_temporario = f"temp_{uuid.uuid4()}.{extensao}"
    
    try:
        with open(nome_temporario, "wb") as buffer:
            shutil.copyfileobj(arquivo.file, buffer)
            texto_transcrito = ouvir_audio(nome_temporario)

            return {
                "nome_arquivo": arquivo.filename,
                "transcricao": texto_transcrito
            }
        
    except Exception as e:
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

# # --- EXECUÇÃO ---
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
