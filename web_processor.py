import os
import time
import re
from pathlib import Path
from dotenv import load_dotenv

import fitz  # PyMuPDF
from docx import Document
from openai import OpenAI

import markdown
from xhtml2pdf import pisa
import io

load_dotenv()

MODELS_CONFIG = [
    {"name": "llama-3.3-70b-versatile", "safe_limit": 8000, "label": "TOP 1 (Gênio)"},
    {"name": "qwen/qwen3-32b", "safe_limit": 8000, "label": "TOP 2 (Especialista)"},
    {"name": "llama-3.1-8b-instant", "safe_limit": 8000, "label": "TOP 3 (Veloz)"}
]

def extract_text_from_uploads(uploaded_files, stop_heading=None, log_cb=None):
    combined_text = ""
    for file in uploaded_files:
        try:
            content = ""
            ext = file.name.split('.')[-1].lower()
            
            if ext in ['md', 'txt']:
                content = file.getvalue().decode("utf-8")
            elif ext == 'pdf':
                with fitz.open(stream=file.getvalue(), filetype="pdf") as doc:
                    for page in doc: content += page.get_text() + "\n"
            elif ext == 'docx':
                from io import BytesIO
                doc = Document(BytesIO(file.getvalue()))
                content = "\n".join([para.text for para in doc.paragraphs])
            
            combined_text += f"\n--- ORIGEM: {file.name} ---\n{content}\n"
        except Exception as e:
            if log_cb: log_cb(f"[!] ERRO LEITURA: Falha ao ler {file.name}: {e}")
            continue

    if stop_heading:
        match = re.search(re.escape(stop_heading), combined_text, re.IGNORECASE)
        if match:
            combined_text = combined_text[:match.start()]
            if log_cb: log_cb(f"[*] CORTE: Texto cortado no título '{stop_heading}'.")
        else:
            if log_cb: log_cb(f"[!] AVISO: Título '{stop_heading}' não encontrado. Lendo tudo.")

    return combined_text

def chunk_text(text, max_chars):
    paragraphs = text.split('\n')
    chunks = []
    current_chunk = ""
    for p in paragraphs:
        if len(current_chunk) + len(p) > max_chars:
            chunks.append(current_chunk)
            current_chunk = p + "\n"
        else:
            current_chunk += p + "\n"
    if current_chunk.strip(): chunks.append(current_chunk)
    return chunks

def call_ia_with_fallback(client, context_full, template, history_list, start_num, end_num, lote_atual, total_lotes, log_cb):
    for model_idx in range(len(MODELS_CONFIG)):
        config = MODELS_CONFIG[model_idx]
        model_name = config["name"]
        
        chunks = chunk_text(context_full, config["safe_limit"])
        progresso = lote_atual / total_lotes
        chunk_idx = int(progresso * len(chunks))
        if chunk_idx >= len(chunks): chunk_idx = len(chunks) - 1
            
        current_context = chunks[chunk_idx]
        forbidden = "\n- ".join(history_list) if history_list else "Nenhum."
        
        prompt = template.replace("{{CONTEXTO_NOTAS}}", current_context)
        prompt = prompt.replace("{{START_NUM}}", f"{start_num:02d}")
        prompt = prompt.replace("{{END_NUM}}", f"{end_num:02d}")
        prompt = prompt.replace("{{HISTORICO}}", forbidden)

        log_cb(f"[*] MODELO: Tentando {config['label']} ({model_name}) | Lendo parte {chunk_idx+1} de {len(chunks)}.")
        
        try:
            response = client.chat.completions.with_raw_response.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "Você é um examinador PhD. Siga rigorosamente a formatação com a tag [GABARITO]."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.35,
                max_tokens=2000 
            )
            
            headers = response.headers
            rem = headers.get('x-ratelimit-remaining-tokens', 'N/A')
            log_cb(f"[*] TELEMETRIA: TPM Restantes: {rem}")

            if rem != 'N/A' and int(rem) < 1000:
                log_cb("[!] ALERTA: Cota TPM quase zerada. Risco de fallback na próxima.")

            parsed_response = response.parse()
            raw_text = parsed_response.choices[0].message.content
            
            # Filtro anti-pensamento nativo
            clean_text = re.sub(r'<think>.*?</think>', '', raw_text, flags=re.DOTALL).strip()
            return clean_text, model_idx

        except Exception as e:
            err_str = str(e).lower()
            log_cb(f"[!] DIAGNÓSTICO ({model_name}): {str(e)}")
            
            if any(x in err_str for x in ["429", "rate limit", "rate_limit", "413", "insufficient_quota", "400", "model_decommissioned"]):
                log_cb("[!] FALLBACK: Engatando próximo modelo da frota...")
                continue 
            else:
                raise e
    
    raise Exception("FALHA CRÍTICA: Todos os modelos da frota falharam.")

