import streamlit as st
import os
import shutil
import zipfile
import re
from pypdf import PdfReader, PdfWriter
import pdf2image
import pytesseract

st.set_page_config(page_title="Separador de OS", page_icon="📄", layout="centered")
st.title("📄 Separador Inteligente de Ordens de Serviço")
st.write("Faça o upload do PDF único. O sistema usará OCR para separar cada Ordem e gerar um ZIP para download.")

@st.cache_data
def get_regex():
    return re.compile(r'(?:ordem|os|o\s*s|o\s*n)[\s:#№]*([0-9]{9})', re.IGNORECASE), re.compile(r'fim\s+d[eo]\s+relat[óoa]rio', re.IGNORECASE)

arquivo_carregado = st.file_uploader("Arraste e solte o PDF aqui", type=["pdf"])

if arquivo_carregado and st.button("🚀 Iniciar Processamento", type="primary", use_container_width=True):
    INPUT_DIR, OUTPUT_DIR, ZIP_PATH = "temp_input", "temp_output", "Ordens_Separadas.zip"

    os.makedirs(INPUT_DIR, exist_ok=True)
    if os.path.exists(OUTPUT_DIR): shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    input_pdf_path = os.path.join(INPUT_DIR, arquivo_carregado.name)
    with open(input_pdf_path, "wb") as f: f.write(arquivo_carregado.getbuffer())

    reader = PdfReader(input_pdf_path)
    total_pages = len(reader.pages)
    current_os_number, current_writer = None, None

    progress_bar = st.progress(0)
    status_text = st.empty()
    log_box = st.empty()
    logs = []
    regex_ordem, regex_fim = get_regex()

    for page_num in range(total_pages):
        status_text.text(f"A ler página {page_num + 1} de {total_pages}...")
        imagens = pdf2image.convert_from_path(input_pdf_path, dpi=150, first_page=page_num + 1, last_page=page_num + 1)

        if not imagens: continue

        texto_ocr = pytesseract.image_to_string(imagens[0], lang='por')
        match_ordem = regex_ordem.search(texto_ocr)
        nova_os = match_ordem.group(1) if match_ordem else None
        fim_relatorio = bool(regex_fim.search(texto_ocr))

        if nova_os:
            if current_writer and current_os_number:
                with open(os.path.join(OUTPUT_DIR, f"{current_os_number}.pdf"), "wb") as f_out: current_writer.write(f_out)
            current_os_number, current_writer = nova_os, PdfWriter()
            current_writer.add_page(reader.pages[page_num])
            logs.append(f"✅ Nova Ordem: {current_os_number}")

        elif current_os_number and current_writer:
            current_writer.add_page(reader.pages[page_num])
            logs.append(f"↳ Página anexada à Ordem {current_os_number}")

        if fim_relatorio and current_writer and current_os_number:
            with open(os.path.join(OUTPUT_DIR, f"{current_os_number}.pdf"), "wb") as f_out: current_writer.write(f_out)
            logs.append(f"🏁 Fim de relatório! Ordem {current_os_number} salva.")
            current_os_number, current_writer = None, None

        progress_bar.progress((page_num + 1) / total_pages)
        log_box.code("\n".join(logs[-5:]))

    if current_writer and current_os_number:
        with open(os.path.join(OUTPUT_DIR, f"{current_os_number}.pdf"), "wb") as f_out: current_writer.write(f_out)

    status_text.text("📦 A compactar ficheiros...")
    with zipfile.ZipFile(ZIP_PATH, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, arquivos in os.walk(OUTPUT_DIR):
            for arquivo in arquivos:
                if arquivo.endswith('.pdf'): zipf.write(os.path.join(root, arquivo), arcname=arquivo)

    st.success("Análise concluída com sucesso!")
    with open(ZIP_PATH, "rb") as fp:
        st.download_button(label="⬇️ Descarregar Ordens Separadas (ZIP)", data=fp, file_name="Ordens_Separadas.zip", mime="application/zip", type="primary", use_container_width=True)