# 📝 Gerador de Provas IA (Versão CLI / Docker)

Um motor avançado em linha de comando que lê materiais de estudo (PDFs, Docs, TXT, Markdown) e utiliza a inteligência artificial da **Groq API** para gerar provas de múltipla escolha com gabarito comentado. Construído com resiliência, sistema de fallback e foco em processamento em lote.

## ✨ Funcionalidades Principais

* **Alta Disponibilidade (Fallback):** Utiliza uma frota de IAs em cascata. Se o modelo principal (Llama 3.3 70B) atingir limites de tokens ou cota, o sistema engata automaticamente modelos de suporte (Qwen, Llama 3.1 8B).
* **Gestão Inteligente de Contexto:** Fatiamento (chunking) matemático do texto baseado na cota do plano gratuito (Free Tier) e controle de TPM (Tokens Per Minute).
* **Leitura Multi-Formato:** Extrai texto nativamente de `.txt`, `.md`, `.pdf` e `.docx`.
* **Corte por Tópico:** Capacidade de parar a leitura do material ao encontrar um título específico (ex: ignorar referências bibliográficas).
* **Memória de Histórico:** Salva os títulos das questões geradas em um `quiz_history.json` para evitar que a IA repita a mesma pergunta em lotes futuros.
* **Pronto para Nuvem:** Estruturado com `Dockerfile` e `docker-compose.yml` para rodar isolado em qualquer máquina sem sujar o sistema operacional.

## 🛠️ Pré-requisitos

* [Docker](https://docs.docker.com/get-docker/) e [Docker Compose](https://docs.docker.com/compose/install/) instalados.
* Uma chave de API da Groq (Obtenha em: https://console.groq.com/keys).

## 🚀 Como Configurar e Rodar

### 1. Configuração do Ambiente
Clone este repositório e crie um arquivo `.env` na raiz da pasta com a sua chave da Groq:
```env
GROQ_API_KEY=gsk_sua_chave_aqui
```

### 2. Rodando com Docker Compose (Recomendado)
A forma mais fácil de executar é utilizando o Docker Compose. Coloque os materiais que você deseja transformar em prova dentro de uma pasta (ex: `./dados/entrada`) e mapeie os volumes no seu `docker-compose.yml`.

Para iniciar o contêiner e gerar a prova, execute:
```bash
docker-compose up --build
```
*O sistema montará a imagem, instalará as dependências via `uv` (conforme o `pyproject.toml`) e executará o `processor.py`.*

### 3. Rodando Localmente (Sem Docker)
Caso prefira rodar diretamente no seu terminal (requer Python 3.10+):

```bash
# Instale as dependências usando uv ou pip
uv pip install -r requirements.txt

# Execute o processador passando os parâmetros
python processor.py -p ./caminho/do/material -o ./caminho/de/saida -n minha_prova -t "Conclusão"
```

## ⚙️ Parâmetros do CLI (`processor.py`)

O script aceita os seguintes argumentos:

| Argumento | Comando Longo | Descrição | Obrigatório |
| :--- | :--- | :--- | :---: |
| `-p` | `--path` | Caminho do arquivo ou da pasta com os materiais base. | **Sim** |
| `-o` | `--output` | Pasta onde o arquivo `.md` e o histórico serão salvos. | **Sim** |
| `-n` | `--name` | Nome do arquivo de saída (padrão: `simulado_gerado`). | Não |
| `-t` | `--topic_stop`| Palavra ou título exato onde a leitura do documento deve parar. | Não |

## 📁 Estrutura de Arquivos
* `processor.py`: Motor principal de extração e geração.
* `Dockerfile` / `docker-compose.yml`: Orquestração de contêineres.
* `pyproject.toml` / `uv.lock`: Gerenciamento moderno e ultra-rápido de dependências com o Astral UV.
* `prompts/master_quiz.txt`: Template do prompt injetado na IA.
