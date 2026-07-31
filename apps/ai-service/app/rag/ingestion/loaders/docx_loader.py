import io
import re
import zipfile
from xml.etree import ElementTree


def load_docx(data: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        root = ElementTree.fromstring(archive.read("word/document.xml"))
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{namespace}p"):
        text = "".join(node.text or "" for node in paragraph.iter(f"{namespace}t")).strip()
        if not text:
            continue
        style = paragraph.find(f"{namespace}pPr/{namespace}pStyle")
        style_name = style.get(f"{namespace}val", "").lower() if style is not None else ""
        heading = re.match(r"heading(\d+)", style_name)
        if heading:
            text = f"{'#' * min(int(heading.group(1)), 6)} {text}"
        paragraphs.append(text)
    return "\n".join(paragraphs)
