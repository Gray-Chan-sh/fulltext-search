"""Plain text / code file extraction."""

import mimetypes
from pathlib import Path

# Common text extensions that might not be recognised by mimetypes
TEXT_EXTENSIONS: set[str] = {
    ".txt", ".md", ".rst", ".log", ".csv", ".tsv", ".json", ".xml", ".yaml",
    ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".h", ".cpp", ".hpp",
    ".rs", ".go", ".rb", ".php", ".sh", ".bash", ".zsh", ".fish",
    ".sql", ".r", ".m", ".swift", ".kt", ".scala", ".clj", ".lua",
    ".html", ".htm", ".css", ".scss", ".less", ".sass",
    ".diff", ".patch", ".gitignore", ".env", ".dockerfile",
    ".vue", ".svelte", ".astro", ".ejs", ".hbs",
    ".tex", ".bib",
}


def is_text_file(path: str) -> bool:
    """Check if a file is likely plain text by extension."""
    ext = Path(path).suffix.lower()
    if ext in TEXT_EXTENSIONS:
        return True
    # Check mimetype for unrecognised text files
    mime, _ = mimetypes.guess_type(path)
    if mime and mime.startswith("text/"):
        return True
    return False


def extract(path: str) -> str:
    """Read a text file. Returns empty string on decode error."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return ""
