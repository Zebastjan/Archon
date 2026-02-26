# Docling Test Fixtures

This directory contains test fixtures for the Docling integration in Archon.

## Files

### PDFs (from Docling repo)

- `normal_4pages.pdf` - Simple multi-page PDF with text and headings
- `code_and_formula.pdf` - PDF with code blocks and mathematical formulas
- `amt_handbook_sample.pdf` - Sample handbook with tables

### DOCX

- `simple_test.docx` - Simple DOCX with headings, paragraphs, and a table

## Source

PDF files are from the [Docling project](https://github.com/docling-project/docling) test data:
- https://github.com/docling-project/docling/tree/main/tests/data/pdf

## Expected Behaviors

| File | Expected | Test Scenario |
|------|----------|---------------|
| normal_4pages.pdf | 4 pages, simple text | Happy path |
| code_and_formula.pdf | Code blocks, formulas | Code chunking |
| amt_handbook_sample.pdf | Tables, mixed content | Table preservation |
| simple_test.docx | Headings, table | DOCX format |

## Adding More Fixtures

To add more fixtures:
1. Download from Docling repo or create new test files
2. Update this README with description
3. Update test expectations in test files
