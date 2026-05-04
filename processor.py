import os
import argparse
import json
import time
import re
from pathlib import Path
from dotenv import load_dotenv

import fitz  # PyMuPDF
from docx import Document
from openai import OpenAI

load_dotenv()

HISTORY_FILE_NAME = "quiz_history.json"

# --- HIERARQUIA DE MODELOS E LIMITES ---
# O Limite TPM da Groq no Free Tier é 6000 tokens (Soma de Envio + Resposta).
# Com max_tokens=2000 para a resposta, nos sobram ~4000 tokens para o envio.
# 8000 caracteres dão aproximadamente 2000 tokens, deixando uma margem de segurança GIGANTE.
MODELS_CONFIG = [
    {"name": "llama-3.3-70b-versatile", "safe_limit": 8000, "label": "TOP 1 (Gênio)"},
    {"name": "qwen/qwen3-32b", "safe_limit": 8000, "label": "TOP 2 (Especialista)"},
    {"name": "llama-3.1-8b-instant", "safe_limit": 8000, "label": "TOP 3 (Veloz)"}
]

def print_log(step, msg, alert=False):
    prefix = "[!]" if alert else "[*]"
    print(f"{prefix} {step.upper()}: {msg}", flush=True)

def extract_text(input_path, stop_heading=None):
    combined_text = ""
    path = Path(input_path)
    
    if path.is_file():
        files = [path]
    else:
        files = sorted([f for f in path.glob('**/*.*') if f.suffix in ['.md', '.txt', '.pdf', '.docx']])
    
    for file in files:
        try:
            content = ""
            if file.suffix in ['.md', '.txt']:
                with open(file, 'r', encoding='utf-8') as f: content = f.read()
            elif file.suffix == '.pdf':
                with fitz.open(file) as doc:
                    for page in doc: content += page.get_text() + "\n"
            elif file.suffix == '.docx':
                doc = Document(file)
                content = "\n".join([para.text for para in doc.paragraphs])
            
            combined_text += f"\n--- ORIGEM: {file.name} ---\n{content}\n"
        except Exception as e:
            print_log("erro leitura", f"Falha ao ler {file.name}: {e}", True)
            continue

    if stop_heading:
        match = re.search(re.escape(stop_heading), combined_text, re.IGNORECASE)
        if match:
            combined_text = combined_text[:match.start()]
            print_log("corte", f"Texto cortado com sucesso no título '{stop_heading}'.")

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
            
    if current_chunk.strip():
        chunks.append(current_chunk)
        
    return chunks

