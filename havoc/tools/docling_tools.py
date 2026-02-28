"""Docling document parsing tools — deep integration with TableFormer, OCR, multi-format."""

from __future__ import annotations

import logging
import os
import shutil
import time
from pathlib import Path
from typing import Any

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import huggingface_hub.file_download as _hf_dl
_orig_symlink = _hf_dl._create_symlink
def _patched_symlink(src, dst, new_blob=False):
    try:
        _orig_symlink(src, dst, new_blob=new_blob)
    except OSError:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            os.remove(dst)
        shutil.copyfile(src, dst)
_hf_dl._create_symlink = _patched_symlink

from langchain_core.tools import tool

from models import DocumentSource, ParsedDocument

logger = logging.getLogger(__name__)

_converter = None


def _get_converter():
    global _converter
    if _converter is not None:
        return _converter

    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.pipeline_options import (
        PdfPipelineOptions,
        TableStructureOptions,
        RapidOcrOptions,
    )
    from docling.datamodel.base_models import InputFormat

    pipeline_options = PdfPipelineOptions(
        do_ocr=True,
        ocr_options=RapidOcrOptions(),
        do_table_structure=True,
        table_structure_options=TableStructureOptions(mode="accurate"),
    )

    _converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
        },
    )
    return _converter


@tool
def docling_convert(file_path: str) -> str:
    """Convert a document (PDF, DOCX, image, etc.) to structured markdown using Docling.

    Args:
        file_path: Path to the document file.

    Returns:
        Structured markdown representation of the document.
    """
    converter = _get_converter()
    result = converter.convert(file_path)
    doc = result.document
    return doc.export_to_markdown()


@tool
def docling_extract_tables(file_path: str) -> str:
    """Extract all tables from a document as structured data using Docling TableFormer.

    Args:
        file_path: Path to the document file.

    Returns:
        JSON string with all extracted tables (list of dicts with headers and rows).
    """
    import json
    converter = _get_converter()
    result = converter.convert(file_path)
    doc = result.document

    tables_out = []
    for i, table in enumerate(doc.tables):
        try:
            df = table.export_to_dataframe()
            tables_out.append({
                "table_index": i,
                "headers": list(df.columns),
                "rows": df.values.tolist(),
                "shape": list(df.shape),
            })
        except Exception as e:
            tables_out.append({"table_index": i, "error": str(e)})

    return json.dumps(tables_out, indent=2, default=str)


@tool
def docling_get_sections(file_path: str) -> str:
    """Extract document section hierarchy using Docling layout analysis.

    Args:
        file_path: Path to the document file.

    Returns:
        JSON string with section titles and their content.
    """
    import json
    converter = _get_converter()
    result = converter.convert(file_path)
    doc = result.document

    sections = []
    md = doc.export_to_markdown()
    current_section = ""
    current_content: list[str] = []

    for line in md.split("\n"):
        if line.startswith("#"):
            if current_section:
                sections.append({
                    "title": current_section,
                    "content": "\n".join(current_content).strip(),
                })
            current_section = line.lstrip("#").strip()
            current_content = []
        else:
            current_content.append(line)

    if current_section:
        sections.append({
            "title": current_section,
            "content": "\n".join(current_content).strip(),
        })

    return json.dumps(sections, indent=2)


def parse_document_full(file_path: str | Path) -> ParsedDocument:
    """Full document parse — returns ParsedDocument with all extracted data."""
    file_path = Path(file_path)
    start = time.time()

    converter = _get_converter()
    result = converter.convert(str(file_path))
    doc = result.document

    markdown = doc.export_to_markdown()

    try:
        raw_dict = doc.export_to_dict()
    except Exception:
        raw_dict = {}

    tables_data = []
    for i, table in enumerate(doc.tables):
        try:
            df = table.export_to_dataframe()
            tables_data.append({
                "table_index": i,
                "headers": list(df.columns),
                "rows": df.values.tolist(),
            })
        except Exception:
            pass

    sections = []
    current = ""
    for line in markdown.split("\n"):
        if line.startswith("#"):
            title = line.lstrip("#").strip()
            if title and title != current:
                sections.append(title)
                current = title

    page_count = 0
    try:
        page_count = len(doc.pages)
    except Exception:
        pass

    elapsed = (time.time() - start) * 1000

    return ParsedDocument(
        filename=file_path.name,
        format=file_path.suffix.lstrip(".").upper(),
        pages=page_count,
        tables_found=len(tables_data),
        sections=sections,
        markdown=markdown,
        raw_dict=raw_dict,
        tables_data=tables_data,
        parse_time_ms=round(elapsed, 1),
    )