def clean_ai_hallucinations(text):
    """Escudo definitivo contra vazamentos de prompt e má formatação da IA."""
    
    # 1. Aniquila o vazamento do prompt (apaga tudo a partir de [PERFIL DO EXAMINADOR] ou [TAREFA ATUAL] se a IA cuspir de volta)
    text = re.sub(r'\[PERFIL DO EXAMINADOR\].*', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'\[TAREFA ATUAL\].*', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'\[REGRAS DE COMPLEXIDADE\].*', '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # 2. Desgruda a Alternativa da Análise (Ex: transforma "Alternativa BAnálise Técnica" em "Alternativa B \n\n **Análise Técnica**")
    text = re.sub(r'(Alternativa\s*[A-E][\.\)]?)\s*(Análise Técnica)', r'\1\n\n**\2**', text, flags=re.IGNORECASE)
    
    # 3. Empurra as alternativas A), B), C)... para uma nova linha (Regra anterior mantida)
    text = re.sub(r'(?<!\n)\s+([A-E]\))', r'\n\n\1', text)
    
    # 4. Remove alternativas duplicadas como B) B)
    text = re.sub(r'([A-E]\))\s+\1', r'\1', text)
    
    return text.strip()

def generate_exam(api_key, uploaded_files, stop_heading, template_text, log_cb):
    log_cb("[*] INÍCIO: Extraindo conteúdo dos arquivos...")
    content = extract_text_from_uploads(uploaded_files, stop_heading, log_cb)
    
    if not content.strip():
        log_cb("[!] ERRO: Nenhum conteúdo extraído. Verifique os arquivos.")
        return None, None

    log_cb(f"[*] PROCESSAMENTO: Total de caracteres: {len(content)}")

    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=api_key)
    
    history = [] 
    all_questions = []
    all_gabs = []
    q_num = 1
    total_lotes = 10
    
    for lote_atual in range(total_lotes):
        log_cb(f"\n--- Processando Lote {lote_atual+1}/{total_lotes} (Questões {q_num:02d} e {q_num+1:02d}) ---")
        try:
            res_text, used_idx = call_ia_with_fallback(client, content, template_text, history, q_num, q_num+1, lote_atual, total_lotes, log_cb)
            
            # Passa o pente fino IMEDIATAMENTE após a resposta da IA
            res_text = clean_ai_hallucinations(res_text)
            
            if "[GABARITO]" in res_text:
                parts = res_text.split("[GABARITO]")
                all_questions.append(parts[0].strip())
                all_gabs.append(parts[1].strip())
                
                titles = re.findall(r"Questão\s*\d+:\s*(.*)", parts[0], re.IGNORECASE)
                history.extend(titles)
            else:
                log_cb("[!] AVISO: Tag [GABARITO] falhou. Inserindo texto cru.")
                all_questions.append(res_text)
            
            q_num += 2
            time.sleep(3.5) 
            
        except Exception as e:
            log_cb(f"[!] ERRO FATAL: {e}")
            break

    if not all_questions:
        return None, None

    log_cb("[*] MONTAGEM: Compilando arquivo Markdown final...")
    final_markdown = "## Exame Tecnico Avancado\n\n"
    final_markdown += "\n\n".join(all_questions)
    final_markdown += "\n\n---\n## GABARITO COMENTADO E ANALITICO\n\n"
    final_markdown += "\n\n".join(all_gabs)
    
    # Uma última limpeza por precaução
    final_markdown = clean_ai_hallucinations(final_markdown)

    try:
        log_cb("[*] PDF: Convertendo estrutura e gerando arquivo final...")
        html_body = markdown.markdown(final_markdown, extensions=['tables'])
        
        html_content = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                @page {{ margin: 2cm; }}
                body {{ font-family: Helvetica, Arial, sans-serif; font-size: 12pt; line-height: 1.6; }}
                h2 {{ color: #2c3e50; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; }}
                h3 {{ color: #34495e; }}
                p {{ margin-bottom: 10px; text-align: justify; }}
            </style>
        </head>
        <body>
            {html_body}
        </body>
        </html>
        """
        
        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.BytesIO(html_content.encode('utf-8')), dest=pdf_buffer, encoding='utf-8')
        
        if not pisa_status.err:
            pdf_bytes = pdf_buffer.getvalue()
            log_cb("[*] SUCESSO: Arquivo PDF gerado perfeitamente.")
        else:
            log_cb("[!] ERRO PDF: Falha interna no motor de conversão (xhtml2pdf).")
            pdf_bytes = None
            
    except Exception as e:
        log_cb(f"[!] ERRO PDF: Exceção ao gerar o PDF ({e}). Retornando apenas Markdown.")
        pdf_bytes = None

    log_cb("[*] FIM: Sistema finalizado com sucesso!")
    return final_markdown, pdf_bytes