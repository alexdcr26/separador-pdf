import streamlit as st
import os
import shutil
import zipfile
import re
import time
import pandas as pd
from pypdf import PdfReader, PdfWriter
import pdf2image
import pytesseract

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Nexus OS | OCR Avançado Fogás", 
    page_icon="⚡", 
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- ESTILIZAÇÃO E ANIMAÇÃO ---
st.markdown("""
    <style>
    @keyframes neonGlow {
        0% { text-shadow: 0 0 5px #00e676, 0 0 10px #00e676; }
        50% { text-shadow: 0 0 20px #00e676, 0 0 35px #00e676; }
        100% { text-shadow: 0 0 5px #00e676, 0 0 10px #00e676; }
    }
    .main-banner {
        font-size: 2.2rem;
        font-weight: 900;
        color: #00e676;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        animation: neonGlow 2s infinite ease-in-out;
        margin-bottom: 0.3rem;
    }
    .sub-banner {
        font-size: 1.1rem;
        color: #90caf9;
        font-weight: 500;
        margin-bottom: 1.5rem;
    }
    [data-testid="stSidebar"] { display: none; }
    </style>
""", unsafe_allow_html=True)

# --- REGRAS CRITERIOSAS DE OCR ---
def extrair_numero_os(texto):
    """
    Extrai com alta precisão o número da Ordem Fogás (9 dígitos iniciando com 3).
    Tolera espaços no meio do número (ex: '311053 788' -> '311053788').
    """
    candidatos = re.findall(r'\b(3\d{2}[\s.-]*\d{3}[\s.-]*\d{3})\b', texto)
    for c in candidatos:
        limpo = re.sub(r'\D', '', c)
        if len(limpo) == 9:
            return limpo

    cabecalho = texto[:1600]
    cabecalho_normalizado = re.sub(r'(\d)\s+(\d)', r'\1\2', cabecalho)
    cabecalho_normalizado = re.sub(r'(\d)\s+(\d)', r'\1\2', cabecalho_normalizado)
    
    match_ordem = re.search(r'(?:ordem|os|o\s*s)[\s\S]{0,120}?\b(3\d{8})\b', cabecalho_normalizado, re.IGNORECASE)
    if match_ordem:
        return match_ordem.group(1)

    match_direto = re.search(r'\b(3\d{8})\b', cabecalho_normalizado)
    if match_direto:
        return match_direto.group(1)
        
    return None

def checar_inicio_ordem(texto):
    """
    Detecta se é o início de uma nova ordem de 3 formas:
    1. Lê explicitamente 'Página 1' no cabeçalho.
    2. Encontra o campo 'Solicitante:' (exclusivo da pág 1).
    3. Encontra o campo 'Descrição da Ordem' (exclusivo da pág 1).
    """
    cabecalho = texto[:1200]
    
    tem_pag_1 = bool(re.search(r'p[áa]g(?:ina)?\.?\s*1\b', cabecalho, re.IGNORECASE))
    tem_solicitante = bool(re.search(r'solicitante\s*:', texto, re.IGNORECASE))
    tem_desc_ordem = bool(re.search(r'descri[çc][ãa]o\s+da\s+ordem', texto, re.IGNORECASE))
    
    return tem_pag_1 or tem_solicitante or tem_desc_ordem

# --- CABEÇALHO ---
st.markdown('<div class="main-banner">🔥 Bora Randy, tem que escanear todas as ordens!</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-banner">Motor de separação inteligente com auditoria de páginas e validação anti-mesclagem de OS.</div>', unsafe_allow_html=True)

espaco_meme = st.empty()

# --- UPLOAD ---
arquivo_carregado = st.file_uploader("📂 Arraste o arquivo PDF único aqui:", type=["pdf"])

