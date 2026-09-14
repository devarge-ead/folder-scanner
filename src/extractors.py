"""Per-format text extraction.

Each function returns a list of ``(kind, value, text)`` tuples where:
  * ``kind`` is one of ``"page"``, ``"line"``, ``"cell"`` or ``"para"``
  * ``value`` is a human readable location descriptor
  * ``text`` is the visible text found at that location

Only body/visible text is extracted; document metadata is intentionally skipped.
Libraries are imported lazily inside each function so a missing optional package
never crashes the application at startup.
"""

import os


# --------------------------------------------------------------------------- #
# Word (.docx) - python-docx
# --------------------------------------------------------------------------- #
def docx_chunks(path: str):
    """Yield visible text chunks from a modern Word document.

    The docx format has no page concept (rendering decides pagination), so
    paragraphs and table cells are reported instead.
    """
    from docx import Document

    document = Document(path)
    result = []

    para_no = 0
    for paragraph in document.paragraphs:
        text = (paragraph.text or "").strip()
        if text:
            para_no += 1
            result.append(("para", str(para_no), text))

    table_no = 0
    for table in document.tables:
        table_no += 1
        for row_idx, row in enumerate(table.rows, 1):
            for col_idx, cell in enumerate(row.cells, 1):
                text = (cell.text or "").strip()
                if text:
                    result.append(("cell", f"T{table_no} R{row_idx} C{col_idx}", text))

    return result


# --------------------------------------------------------------------------- #
# Excel (.xlsx / .xls)
# --------------------------------------------------------------------------- #
def xlsx_chunks(path: str):
    """Yield cell text chunks (with sheet + cell reference) from .xlsx files."""
    from openpyxl import load_workbook

    workbook = load_workbook(path, read_only=True, data_only=True)
    result = []
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue
                value = str(cell.value).strip()
                if value:
                    result.append(("cell", f"{sheet.title}!{cell.coordinate}", value))
    workbook.close()
    return result


def xls_chunks(path: str):
    """Yield cell text chunks from legacy .xls files."""
    import xlrd

    workbook = xlrd.open_workbook(path)
    result = []
    for sheet in workbook.sheets():
        for row_idx in range(sheet.nrows):
            for col_idx in range(sheet.ncols):
                raw = sheet.cell_value(row_idx, col_idx)
                if raw is None:
                    continue
                value = str(raw).strip()
                if value:
                    coord = f"{sheet.name}!R{row_idx + 1}C{col_idx + 1}"
                    result.append(("cell", coord, value))
    return result


# --------------------------------------------------------------------------- #
# PDF - PyMuPDF (fitz), reports real page numbers
# --------------------------------------------------------------------------- #
def pdf_chunks(path: str):
    """Yield page text chunks from a PDF, one chunk per page."""
    try:
        import pymupdf as fitz  # modern PyMuPDF import name
    except ImportError:
        import fitz  # legacy import name fallback

    result = []
    with fitz.open(path) as document:
        for page_no, page in enumerate(document, 1):
            text = (page.get_text() or "").strip()
            if text:
                result.append(("page", str(page_no), text))
    return result


# --------------------------------------------------------------------------- #
# Plain text files - line based
# --------------------------------------------------------------------------- #
def txt_chunks(path: str):
    """Yield line chunks from a plain text file."""
    result = []
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line_no, line in enumerate(handle, 1):
            text = line.rstrip("\r\n").strip()
            if text:
                result.append(("line", str(line_no), text))
    return result


# --------------------------------------------------------------------------- #
# Legacy Word (.doc) - best effort text extraction via olefile
# --------------------------------------------------------------------------- #
def doc_chunks(path: str):
    """Best effort extraction of visible text from a legacy .doc file.

    The .doc format stores text inside OLE streams; this heuristic reads the
    WordDocument stream and keeps readable runs. It is good enough for exact
    substring search on most files.
    """
    import olefile

    if not olefile.isOleFile(path):
        return []

    ole = olefile.OleFileIO(path)
    try:
        stream = ole.openstream("WordDocument")
        data = stream.read()
    finally:
        ole.close()

    return _extract_readable_runs(data)


def _extract_readable_runs(data: bytes):
    """Extract readable text runs from raw .doc bytes."""
    result = []
    current = []
    i = 0
    length = len(data)
    while i < length:
        char_code = data[i]
        # Two-stroke unicode marker in Word files (0x13 control)
        if char_code == 0x13 and i + 1 < length:
            candidate = data[i + 1]
            if 0x20 <= candidate < 0x7F or candidate in (0xE9, 0xE7, 0xF0, 0xDD):
                current.append(chr(candidate))
                i += 2
                continue
        if 0x20 <= char_code < 0x7F:
            current.append(chr(char_code))
        elif current:
            run = "".join(current).strip()
            if len(run) > 1:
                result.append(("para", str(len(result) + 1), run))
            current = []
        i += 1

    if current:
        run = "".join(current).strip()
        if len(run) > 1:
            result.append(("para", str(len(result) + 1), run))
    return result


# --------------------------------------------------------------------------- #
# Extension routing
# --------------------------------------------------------------------------- #
TYPE_TO_EXTENSIONS = {
    "word": {".doc", ".docx"},
    "excel": {".xls", ".xlsx", ".xlsm"},
    "pdf": {".pdf"},
    "txt": {".txt", ".log", ".csv", ".md", ".json", ".xml", ".ini", ".cfg", ".tsv"},
}

_TYPE_TO_EXTRACTOR = {
    "docx": docx_chunks,
    "doc": doc_chunks,
    "xlsx": xlsx_chunks,
    "xls": xls_chunks,
    "pdf": pdf_chunks,
    "txt": txt_chunks,
}


def chunks_for_path(path: str):
    """Dispatch a file to the matching extractor based on its extension.

    Returns ``None`` when the format has no registered extractor.
    """
    extension = os.path.splitext(path)[1].lower()
    extractor = _TYPE_TO_EXTRACTOR.get(extension.lstrip("."))
    if extractor is None:
        return None
    return extractor(path)