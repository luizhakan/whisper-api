# Whisper API

Este projeto é uma implementação da API Whisper, que permite a transcrição de áudio em texto.

## Pré-requisitos

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