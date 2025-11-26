import os
import PyPDF2
import docx


def extract_text_from_file(uploaded_file):
    text = ""
    try:
        filename = uploaded_file.filename or ""
        ext = os.path.splitext(filename)[1].lower()

        if ext == ".pdf":
            reader = PyPDF2.PdfReader(uploaded_file)
            for page in reader.pages:
                page_text = page.extract_text() or ""
                text += page_text

        elif ext == ".docx":
            doc = docx.Document(uploaded_file)
            for para in doc.paragraphs:
                text += para.text + "\n"

        else:
            uploaded_file.seek(0)
            text = uploaded_file.read().decode("utf-8", errors="ignore")

    except Exception as e:
        return f"Erro ao ler arquivo: {e}"

    return text
