import streamlit as st
import os
import shutil
import zipfile
import re
import time
from pypdf import PdfReader, PdfWriter
import pdf2image
import pytesseract

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Nexus OS | OCR Avançado", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")

# --- CUSTOM CSS COM ANIMAÇÕES ---
st.markdown("""
    <style>
    @keyframes neonGlow {
        0% { text-shadow: 0 0 5px #00e676, 0 0 10px #00e676; }
        50% { text-shadow: 0 0 20px #00e676, 0 0 35px #00e676; }
        100% { text-shadow: 0 0 5px #00e676, 0 0 10px #00e676; }
    }
    .main-banner {
        font-size: 2.3rem;
        font-weight: 900;
        color: #00e676;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        animation: neonGlow 2s infinite ease-in-out;
        margin-bottom: 0.3rem;
    }
    .sub-banner {
        font-size: 1.15rem;
        color: #90caf9;
        font-weight: 500;
        margin-bottom: 1.8rem;
    }
    @keyframes fadeOutMeme {
        0% { opacity: 1; transform: scale(1); }
        60% { opacity: 1; transform: scale(1); }
        100% { opacity: 0; transform: scale(0.95); display: none; }
    }
    .meme-popup {
        display: flex;
        justify-content: center;
        align-items: center;
        margin-bottom: 1.5rem;
        animation: fadeOutMeme 5s forwards;
    }
    .meme-popup img {
        max-width: 340px;
        border-radius: 12px;
        box-shadow: 0 0 25px rgba(0, 230, 118, 0.45);
        border: 2px solid #00e676;
    }
    [data-testid="stSidebar"] { display: none; }
    </style>
""", unsafe_allow_html=True)

# Link direto para a imagem do meme
URL_MEME = "https://i.imgflip.com/1m9k2x.jpg"

# --- REGEX OCR ---
@st.cache_data
def get_regex():
    regex_ordem = re.compile(r'(?:ordem|os|o\s*s|o\s*n)[\s:#№]*([0-9]{9})', re.IGNORECASE)
    regex_fim = re.compile(r'fim\s+d[eo]\s+relat[óoa]rio', re.IGNORECASE)
    return regex_ordem, regex_fim

# --- ESPAÇO PARA O MEME NO TOPO ---
espaco_meme = st.empty()

# --- CABEÇALHO ---
st.markdown('<div class="main-banner">🔥 Bora Randy, tem que escanear todas as ordens!</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-banner">Carregue o arquivo consolidado para separar e empacotar todos os documentos automaticamente.</div>', unsafe_allow_html=True)

# --- ÁREA DE UPLOAD ---
arquivo_carregado = st.file_uploader("📂 Arraste o arquivo PDF único aqui:", type=["pdf"])

if arquivo_carregado is not None:
    if st.button("🚀 INICIAR ESCANEAMENTO COMPLETO", type="primary", use_container_width=True):
        INPUT_DIR, OUTPUT_DIR, ZIP_PATH = "temp_input", "temp_output", "Ordens_Separadas.zip"
        os.makedirs(INPUT_DIR, exist_ok=True)
        if os.path.exists(OUTPUT_DIR): 
            shutil.rmtree(OUTPUT_DIR)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        input_pdf_path = os.path.join(INPUT_DIR, arquivo_carregado.name)
        with open(input_pdf_path, "wb") as f: 
            f.write(arquivo_carregado.getbuffer())
            
        reader = PdfReader(input_pdf_path)
        total_pages = len(reader.pages)
        
        # Painel de métricas
        st.markdown("### ⚙️ Monitor de Processamento")
        col_m1, col_m2 = st.columns(2)
        met_pag = col_m1.metric("Páginas Processadas", f"0 / {total_pages}")
        met_os = col_m2.metric("Ordens Extraídas", "0")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        current_os_number = None
        current_writer = None
        regex_ordem, regex_fim = get_regex()
        total_os_encontradas = 0

        # Loop de processamento OCR
        for page_num in range(total_pages):
            status_text.text(f"⚡ Escaneando página {page_num + 1} de {total_pages}...")
            imagens = pdf2image.convert_from_path(input_pdf_path, dpi=150, first_page=page_num + 1, last_page=page_num + 1)
            
            if not imagens: 
                continue
                
            texto_ocr = pytesseract.image_to_string(imagens[0], lang='por')
            match_ordem = regex_ordem.search(texto_ocr)
            nova_os = match_ordem.group(1) if match_ordem else None
            fim_relatorio = bool(regex_fim.search(texto_ocr))
            
            if nova_os:
                if current_writer and current_os_number:
                    with open(os.path.join(OUTPUT_DIR, f"{current_os_number}.pdf"), "wb") as f_out: 
                        current_writer.write(f_out)
                current_os_number, current_writer = nova_os, PdfWriter()
                current_writer.add_page(reader.pages[page_num])
                total_os_encontradas += 1
                
            elif current_os_number and current_writer:
                current_writer.add_page(reader.pages[page_num])
                
            if fim_relatorio and current_writer and current_os_number:
                with open(os.path.join(OUTPUT_DIR, f"{current_os_number}.pdf"), "wb") as f_out: 
                    current_writer.write(f_out)
                current_os_number, current_writer = None, None
                
            progress_bar.progress((page_num + 1) / total_pages)
            met_pag.metric("Páginas Processadas", f"{page_num + 1} / {total_pages}")
            met_os.metric("Ordens Extraídas", str(total_os_encontradas))

        if current_writer and current_os_number:
            with open(os.path.join(OUTPUT_DIR, f"{current_os_number}.pdf"), "wb") as f_out: 
                current_writer.write(f_out)

        status_text.text("📦 Compactando arquivos em lote...")
        with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, arquivos in os.walk(OUTPUT_DIR):
                for arquivo in arquivos:
                    if arquivo.endswith('.pdf'): 
                        zipf.write(os.path.join(root, arquivo), arcname=arquivo)
        
        status_text.empty()
        
        # Exibe o meme animado que se esvai suavemente durante 5 segundos
        espaco_meme.markdown(f'''
            <div class="meme-popup">
                <img src="{URL_MEME}" alt="Muito Bem! Mandou bem demais!">
            </div>
        ''', unsafe_allow_html=True)
        
        st.balloons()
        st.success(f"🎯 Concluído! Todas as {total_os_encontradas} ordens foram escaneadas e separadas com sucesso!")
        
        # Botão de download central
        with open(ZIP_PATH, "rb") as fp:
            st.download_button(
                label="⬇️ BAIXAR TODAS AS ORDENS EM ZIP",
                data=fp,
                file_name="Ordens_Separadas.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True
            )
            
        # Limpa o placeholder no backend após a transição visual
        time.sleep(5)
        espaco_meme.empty()
