"""Analyze SMC PDFs with Docling — OCR + TableFormer Accurate Mode."""

import os
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

# Patch symlink creation for Windows without Developer Mode
import huggingface_hub.file_download as _hf_dl
_orig_create_symlink = _hf_dl._create_symlink
def _patched_create_symlink(src, dst, new_blob=False):
    try:
        _orig_create_symlink(src, dst, new_blob=new_blob)
    except OSError:
        import shutil
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.exists(dst):
            os.remove(dst)
        shutil.copyfile(src, dst)
_hf_dl._create_symlink = _patched_create_symlink

from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    TableStructureOptions,
    RapidOcrOptions,
)
from docling.datamodel.base_models import InputFormat
import json
import time

BASE = Path(r"c:\Users\alecf\Desktop\zurich-hackathon\humanCentricInstructionUnderstandingForRobotTaskPlanning")

pipeline_options = PdfPipelineOptions(
    do_ocr=True,
    ocr_options=RapidOcrOptions(),
    do_table_structure=True,
    table_structure_options=TableStructureOptions(mode="accurate"),
)

converter = DocumentConverter(
    format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)}
)

import sys
sys.stdout.reconfigure(encoding='utf-8')

output_file = BASE.parent / "docling_output.txt"

with open(output_file, "w", encoding="utf-8") as out:
    for pdf_name in ["assembly_instruction.pdf", "items_list.pdf"]:
        pdf_path = BASE / pdf_name
        header = f"\n{'='*80}\nPARSING: {pdf_name} ({pdf_path.stat().st_size / 1024:.0f} KB)\n{'='*80}"
        print(header)
        out.write(header + "\n")

        t0 = time.time()
        result = converter.convert(str(pdf_path))
        elapsed = time.time() - t0
        print(f"Parse time: {elapsed:.1f}s")
        out.write(f"Parse time: {elapsed:.1f}s\n")

        doc = result.document
        md = doc.export_to_markdown()

        out.write(f"\n--- MARKDOWN OUTPUT ({len(md)} chars) ---\n\n")
        out.write(md)
        out.write("\n")
        print(f"Markdown: {len(md)} chars written")

        tables = doc.tables
        out.write(f"\n--- TABLES FOUND: {len(tables)} ---\n")
        print(f"Tables found: {len(tables)}")
        for i, table in enumerate(tables):
            out.write(f"\nTable {i+1}:\n")
            try:
                df = table.export_to_dataframe()
                out.write(df.to_string() + "\n")
            except Exception as e:
                out.write(f"  (Could not export to DataFrame: {e})\n")

        out.write(f"\n--- DOCUMENT STRUCTURE ---\n")
        try:
            for page_no, page in doc.pages.items():
                out.write(f"Page {page_no}: size={page.size}\n")
        except Exception as e:
            out.write(f"Pages info: {e}\n")

    out.write("\n\nDONE.\n")
    print(f"\nOutput written to: {output_file}")
