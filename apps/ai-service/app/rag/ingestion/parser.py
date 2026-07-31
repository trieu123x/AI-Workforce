from app.rag.ingestion.loaders import load_csv, load_docx, load_pdf, load_text


def parse_document(filename: str, data: bytes) -> str:
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension in {"txt", "md"}:
        return load_text(data)
    if extension == "csv":
        return load_csv(data)
    if extension == "pdf":
        return load_pdf(data)
    if extension == "docx":
        return load_docx(data)
    raise ValueError("Supported file types: PDF, DOCX, TXT, MD and CSV")
