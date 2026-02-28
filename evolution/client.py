"""
Cliente HTTP assíncrono para a Evolution API.
Responsável por enviar mensagens de texto via WhatsApp.
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

EVOLUTION_API_URL = os.getenv("EVOLUTION_API_URL", "http://localhost:8080")
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY", "")
EVOLUTION_INSTANCE = os.getenv("EVOLUTION_INSTANCE", "")


def _headers() -> dict:
    """Retorna headers padrão para as requisições à Evolution API."""
    return {
        "apikey": EVOLUTION_API_KEY,
        "Content-Type": "application/json",
    }


async def enviar_texto(numero: str, texto: str) -> dict:
    """
    Envia uma mensagem de texto via Evolution API.

    Args:
        numero: Número do destinatário com DDI (ex: 5511999999999)
        texto: Texto da mensagem

    Returns:
        Resposta da API como dict
    """
    url = f"{EVOLUTION_API_URL}/message/sendText/{EVOLUTION_INSTANCE}"
    payload = {
        "number": numero,
        "text": texto,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(url, json=payload, headers=_headers())
        response.raise_for_status()
        return response.json()


async def buscar_base64_midia(message_key: dict) -> str | None:
    """
    Busca o conteúdo base64 de uma mídia recebida via Evolution API.
    Usado como fallback caso o webhook não envie o base64 diretamente.

    Args:
        message_key: Dict com a key da mensagem (contém "id")

    Returns:
        String base64 do áudio ou None se falhar
    """
    url = f"{EVOLUTION_API_URL}/chat/getBase64FromMediaMessage/{EVOLUTION_INSTANCE}"
    payload = {
        "message": {
            "key": message_key,
        },
        "convertToMp4": False,
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload, headers=_headers())
            response.raise_for_status()
            data = response.json()
            return data.get("base64")
    except Exception as e:
        print(f"❌ Erro ao buscar base64 da mídia: {e}")
        return None
