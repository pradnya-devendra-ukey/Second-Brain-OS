import fitz  # PyMuPDF
import re

def parse_pdf(file_path: str) -> str:
    """Extracts text content from a PDF file using PyMuPDF."""
    text = ""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        raise ValueError(f"Error parsing PDF file: {str(e)}")
    return text

def parse_markdown(file_path: str) -> str:
    """Extracts text content from a markdown file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        raise ValueError(f"Error parsing Markdown file: {str(e)}")
    return text

def parse_txt(file_path: str) -> str:
    """Extracts text content from a plain text file."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    except Exception as e:
        raise ValueError(f"Error parsing Text file: {str(e)}")
    return text

def parse_document(file_path: str, file_type: str) -> str:
    """Dispatches parsing depending on file extension/type."""
    file_type = file_type.lower().strip(".")
    if file_type == "pdf":
        return parse_pdf(file_path)
    elif file_type in ("md", "markdown"):
        return parse_markdown(file_path)
    elif file_type in ("txt", "text"):
        return parse_txt(file_path)
    else:
        # Fallback to general read
        return parse_txt(file_path)

def clean_text(text: str) -> str:
    """Cleans up whitespace and formatting artifacts."""
    # Replace multiple spaces with a single space
    text = re.sub(r"[ \t]+", " ", text)
    # Replace multiple newlines with double newlines (to keep paragraph splits)
    text = re.sub(r"\n\s*\n", "\n\n", text)
    return text.strip()
