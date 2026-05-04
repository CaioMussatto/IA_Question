# 📝 Gerador de Provas IA (Web)

Uma aplicação web robusta construída com **Streamlit** e inteligência artificial (**Groq API**) que lê seus materiais de estudo e gera provas completas de múltipla escolha com gabarito comentado.

## ✨ Funcionalidades

* **Leitura Multi-formato:** Suporta envio de arquivos `.txt`, `.md`, `.pdf` e `.docx`.
* **Motor Anti-Bloqueio (Chunking):** Fatiamento inteligente do texto com intervalos de tempo para contornar limites de *Rate Limit* de APIs gratuitas.
* **Frota de IA com Fallback:** Utiliza um sistema de cascata. Se o modelo principal (ex: Llama 3.3 70B) atingir o limite de tokens, o sistema engata automaticamente modelos secundários (Qwen, Llama 3.1 8B) sem interromper a geração.
* **Filtro Anti-Alucinação:** Expressões Regulares (Regex) nativas em Python que limpam "pensamentos" da IA (tags `<think>`) e evitam vazamento do prompt original no documento final.
* **Exportação Profissional:** Baixe a prova gerada instantaneamente em **Markdown (.md)** ou **PDF (.pdf)** perfeitamente formatado usando `xhtml2pdf`.
* **Memória de Sessão:** A interface preserva os resultados gerados mesmo após o usuário clicar nos botões de download.

## 🚀 Como Executar Localmente

### Pré-requisitos
* Python 3.10 ou superior.
* Recomendado usar o [uv](https://github.com/astral-sh/uv) ou `pip` para gerenciar pacotes.

### Passo a Passo

1. **Clone o repositório e acesse a pasta:**
   ```bash
   git clone https://github.com/CaioMussatto/IA_Question.git
   cd ia_question
   ```

2. **Instale as dependências:**
   ```bash
   uv pip install -r requirements.txt
   # ou
   pip install -r requirements.txt
   ```
   *(Certifique-se de que `streamlit`, `openai`, `python-dotenv`, `pymupdf`, `python-docx`, `markdown` e `xhtml2pdf` estão instalados).*

3. **Configuração da API:**
   * Crie um arquivo chamado `.env` na raiz do projeto.
   * Adicione sua chave da Groq:
     ```env
     GROQ_API_KEY=gsk_sua_chave_aqui
     ```
   * *Nota: Você também pode colar a chave diretamente na interface web ao rodar o app.*

4. **Inicie a aplicação:**
   ```bash
   streamlit run app.py
   ```

## 🛠️ Arquitetura do Projeto
* `app.py`: Frontend em Streamlit (Interface, layout, botões e gerenciamento de estado).
* `web_processor.py`: Backend (Extração de texto, comunicação com a Groq API, sistema de fallback, filtros regex e gerador de PDF).
* `prompts/master_quiz.txt`: Template do prompt mestre que dita as regras e o perfil do examinador para a IA.