if arquivo_carregado is not None:
    if st.button("🚀 INICIAR ESCANEAMENTO CRITERIOSO", type="primary", use_container_width=True):
        INPUT_DIR = "temp_input"
        OUTPUT_DIR = "temp_output"
        ZIP_PATH = "Ordens_Separadas.zip"

        os.makedirs(INPUT_DIR, exist_ok=True)
        if os.path.exists(OUTPUT_DIR):
            shutil.rmtree(OUTPUT_DIR)
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        input_pdf_path = os.path.join(INPUT_DIR, arquivo_carregado.name)
        with open(input_pdf_path, "wb") as f:
            f.write(arquivo_carregado.getbuffer())

        reader = PdfReader(input_pdf_path)
        total_pages = len(reader.pages)

        # Controles visuais
        st.markdown("### ⚙️ Monitor em Tempo Real")
        col_m1, col_m2 = st.columns(2)
        met_pag = col_m1.metric("Páginas Processadas", f"0 / {total_pages}")
        met_os = col_m2.metric("Ordens Extraídas", "0")
        
        progress_bar = st.progress(0)
        status_text = st.empty()

        # Estruturas de controle de agrupamento
        current_os_number = None
        current_writer = None
        current_page_count = 0
        lista_ordens = []

        # --- LOOP OCR ---
        for page_num in range(total_pages):
            status_text.text(f"⚡ Analisando página {page_num + 1} de {total_pages}...")
            
            imagens = pdf2image.convert_from_path(
                input_pdf_path, 
                dpi=150, 
                first_page=page_num + 1, 
                last_page=page_num + 1
            )
            
            texto_ocr = pytesseract.image_to_string(imagens[0], lang='por') if imagens else ""

            os_detectada = extrair_numero_os(texto_ocr)
            inicio_confirmado = checar_inicio_ordem(texto_ocr)

            # O sistema corta o documento se encontrar uma nova Página 1 (ou layout de pág 1)
            # ou se o número da OS mudar. "Fim do relatório" é ignorado na separação.
            nova_ordem_iniciou = (
                (os_detectada and os_detectada != current_os_number) or 
                (inicio_confirmado and current_writer is not None)
            )

            if nova_ordem_iniciou:
                if current_writer and current_os_number:
                    caminho_saida = os.path.join(OUTPUT_DIR, f"{current_os_number}.pdf")
                    with open(caminho_saida, "wb") as f_out:
                        current_writer.write(f_out)
                    lista_ordens.append({
                        "Ordem de Serviço (OS)": current_os_number,
                        "Total de Páginas": current_page_count,
                        "Tipo de Ordem": "Página Única" if current_page_count == 1 else "Múltiplas Páginas"
                    })
                # Reseta para iniciar o novo agrupamento
                current_writer = None
                current_os_number = None
                current_page_count = 0

            # Inicializa o agrupador da ordem detectada ou de uma página sem OS aparente
            if current_writer is None:
                current_os_number = os_detectada if os_detectada else f"OS_DESCONHECIDA_{page_num + 1}"
                current_writer = PdfWriter()
                current_page_count = 0

            # Anexa a página atual (Página 1, 2, 3... sempre cairão aqui)
            current_writer.add_page(reader.pages[page_num])
            current_page_count += 1

            # Atualização dos mostradores em tela
            progress_bar.progress((page_num + 1) / total_pages)
            met_pag.metric("Páginas Processadas", f"{page_num + 1} / {total_pages}")
            met_os.metric("Ordens Extraídas", str(len(lista_ordens) + (1 if current_writer else 0)))

        # Salva a última ordem que ficou pendente no agrupador ao final do PDF
        if current_writer and current_os_number:
            caminho_saida = os.path.join(OUTPUT_DIR, f"{current_os_number}.pdf")
            with open(caminho_saida, "wb") as f_out:
                current_writer.write(f_out)
            lista_ordens.append({
                "Ordem de Serviço (OS)": current_os_number,
                "Total de Páginas": current_page_count,
                "Tipo de Ordem": "Página Única" if current_page_count == 1 else "Múltiplas Páginas"
            })

        # Compactação final
        status_text.text("📦 Compactando documentos individuais...")
        with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, arquivos in os.walk(OUTPUT_DIR):
                for arquivo in arquivos:
                    if arquivo.endswith('.pdf'):
                        zipf.write(os.path.join(root, arquivo), arcname=arquivo)

        status_text.empty()

        # Finalização visual
        st.balloons()
        if os.path.exists("meme.jpg"):
            with espaco_meme.container():
                c1, c2, c3 = st.columns([1, 1, 1])
                with c2:
                    st.image("meme.jpg", width=340)
            time.sleep(5)
            espaco_meme.empty()

        st.success(f"🎯 Escaneamento concluído! Total de {len(lista_ordens)} ordens separadas com sucesso.")

        # Download
        with open(ZIP_PATH, "rb") as fp:
            st.download_button(
                label="⬇️ BAIXAR TODAS AS ORDENS EM ZIP",
                data=fp,
                file_name="Ordens_Separadas.zip",
                mime="application/zip",
                type="primary",
                use_container_width=True
            )

        # Auditoria Geral
        st.divider()
        st.subheader("📋 Auditoria Geral das Ordens Separadas")

        if lista_ordens:
            df = pd.DataFrame(lista_ordens)
            total_os = len(df)
            unicas = len(df[df["Total de Páginas"] == 1])
            multiplas = len(df[df["Total de Páginas"] > 1])

            c_tot, c_uni, c_mul = st.columns(3)
            c_tot.metric("Total de Ordens", total_os)
            c_uni.metric("Ordens com 1 Página", unicas)
            c_mul.metric("Ordens com Mais de 1 Página", multiplas)

            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True
            )
