import streamlit as st
import os
import shutil
import zipfile
import re
import base64
from pypdf import PdfReader, PdfWriter
import pdf2image
import pytesseract

# --- CONFIGURAÇÃO DA PÁGINA (WIDE MODE) ---
st.set_page_config(page_title="Nexus OS | OCR Avançado", page_icon="⚡", layout="wide")

# --- CUSTOM CSS PARA VISUAL TECNOLÓGICO ---
st.markdown("""
    <style>
    .main-header { font-size: 2.5rem; font-weight: 700; color: #1E88E5; margin-bottom: 0px; }
    .sub-header { font-size: 1.1rem; color: #B0BEC5; margin-bottom: 2rem; }
    .stProgress .st-bo { background-color: #1E88E5; }
    </style>
""", unsafe_allow_html=True)

# --- FUNÇÕES DE REGRA DE NEGÓCIO ---
@st.cache_data
def get_regex():
    regex_ordem = re.compile(r'(?:ordem|os|o\s*s|o\s*n)[\s:#№]*([0-9]{9})', re.IGNORECASE)
    regex_fim = re.compile(r'fim\s+d[eo]\s+relat[óoa]rio', re.IGNORECASE)
    return regex_ordem, regex_fim

def exibir_pdf(file_path):
    """Função para injetar o PDF diretamente na interface web"""
    with open(file_path, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    pdf_display = f'<iframe src="data:application/pdf;base64,{base64_pdf}" width="100%" height="600" type="application/pdf" style="border-radius: 8px; border: 1px solid #555;"></iframe>'
    st.markdown(pdf_display, unsafe_allow_html=True)

# --- CABEÇALHO ---
st.markdown('<p class="main-header">⚡ Nexus OS : Motor OCR Inteligente</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Plataforma de processamento de documentos com Inteligência Artificial. Faça o upload, audite os resultados em tempo real e exporte o lote.</p>', unsafe_allow_html=True)

# Inicializar variáveis de sessão para guardar o estado após o processamento
if 'processado' not in st.session_state:
    st.session_state.processado = False
if 'ordens_geradas' not in st.session_state:
    st.session_state.ordens_geradas = []

# --- LAYOUT PRINCIPAL (2 COLUNAS) ---
col1, col2 = st.columns([1, 2], gap="large")

with col1:
    st.subheader("📥 1. Entrada de Dados")
    arquivo_carregado = st.file_uploader("Arraste o PDF gigante aqui", type=["pdf"])
    
    if arquivo_carregado is not None:
        if st.button("🚀 Iniciar Processamento Tecnológico", type="primary", use_container_width=True):
            
            # Resetar estado
            st.session_state.processado = False
            st.session_state.ordens_geradas = []
            
            # Prepara diretórios
            INPUT_DIR, OUTPUT_DIR, ZIP_PATH = "temp_input", "temp_output", "Ordens_Separadas.zip"
            os.makedirs(INPUT_DIR, exist_ok=True)
            if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
            os.makedirs(OUTPUT_DIR, exist_ok=True)
            
            input_pdf_path = os.path.join(INPUT_DIR, arquivo_carregado.name)
            with open(input_pdf_path, "wb") as f: f.write(arquivo_carregado.getbuffer())
                
            reader = PdfReader(input_pdf_path)
            total_pages = len(reader.pages)
            
            # Interface de Progresso
            st.markdown("### ⚙️ Monitor de Processamento")
            metrica_paginas, metrica_os = st.columns(2)
            met_pag = metrica_paginas.metric(label="Páginas Lidas", value="0")
            met_os = metrica_os.metric(label="OS Identificadas", value="0")
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            current_os_number = None
            current_writer = None
            regex_ordem, regex_fim = get_regex()
            arquivos_os = set() # Para guardar os nomes únicos

            # Motor
            for page_num in range(total_pages):
                status_text.text(f"A analisar estrutura da página {page_num + 1}/{total_pages}...")
                imagens = pdf2image.convert_from_path(input_pdf_path, dpi=150, first_page=page_num + 1, last_page=page_num + 1)
                
                if not imagens: continue
                    
                texto_ocr = pytesseract.image_to_string(imagens[0], lang='por')
                match_ordem = regex_ordem.search(texto_ocr)
                nova_os = match_ordem.group(1) if match_ordem else None
                fim_relatorio = bool(regex_fim.search(texto_ocr))
                
                if nova_os:
                    if current_writer and current_os_number:
                        with open(os.path.join(OUTPUT_DIR, f"{current_os_number}.pdf"), "wb") as f_out: current_writer.write(f_out)
                        arquivos_os.add(f"{current_os_number}.pdf")
                    current_os_number, current_writer = nova_os, PdfWriter()
                    current_writer.add_page(reader.pages[page_num])
                    
                elif current_os_number and current_writer:
                    current_writer.add_page(reader.pages[page_num])
                    
                if fim_relatorio and current_writer and current_os_number:
                    with open(os.path.join(OUTPUT_DIR, f"{current_os_number}.pdf"), "wb") as f_out: current_writer.write(f_out)
                    arquivos_os.add(f"{current_os_number}.pdf")
                    current_os_number, current_writer = None, None
                    
                # Atualizar Métricas Visuais
                progress_bar.progress((page_num + 1) / total_pages)
                met_pag.metric(label="Páginas Lidas", value=f"{page_num + 1}/{total_pages}")
                met_os.metric(label="OS Identificadas", value=str(len(arquivos_os)))

            if current_writer and current_os_number:
                with open(os.path.join(OUTPUT_DIR, f"{current_os_number}.pdf"), "wb") as f_out: current_writer.write(f_out)
                arquivos_os.add(f"{current_os_number}.pdf")

            status_text.text("📦 A compilar ficheiro mestre (ZIP)...")
            with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, arquivos in os.walk(OUTPUT_DIR):
                    for arquivo in arquivos:
                        if arquivo.endswith('.pdf'): zipf.write(os.path.join(root, arquivo), arcname=arquivo)
            
            status_text.empty()
            st.success("✅ Processamento concluído com sucesso!")
            
            # Guardar em sessão para manter visível
            st.session_state.processado = True
            st.session_state.ordens_geradas = sorted(list(arquivos_os))

with col2:
    st.subheader("👁️ 2. Auditoria e Validação")
    
    if not st.session_state.processado:
        st.info("👈 Faça o upload de um ficheiro e inicie o processamento para visualizar os resultados aqui.")
    else:
        st.success(f"Foram extraídas {len(st.session_state.ordens_geradas)} Ordens de Serviço.")
        
        # Área de Download
        with open("Ordens_Separadas.zip", "rb") as fp:
            st.download_button(
                label="📦 DESCARREGAR LOTE COMPLETO (ZIP)",
                data=fp,
                file_name="Ordens_Separadas.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True
            )
            
        st.divider()
        
        # Área de Preview Dinâmico
        st.markdown("### 🔎 Pré-visualização de Documentos")
        os_selecionada = st.selectbox("Selecione uma Ordem de Serviço para auditar:", st.session_state.ordens_geradas)
        
        if os_selecionada:
            caminho_pdf_gerado = os.path.join("temp_output", os_selecionada)
            if os.path.exists(caminho_pdf_gerado):
                exibir_pdf(caminho_pdf_gerado)
            else:
                st.error("Erro ao carregar pré-visualização.")
