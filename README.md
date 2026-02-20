# Whisper API

Este projeto é uma implementação da API Whisper, que permite a transcrição de áudio em texto.

## 🆕 Nova Funcionalidade: Transcrição em Lote com Envio de Email

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

1. **Variável de Ambiente**: Adicione ao arquivo `.env`:
```
APP_SENHA_GOOGLE=seu_app_password_aqui
```

2. **Como gerar a Senha do App no Gmail:**
   - Ative a autenticação de 2 fatores na sua conta Google
   - Acesse [Google App Passwords](https://myaccount.google.com/apppasswords)
   - Selecione "Mail" e "Windows Computer"
   - Copie a senha gerada e adicione ao `.env`

#### Endpoints Existentes:



Antes de começar, você precisará ter os seguintes itens instalados:

- Python 3.7 ou superior
- pip (gerenciador de pacotes do Python)

## Instalação

1. Clone o repositório:
   ```bash
   git clone <URL_DO_REPOSITORIO>
   cd whisper-api
   ```

2. Crie um ambiente virtual:
   ```bash
   python -m venv venv
   ```

3. Ative o ambiente virtual:
   ```bash
   source venv/bin/activate.fish  # Para fish shell
   ```

4. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```

## Instalação do Uvicorn

Para rodar a API com Uvicorn, você precisa instalá-lo. Siga os passos abaixo:

1. **Instale o Uvicorn:**
   ```bash
   pip install uvicorn
   ```

2. **Execute o servidor da API com Uvicorn:**
   ```bash
   uvicorn main:app --reload
   ```
   - `main` é o nome do arquivo Python (sem a extensão) onde a aplicação FastAPI está definida.
   - `app` é o nome da instância da aplicação FastAPI.
   - `--reload` permite que o servidor reinicie automaticamente ao fazer alterações no código.

3. **Acesse a API** em seu navegador ou ferramenta de teste de API (como Postman) no seguinte endereço:
   ```plaintext
   http://localhost:8000
   ```

## Uso da API

Para rodar a API, siga os passos abaixo:

1. **Ative o ambiente virtual** (se ainda não estiver ativado):
   ```bash
   source venv/bin/activate.fish  # Para fish shell
   ```

2. **Execute o servidor da API:**
   ```bash
   python main.py
   ```

3. **Acesse a API** em seu navegador ou ferramenta de teste de API (como Postman) no seguinte endereço:
   ```plaintext
   http://localhost:5000
   ```

4. **Faça requisições** para os endpoints disponíveis conforme a documentação do projeto.

## Contribuição

Sinta-se à vontade para contribuir com melhorias ou correções. Abra um pull request ou crie uma issue para discutir mudanças.

## Licença

Este projeto está licenciado sob a MIT License. Veja o arquivo LICENSE para mais detalhes.