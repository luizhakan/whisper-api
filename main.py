import whisper
import subprocess
import os
import sys
import glob
from fastapi import FastAPI

app = FastAPI()
# --- CONFIGURAÇÕES ---
ARQUIVO_AUDIO = "teste6.ogg"

@app.get("/")
async def root():
    texto_raw = ouvir_audio(ARQUIVO_AUDIO)
    return texto_raw


# Busca automática pelo modelo Qwen3
arquivos_modelo = glob.glob("*Qwen3-4B*Q4_K_M.gguf")
if not arquivos_modelo:
    print("❌ Erro: Modelo Qwen3 não encontrado.")
    sys.exit(1)

MODELO_GGUF = f"./{arquivos_modelo[0]}"
CAMINHO_LLAMA_CLI = "./llama-cli"

def ouvir_audio(arquivo):
    print(f"\n🎧 Ouvindo (Whisper Medium)... ", end="", flush=True)
    model = whisper.load_model("large-v3") 
    result = model.transcribe(arquivo, language='pt')
    texto = result["text"].strip()
    print("✅")
    return texto

def corrigir_texto(texto_bagunçado):
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
    
    comando = [
        CAMINHO_LLAMA_CLI,
        "-m", MODELO_GGUF,
        "-p", prompt_final,
        "-n", "4096",
        "-c", "8192",   
        "-t", "6",
        "--no-display-prompt", 
        "--log-disable"
    ]
    
    resultado = subprocess.run(
        comando, 
        capture_output=True, 
        text=True,
        encoding='utf-8', 
        errors='ignore'
    )
    
    saida = resultado.stdout.strip()
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
