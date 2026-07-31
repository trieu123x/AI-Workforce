import io

from pypdf import PdfReader


def load_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n\n".join(
        f"[[PAGE:{page_number}]]\n{page.extract_text() or ''}"
        for page_number, page in enumerate(reader.pages, start=1)
    )
