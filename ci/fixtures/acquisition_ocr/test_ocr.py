"""OCR and rasterized PDF fixtures; trusted inputs only."""
import importlib.util
import io
import unittest
from PIL import Image, ImageDraw, ImageFont

class OCRFixtures(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec("scripts.acquisition_ocr"),"OCR module missing")
        from scripts import acquisition_ocr
        self.a=acquisition_ocr

    def image(self,kind):
        img=Image.new("RGB",(1200,300),"white")
        draw=ImageDraw.Draw(img)
        font=ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",72)
        draw.text((35,85),"ZEIBAEL 12345",font=font,fill="black")
        out=io.BytesIO()
        img.save(out,format=kind)
        return out.getvalue()

    def test_png_ocr(self):
        r=self.a.extract_ocr(self.image("PNG"),"png")
        self.assertIn("ZEIBAEL 12345",r["units"][0]["text"])
        self.assertEqual(r["units"][0]["page"],1)
        self.assertEqual(len(r["sha256"]),64)

    def test_scanned_pdf_ocr(self):
        r=self.a.extract_ocr(self.image("PDF"),"pdf")
        self.assertIn("ZEIBAEL 12345",r["units"][0]["text"])
        self.assertEqual(r["units"][0]["page"],1)

    def test_guards(self):
        for raw,kind in [(b"not image","png"),(b"x"*8000001,"png"),(self.image("PNG"),"gif")]:
            with self.subTest(kind=kind),self.assertRaises(ValueError):
                self.a.extract_ocr(raw,kind)

if __name__=="__main__":
    unittest.main(verbosity=2)
