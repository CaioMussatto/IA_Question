import streamlit as st
import os
from dotenv import load_dotenv
from web_processor import generate_exam

st.set_page_config(page_title="Gerador de Provas IA", page_icon="📝", layout="wide")

# --- INICIALIZAÇÃO DA MEMÓRIA (SESSION STATE) ---
if 'md_result' not in st.session_state:
    st.session_state.md_result = None
if 'pdf_bytes' not in st.session_state:
    st.session_state.pdf_bytes = None
if 'log_texto' not in st.session_state:
    st.session_state.log_texto = ""

st.title("📝 Gerador de Exames Avançado (Groq API)")

# --- MENSAGEM DE INSTRUÇÕES (NO TOPO) ---
with st.expander("📖 Como funciona e como obter sua API Key (LEIA ANTES DE COMEÇAR)", expanded=True):
    st.markdown("""
    **Por que criamos este sistema?**<br>
    Para evitar custos altíssimos de inteligência artificial, utilizamos o plano gratuito da Groq. 
    
    O único detalhe de ferramentas gratuitas é que elas possuem um limite de leitura por minuto. Para contornar isso, o aplicativo foi desenhado para fatiar o seu material e ler em pequenos lotes, aguardando um curto intervalo de tempo entre cada questão para não ser bloqueado. 
    
    A melhor forma de se utilizar essa aplicação é criar cada prova com um certo periodo de tempo, com a preferencia de um bom tempo entre cada geração.
    
    **Como conseguir sua Chave da API (GROQ_API_KEY):**
    1. Acesse https://console.groq.com/keys.
    2. Crie uma conta ou faça login.
    3. Clique no botão "Create API Key".
    4. Dê um nome para a chave (ex: GeradorProvas) e clique em salvar.
    5. Copie a chave (ela começa com `gsk_`) e cole no campo abaixo ou salve no seu arquivo `.env`. 
    6. Não perca, pois ela só aparece uma vez!
    7. NÃO Compartilhe ela com ninguém.
    """, unsafe_allow_html=True)

st.markdown("---")

col_esq, col_dir = st.columns([1, 1.5])

with col_esq:
    st.header("⚙️ Configurações")
    
    st.subheader("1. Credenciais da API")
    api_key_input = st.text_input("Cole sua GROQ_API_KEY aqui:", type="password", help="Se deixado em branco, tentaremos carregar do arquivo .env")
    env_file = st.file_uploader("Ou envie seu arquivo .env", type=["env"])
    
    final_api_key = api_key_input
    if env_file and not final_api_key:
        content = env_file.getvalue().decode("utf-8")
        for line in content.split("\n"):
            if line.startswith("GROQ_API_KEY="):
                final_api_key = line.split("=")[1].strip()
    if not final_api_key:
        load_dotenv()
        final_api_key = os.getenv("GROQ_API_KEY")

    st.subheader("2. Material Base")
    uploaded_files = st.file_uploader(
        "Envie até 3 arquivos (.txt, .md, .pdf, .docx)", 
        type=['txt', 'md', 'pdf', 'docx'], 
        accept_multiple_files=True
    )
    
    if len(uploaded_files) > 3:
        st.error("Por favor, envie no máximo 3 arquivos.")

    st.subheader("3. Tópico de Corte")
    stop_topic = st.text_input(
        "Até qual título ler? (Opcional)", 
        disabled=len(uploaded_files) > 1, 
        help="Só funciona se houver apenas 1 arquivo enviado."
    )
    
    st.markdown("---")
    start_button = st.button("🚀 Iniciar Geração da Prova", use_container_width=True, type="primary")

with col_dir:
    st.header("📊 Resultados e Execução")
    
    resultado_container = st.container()
    terminal_container = st.container()
    
    with terminal_container:
        st.markdown("#### Terminal de Logs")
        log_caixa = st.empty()

    def ui_log(mensagem):
        st.session_state.log_texto += f"{mensagem}\n"
        log_caixa.code(st.session_state.log_texto, language="bash")
    
    # Restaura logs caso a página atualize
    if st.session_state.log_texto:
        log_caixa.code(st.session_state.log_texto, language="bash")
    else:
        log_caixa.code("Aguardando inicialização do sistema...", language="bash")

    if start_button:
        if not final_api_key:
            st.error("GROQ_API_KEY é obrigatória. Digite-a ou envie um arquivo .env.")
        elif not uploaded_files or len(uploaded_files) > 3:
            st.error("Envie entre 1 e 3 arquivos válidos.")
        else:
            # Limpa a memória para uma nova geração
            st.session_state.log_texto = "" 
            st.session_state.md_result = None
            st.session_state.pdf_bytes = None
            
            ui_log("[*] Verificando Prompt Master...")
            
            try:
                with open("prompts/master_quiz.txt", "r", encoding="utf-8") as f:
                    template = f.read()
            except Exception as e:
                st.error("Faltou o arquivo de prompt em: prompts/master_quiz.txt")
                st.stop()
                
            with st.spinner("A frota de IAs está trabalhando... Acompanhe os logs abaixo."):
                topic = stop_topic if len(uploaded_files) == 1 else None
                md, pdf = generate_exam(
                    api_key=final_api_key, 
                    uploaded_files=uploaded_files, 
                    stop_heading=topic, 
                    template_text=template, 
                    log_cb=ui_log
                )
                # Salva o resultado na memória
                st.session_state.md_result = md
                st.session_state.pdf_bytes = pdf
            
            # Força o Streamlit a recarregar a interface imediatamente
            st.rerun()

    # --- ÁREA DA PROVA (DENTRO DO CONTAINER DO TOPO) ---
    # Só renderiza se a prova estiver salva na memória
    if st.session_state.md_result:
        with resultado_container:
            st.success("🎉 Prova gerada com sucesso!")
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                st.download_button(
                    label="📄 Baixar em Markdown",
                    data=st.session_state.md_result,
                    file_name="Prova_Gerada.md",
                    mime="text/markdown",
                    use_container_width=True
                )
            with col_btn2:
                if st.session_state.pdf_bytes:
                    st.download_button(
                        label="📕 Baixar em PDF",
                        data=st.session_state.pdf_bytes,
                        file_name="Prova_Gerada.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                else:
                    st.button("📕 Erro ao Gerar PDF", disabled=True, use_container_width=True)
                    
            with st.expander("👀 Clique aqui para Ver a Prova Gerada", expanded=False):
                st.markdown(st.session_state.md_result)