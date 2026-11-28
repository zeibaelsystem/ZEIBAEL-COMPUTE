"""Only synthetic documents and mocked HTTP; no private data or external crawling."""
import importlib.util
import io
import unittest
import zipfile

import docx
import httpx
import openpyxl
import pptx
from pypdf import PdfWriter
from pypdf.generic import (DecodedStreamObject, DictionaryObject, NameObject,
                           NumberObject)


def buffer(document):
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def pdf_fixture():
    writer = PdfWriter()
    page = writer.add_blank_page(200, 200)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})
    })
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 10 100 Td (ZEIBAEL PDF) Tj ET")
    page[NameObject("/Contents")] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


class Adapters(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("scripts.acquisition_adapters"),
                             "open source adapters not implemented")
        from scripts import acquisition_adapters
        self.a = acquisition_adapters

    def test_pdf(self):
        r = self.a.extract_document(pdf_fixture(), "pdf")
        self.assertIn("ZEIBAEL PDF", r["units"][0]["text"])
        self.assertEqual(r["units"][0]["page"], 1)

    def test_docx(self):
        doc = docx.Document()
        doc.add_paragraph("ZEIBAEL Word")
        table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "key"
        table.cell(0, 1).text = "value"
        r = self.a.extract_document(buffer(doc), "docx")
        self.assertIn("ZEIBAEL Word", r["text"])
        self.assertEqual(r["tables"][0], [["key", "value"]])

    def test_pptx(self):
        presentation = pptx.Presentation()
        slide = presentation.slides.add_slide(presentation.slide_layouts[5])
        slide.shapes.title.text = "ZEIBAEL Slides"
        r = self.a.extract_document(buffer(presentation), "pptx")
        self.assertIn("ZEIBAEL Slides", r["units"][0]["text"])
        self.assertEqual(r["units"][0]["slide"], 1)

    def test_xlsx(self):
        book = openpyxl.Workbook()
        book.active.append(["price", 5])
        book.active.append(["formula", "=B1*2"])
        r = self.a.extract_document(buffer(book), "xlsx")
        self.assertEqual(r["units"][0]["rows"], [["price", 5], ["formula", "=B1*2"]])

    def test_reject_oversize_and_dangerous_zip(self):
        with self.assertRaises(ValueError):
            self.a.extract_document(b"x" * (8_000_001), "pdf")
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as z:
            z.writestr("../outside.xml", "<x/>")
        with self.assertRaises(ValueError):
            self.a.extract_document(out.getvalue(), "docx")

    def test_scrapy_selectors(self):
        r = self.a.extract_html(b'<h1>ZEIBAEL</h1><a href="/next">Next</a>',
                                "https://example.org/")
        self.assertEqual(r["titles"], ["ZEIBAEL"])
        self.assertEqual(r["links"], ["https://example.org/next"])

    def test_httpx_mocked_transport(self):
        seen = []
        def handler(req):
            seen.append(str(req.url))
            return httpx.Response(200, headers={"Content-Type": "application/json"},
                                  content=b'{"value":3}')
        with httpx.Client(transport=httpx.MockTransport(handler), trust_env=False,
                          follow_redirects=False) as client:
            r = self.a.read_mock_response(client, "https://example.org/data", 100)
        self.assertEqual(r.status, 200)
        self.assertEqual(r.body, b'{"value":3}')
        self.assertEqual(seen, ["https://example.org/data"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