def call_ia_with_fallback(client, context_full, template, history_list, start_num, end_num, lote_atual, total_lotes):
    """Lida com fallback e calcula matematicamente o bloco correto com base no progresso."""
    
    for model_idx in range(len(MODELS_CONFIG)):
        config = MODELS_CONFIG[model_idx]
        model_name = config["name"]
        
        # 1. Quebra o texto com base no limite seguro
        chunks = chunk_text(context_full, config["safe_limit"])
        
        # 2. Descobre qual bloco usar baseado no progresso
        progresso = lote_atual / total_lotes
        chunk_idx = int(progresso * len(chunks))
        
        if chunk_idx >= len(chunks):
            chunk_idx = len(chunks) - 1
            
        current_context = chunks[chunk_idx]
        
        forbidden = "\n- ".join(history_list) if history_list else "Nenhum."
        
        prompt = template.replace("{{CONTEXTO_NOTAS}}", current_context)
        prompt = prompt.replace("{{START_NUM}}", f"{start_num:02d}")
        prompt = prompt.replace("{{END_NUM}}", f"{end_num:02d}")
        prompt = prompt.replace("{{HISTORICO}}", forbidden)

        print_log("modelo", f"Tentando {config['label']} ({model_name}) | Texto em {len(chunks)} partes. Lendo parte {chunk_idx+1}.")
        
        try:
            response = client.chat.completions.with_raw_response.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "Você é um examinador PhD. Siga rigorosamente a formatação com a tag [GABARITO]."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.35,
                max_tokens=2000 # <-- CORREÇÃO PRINCIPAL: Reduzido para caber nos 6000 do Free Tier Groq
            )
            
            headers = response.headers
            rem = headers.get('x-ratelimit-remaining-tokens', 'N/A')
            print_log("telemetria", f"Tokens TPM Restantes: {rem}")

            if rem != 'N/A' and int(rem) < 1000:
                print_log("alerta", "Cota TPM quase zerada neste modelo. Próxima requisição pode acionar rate limit.", True)

            parsed_response = response.parse()
            return parsed_response.choices[0].message.content, model_idx

        except Exception as e:
            err_str = str(e).lower()
            print_log("diagnóstico", f"Motivo da falha ({model_name}): {str(e)}", True)
            
            if any(x in err_str for x in ["429", "rate limit", "rate_limit", "413", "insufficient_quota", "400", "model_decommissioned"]):
                print_log("fallback", f"Engatando próximo modelo da frota...", True)
                continue 
            else:
                raise e
    
    raise Exception("Falha Crítica: Todos os modelos da frota falharam (provavelmente Cota Diária Global ou Limite TPM).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--path", required=True)
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("-n", "--name", default="simulado_gerado")
    parser.add_argument("-t", "--topic_stop", default=None)
    args = parser.parse_args()

    print_log("início", "Iniciando processador de provas (Alta Disponibilidade).")
    
    content = extract_text(args.path, args.topic_stop)
    
    if not content.strip():
        print_log("erro", "Nenhum conteúdo extraído.", True)
        exit(1)

    print_log("processamento", f"Total de caracteres extraídos: {len(content)}")

    client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=os.getenv("GROQ_API_KEY"))
    
    with open("/app/prompts/master_quiz.txt", 'r', encoding='utf-8') as f:
        template = f.read()

    out_dir = Path(args.output)
    history = [] 
    all_questions = []
    all_gabs = []
    q_num = 1
    total_lotes = 10
    
    for lote_atual in range(total_lotes):
        print_log("lote", f"Processando Lote {lote_atual+1}/{total_lotes} (Questões {q_num:02d} e {q_num+1:02d})")
        
        try:
            res_text, used_idx = call_ia_with_fallback(client, content, template, history, q_num, q_num+1, lote_atual, total_lotes)
            
            if "[GABARITO]" in res_text:
                parts = res_text.split("[GABARITO]")
                all_questions.append(parts[0].strip())
                all_gabs.append(parts[1].strip())
                
                titles = re.findall(r"Questão\s*\d+:\s*(.*)", parts[0], re.IGNORECASE)
                history.extend(titles)
            else:
                print_log("aviso", "Tag [GABARITO] falhou. Inserindo texto cru no documento.", True)
                all_questions.append(res_text)
            
            q_num += 2
            
            # Pausa de 3.5s para esfriar o TPM rate-limit da Groq entre requisições
            time.sleep(3.5) 
            
        except Exception as e:
            print_log("erro fatal", f"Parada crítica no sistema: {e}", True)
            break

    if all_questions:
        print_log("montagem", "Compilando arquivo Markdown final...")
        final_markdown = "## 📝 Exame Técnico Avançado\n\n"
        final_markdown += "\n\n".join(all_questions)
        final_markdown += "\n\n---\n## 🔑 GABARITO COMENTADO E ANALÍTICO\n\n"
        final_markdown += "\n\n".join(all_gabs)

        out_dir.mkdir(parents=True, exist_ok=True)
        filename = args.name if args.name.endswith(".md") else f"{args.name}.md"
        
        with open(out_dir / filename, "w", encoding="utf-8") as f:
            f.write(final_markdown)
        
        with open(out_dir / HISTORY_FILE_NAME, 'w', encoding='utf-8') as f:
            json.dump(list(set(history))[-300:], f, ensure_ascii=False, indent=4)
        
        print_log("sucesso", f"Prova impecável salva em: {out_dir / filename}")