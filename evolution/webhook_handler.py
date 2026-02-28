"""
Handler do webhook da Evolution API.
Processa eventos MESSAGES_UPSERT, filtra mensagens de áudio,
transcreve com Whisper e envia a transcrição para o número destino.
"""

import os
import base64
import uuid
import tempfile
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

NUMERO_DESTINO = os.getenv("NUMERO_DESTINO", "")


def extrair_info_remetente(data: dict) -> dict:
    """
    Extrai informações do remetente a partir do payload do webhook.

    Returns:
        Dict com:
            - nome: pushName ou número
            - numero: número limpo (sem @s.whatsapp.net)
            - local: nome do grupo ou None (conversa privada)
            - eh_grupo: bool
    """
    # Pega o key da mensagem
    key = data.get("key", {})
    remote_jid = key.get("remoteJid", "")

    # Detecta se é grupo
    eh_grupo = remote_jid.endswith("@g.us")

    # Nome do remetente (pushName é o nome que o contato definiu no WhatsApp)
    push_name = data.get("pushName", "")

    if eh_grupo:
        # Em grupos, o participant é quem enviou a mensagem
        participant = key.get("participant", "")
        numero_remetente = participant.replace("@s.whatsapp.net", "")
        # remoteJid em grupos é o ID do grupo, não o nome legível
        # O nome do grupo pode vir em groupMetadata ou no próprio remoteJid
        grupo_id = remote_jid.replace("@g.us", "")
    else:
        # Conversa privada: remoteJid é o número do remetente
        numero_remetente = remote_jid.replace("@s.whatsapp.net", "")
        grupo_id = None

    nome = push_name if push_name else numero_remetente

    return {
        "nome": nome,
        "numero": numero_remetente,
        "local": grupo_id if eh_grupo else None,
        "eh_grupo": eh_grupo,
    }


def extrair_audio_base64(data: dict) -> str | None:
    """
    Extrai o conteúdo base64 do áudio a partir do payload do webhook.
    Quando o webhook está configurado com base64=true, a mídia vem embutida.

    Returns:
        String base64 do áudio ou None se não encontrado
    """
    message = data.get("message", {})

    # Tenta pegar o audioMessage
    audio_msg = message.get("audioMessage", {})

    # O base64 pode vir em diferentes locais dependendo da versão da Evolution API
    # Campo direto no payload (quando base64=true no webhook)
    base64_data = data.get("base64")

    if not base64_data:
        # Tenta dentro do message
        base64_data = message.get("base64")

    if not base64_data:
        # Tenta dentro do audioMessage
        base64_data = audio_msg.get("base64")

    return base64_data


def eh_mensagem_audio(data: dict) -> bool:
    """Verifica se o payload é uma mensagem de áudio."""
    message_type = data.get("messageType", "")
    return message_type == "audioMessage"


def eh_mensagem_propria(data: dict) -> bool:
    """Verifica se a mensagem foi enviada pelo próprio bot (fromMe)."""
    key = data.get("key", {})
    return key.get("fromMe", False)


async def processar_webhook(data: dict, fn_transcrever, fn_enviar_texto):
    """
    Processa o payload completo do webhook da Evolution API.

    Fluxo:
    1. Verifica se é evento de mensagem
    2. Filtra apenas mensagens de áudio (ignora texto, imagem etc.)
    3. Ignora mensagens próprias (evita loop)
    4. Extrai o áudio em base64
    5. Transcreve com Whisper
    6. Envia a transcrição para o NUMERO_DESTINO

    Args:
        data: Payload JSON do webhook
        fn_transcrever: Função de transcrição (ouvir_audio do main.py)
        fn_enviar_texto: Função assíncrona para enviar texto (evolution.client.enviar_texto)
    """
    from evolution.client import buscar_base64_midia

    # O payload pode vir encapsulado em diferentes estruturas
    # Normaliza: pode ter um array de dados ou dado único
    if isinstance(data, list):
        for item in data:
            await _processar_mensagem(item, fn_transcrever, fn_enviar_texto)
    else:
        await _processar_mensagem(data, fn_transcrever, fn_enviar_texto)


async def _processar_mensagem(data: dict, fn_transcrever, fn_enviar_texto):
    """Processa uma única mensagem do webhook."""
    from evolution.client import buscar_base64_midia

    # Ignora mensagens próprias
    if eh_mensagem_propria(data):
        print("⏭️  Mensagem própria (fromMe), ignorando.")
        return

    # Filtra apenas áudio
    if not eh_mensagem_audio(data):
        return

    print(f"\n{'='*60}")
    print(f"🎵 Áudio recebido via WhatsApp!")
    print(f"⏱️  {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")

    # Extrai informações do remetente
    info = extrair_info_remetente(data)
    print(f"👤 De: {info['nome']} ({info['numero']})")
    if info["eh_grupo"]:
        print(f"👥 Grupo: {info['local']}")

    # Extrai áudio base64
    audio_base64 = extrair_audio_base64(data)

    # Se não veio no payload, tenta buscar via API
    if not audio_base64:
        print("📥 Base64 não encontrado no payload, buscando via API...")
        key = data.get("key", {})
        audio_base64 = await buscar_base64_midia(key)

    if not audio_base64:
        print("❌ Não foi possível obter o áudio. Abortando.")
        return

    # Decodifica e salva como arquivo temporário
    nome_temp = None
    try:
        # Remove prefixo data:audio/... se presente
        if "," in audio_base64:
            audio_base64 = audio_base64.split(",", 1)[1]

        audio_bytes = base64.b64decode(audio_base64)
        nome_temp = f"temp_webhook_{uuid.uuid4()}.ogg"

        with open(nome_temp, "wb") as f:
            f.write(audio_bytes)

        print(f"💾 Áudio salvo temporariamente ({len(audio_bytes)} bytes)")

        # Transcreve com Whisper
        print("🎧 Transcrevendo com Whisper...")
        texto = fn_transcrever(nome_temp)

        if not texto or texto.strip() == "":
            print("⚠️  Transcrição vazia, ignorando.")
            return

        print(f"📝 Transcrição: {texto[:100]}{'...' if len(texto) > 100 else ''}")

        # Monta a mensagem formatada
        mensagem = _formatar_mensagem(info, texto)

        # Envia para o número destino
        print(f"📤 Enviando transcrição para {NUMERO_DESTINO}...")
        await fn_enviar_texto(NUMERO_DESTINO, mensagem)
        print("✅ Transcrição enviada com sucesso!")

    except Exception as e:
        print(f"❌ Erro ao processar áudio: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Limpa arquivo temporário
        if nome_temp and os.path.exists(nome_temp):
            os.remove(nome_temp)
            print("🧹 Arquivo temporário removido.")

    print(f"{'='*60}\n")


def _formatar_mensagem(info: dict, texto: str) -> str:
    """
    Formata a mensagem de transcrição para envio.

    Formato:
        - Conversa privada: "João Silva: texto transcrito"
        - Grupo: "João Silva (120363...): texto transcrito"
    """
    nome = info["nome"]

    if info["eh_grupo"] and info["local"]:
        return f"{nome} ({info['local']}): {texto}"
    else:
        return f"{nome}: {texto}"
