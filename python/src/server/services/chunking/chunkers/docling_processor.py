"""Docling document processor for PDF/DOCX conversion."""

from pathlib import Path
from typing import Any

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter


class DoclingDocumentProcessor:
    """Handles conversion of PDF/DOCX/PPTX files to DoclingDocument.

    This processor wraps Docling's DocumentConverter to provide a simple
    interface for converting various document formats to the DoclingDocument
    representation, which can then be fed into chunkers.
    """

    def __init__(
        self,
        do_ocr: bool = True,
        do_table_structure: bool = True,
    ):
        """Initialize the DoclingDocumentProcessor.

        Args:
            do_ocr: Enable OCR for scanned documents
            do_table_structure: Enable table structure extraction
        """
        pdf_options = PdfPipelineOptions()
        pdf_options.do_ocr = do_ocr
        pdf_options.do_table_structure = do_table_structure

        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: pdf_options,
            }
        )

    def convert_file(self, file_path: str | Path) -> Any:
        """Convert a local file to DoclingDocument.

        Args:
            file_path: Path to the document (PDF, DOCX, PPTX, etc.)

        Returns:
            ConversionResult with document attribute containing DoclingDocument

        Raises:
            Exception: If conversion fails
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Document not found: {file_path}")

        result = self.converter.convert(path)
        return result

    def convert_bytes(self, content: bytes, filename: str = "document.pdf") -> Any:
        """Convert document bytes to DoclingDocument.

        Args:
            content: Document bytes
            filename: Original filename (determines format)

        Returns:
            ConversionResult with document attribute containing DoclingDocument

        Raises:
            Exception: If conversion fails
        """
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=filename) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            result = self.converter.convert(Path(tmp_path))
            return result
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def convert_url(self, url: str, **kwargs: Any) -> Any:
        """Convert a URL to DoclingDocument.

        Args:
            url: URL to the document
            **kwargs: Additional arguments passed to converter (e.g., max_num_pages)

        Returns:
            ConversionResult with document attribute containing DoclingDocument

        Raises:
            Exception: If conversion fails
        """
        result = self.converter.convert(url, **kwargs)
        return result

    def export_to_markdown(self, conversion_result: Any) -> str:
        """Export a DoclingDocument to markdown.

        Args:
            conversion_result: Result from convert_* methods

        Returns:
            Markdown representation of the document
        """
        return conversion_result.document.export_to_markdown()

    def export_to_text(self, conversion_result: Any) -> str:
        """Export a DoclingDocument to plain text.

        Args:
            conversion_result: Result from convert_* methods

        Returns:
            Plain text representation of the document
        """
        return conversion_result.document.export_to_text()


__all__ = ["DoclingDocumentProcessor"]
