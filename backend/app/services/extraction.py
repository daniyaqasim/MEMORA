from pathlib import Path

import fitz


def extract_text(file_path: Path, file_type: str) -> str | None:
    """Extract text only from file types supported in Stage 3.

    Image files intentionally return ``None``: OCR is not part of this stage.
    """
    if file_type == "txt":
        return extract_txt(file_path)
    if file_type == "pdf":
        return extract_pdf(file_path)
    return None


def extract_txt(file_path: Path) -> str:
    data = file_path.read_bytes()
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252")


def extract_pdf(file_path: Path) -> str:
    with fitz.open(file_path) as document:
        return "\n".join(page.get_text("text") for page in document)
