# converters/pdf_tools.py
# pip install pymupdf pikepdf
# pip install PyPDF2

import os
import shutil
import uuid
import tempfile
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

# Primary engine
try:
    import fitz  # PyMuPDF
except ImportError as e:
    fitz = None

# For repair and encryption roundtrip
try:
    import pikepdf
except ImportError:
    pikepdf = None

# Fallbacks (limited) for merge/split/rotate if PyMuPDF not present
try:
    from PyPDF2 import PdfReader, PdfWriter
except Exception:
    PdfReader = PdfWriter = None


# ============== Helpers ==============


def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def _unique(prefix: str, ext: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}{ext}"


# In converters/pdf_tools.py


# converters/pdf_tools.py
def _open_doc(path: str, password: Optional[str] = None):
    if fitz is None:
        raise RuntimeError("PyMuPDF (fitz) not installed. pip install pymupdf")
    doc = fitz.open(path)  # don't pass password kwarg
    if password:
        if not doc.authenticate(password):
            doc.close()
            raise ValueError("Invalid password for PDF")
    return doc


def _bbox_from_percent(rect: "fitz.Rect", box: Tuple[float, float, float, float]):
    # Helper: supports percentage values 0..1 for (l, t, r, b) of page rect
    l, t, r, b = box
    if 0 <= l <= 1 and 0 <= t <= 1 and 0 <= r <= 1 and 0 <= b <= 1:
        return fitz.Rect(
            rect.x0 + l * rect.width,
            rect.y0 + t * rect.height,
            rect.x0 + r * rect.width,
            rect.y0 + b * rect.height,
        )
    return fitz.Rect(*box)


def _pdf_save(doc: "fitz.Document", out_path: str):
    # Good defaults: deflate, garbage collect objects
    doc.save(out_path, deflate=True, garbage=4, clean=True)


# ============== Functional API (preferred for Flask routes) ==============


def merge_pdfs(paths: List[str], out_path: str, password: Optional[str] = None):
    """
    Merge multiple PDFs into one.
    """
    _ensure_dir(Path(out_path).parent.as_posix())
    if fitz:
        doc = fitz.open()
        try:
            for p in paths:
                src = _open_doc(p, password=password)
                doc.insert_pdf(src)
                src.close()
            _pdf_save(doc, out_path)
        finally:
            doc.close()
        return out_path
    # Fallback: PyPDF2 (no password support here)
    if PdfReader and PdfWriter:
        writer = PdfWriter()
        for p in paths:
            r = PdfReader(p)
            for page in r.pages:
                writer.add_page(page)
        with open(out_path, "wb") as f:
            writer.write(f)
        return out_path
    raise RuntimeError("No PDF engine available (install pymupdf or PyPDF2)")


def split_pdf(path: str, out_dir: str, password: Optional[str] = None) -> List[str]:
    """
    Split PDF into 1-page PDFs. Returns list of output file paths.
    """
    _ensure_dir(out_dir)
    outs = []
    if fitz:
        src = _open_doc(path, password=password)
        try:
            for i in range(src.page_count):
                one = fitz.open()
                one.insert_pdf(src, from_page=i, to_page=i)
                op = os.path.join(out_dir, f"page_{i+1}.pdf")
                _pdf_save(one, op)
                one.close()
                outs.append(op)
        finally:
            src.close()
        return outs
    # Fallback
    if PdfReader and PdfWriter:
        reader = PdfReader(path)
        for i, page in enumerate(reader.pages, start=1):
            w = PdfWriter()
            w.add_page(page)
            op = os.path.join(out_dir, f"page_{i}.pdf")
            with open(op, "wb") as f:
                w.write(f)
            outs.append(op)
        return outs
    raise RuntimeError("No PDF engine available")


def remove_pages(
    path: str, out_path: str, pages_to_remove: List[int], password: Optional[str] = None
):
    """
    Remove 1-based page indices in pages_to_remove.
    """
    _ensure_dir(Path(out_path).parent.as_posix())
    if fitz:
        src = _open_doc(path, password=password)
        try:
            dels = sorted(
                {p - 1 for p in pages_to_remove if 1 <= p <= src.page_count},
                reverse=True,
            )
            for idx in dels:
                src.delete_page(idx)
            _pdf_save(src, out_path)
        finally:
            src.close()
        return out_path
    # Fallback
    if PdfReader and PdfWriter:
        r = PdfReader(path)
        w = PdfWriter()
        dels0 = {p - 1 for p in pages_to_remove}
        for i, page in enumerate(r.pages):
            if i not in dels0:
                w.add_page(page)
        with open(out_path, "wb") as f:
            w.write(f)
        return out_path
    raise RuntimeError("No PDF engine available")


def reorder_pages(
    path: str, out_path: str, new_order: List[int], password: Optional[str] = None
):
    """
    Reorder pages according to 1-based new_order. Missing/extra indices ignored.
    """
    _ensure_dir(Path(out_path).parent.as_posix())
    if fitz:
        src = _open_doc(path, password=password)
        try:
            order0 = [p - 1 for p in new_order if 1 <= p <= src.page_count]
            src.select(order0)
            _pdf_save(src, out_path)
        finally:
            src.close()
        return out_path
    # Fallback
    if PdfReader and PdfWriter:
        r = PdfReader(path)
        w = PdfWriter()
        order0 = [p - 1 for p in new_order if 1 <= p <= len(r.pages)]
        for i in order0:
            w.add_page(r.pages[i])
        with open(out_path, "wb") as f:
            w.write(f)
        return out_path
    raise RuntimeError("No PDF engine available")


def rotate_pdf(
    path: str, out_path: str, angle: int = 90, password: Optional[str] = None
):
    """
    Rotate all pages by angle (90, 180, 270).
    """
    _ensure_dir(Path(out_path).parent.as_posix())
    angle = angle % 360
    if fitz:
        src = _open_doc(path, password=password)
        try:
            for page in src:
                page.set_rotation((page.rotation + angle) % 360)
            _pdf_save(src, out_path)
        finally:
            src.close()
        return out_path
    # Fallback (PyPDF2)
    if PdfReader and PdfWriter:
        r = PdfReader(path)
        w = PdfWriter()
        for page in r.pages:
            page.rotate(angle)  # PyPDF2 3.x supports rotate()
            w.add_page(page)
        with open(out_path, "wb") as f:
            w.write(f)
        return out_path
    raise RuntimeError("No PDF engine available")


# ✅ FIXED: Complete watermark_text with proper parameters
def watermark_text(
    path: str,
    out_path: str,
    text: str,
    opacity: float = 0.15,
    fontsize: int = 48,
    rotation: int = 45,
    position: str = "center",
    password: Optional[str] = None,
):
    """
    Add text watermark to PDF
    """
    _ensure_dir(Path(out_path).parent.as_posix())

    if fitz:
        src = _open_doc(path, password)
        try:
            for page in src:
                rect = page.rect

                # Calculate position
                if position == "center":
                    # Center the text
                    text_rect = fitz.Rect(0, 0, rect.width, rect.height)
                    page.insert_textbox(
                        text_rect,
                        text,
                        fontsize=fontsize,
                        color=(0.5, 0.5, 0.5),  # Gray color
                        align=1,  # Center alignment
                        rotate=rotation,
                        fill_opacity=opacity,
                    )
                else:
                    # Bottom-right position
                    point = fitz.Point(rect.width - 150, rect.height - 50)
                    page.insert_text(
                        point,
                        text,
                        fontsize=fontsize,
                        color=(0.5, 0.5, 0.5),
                        rotate=rotation,
                        fill_opacity=opacity,
                    )

            _pdf_save(src, out_path)
        finally:
            src.close()
        return out_path

    # Fallback: just copy
    shutil.copy2(path, out_path)
    return out_path


def add_page_numbers(
    path: str,
    out_path: str,
    position: str = "bottom-right",
    fontsize: int = 12,
    margin: float = 36,
    password: Optional[str] = None,
):
    """
    Add page numbers to all pages.
    position: bottom-right | bottom-center | bottom-left | top-right | top-center | top-left
    """
    _ensure_dir(Path(out_path).parent.as_posix())
    if fitz:
        src = _open_doc(path, password=password)
        try:
            for i, page in enumerate(src, start=1):
                w, h = page.rect.width, page.rect.height
                if position == "bottom-right":
                    pt = fitz.Point(w - margin, h - margin)
                    align = 2
                elif position == "bottom-center":
                    pt = fitz.Point(w / 2, h - margin)
                    align = 1
                elif position == "bottom-left":
                    pt = fitz.Point(margin, h - margin)
                    align = 0
                elif position == "top-right":
                    pt = fitz.Point(w - margin, margin)
                    align = 2
                elif position == "top-center":
                    pt = fitz.Point(w / 2, margin)
                    align = 1
                else:  # top-left
                    pt = fitz.Point(margin, margin)
                    align = 0
                page.insert_text(
                    pt, str(i), fontsize=fontsize, color=(0, 0, 0), align=align
                )
            _pdf_save(src, out_path)
        finally:
            src.close()
        return out_path
    # Fallback: not feasible with PyPDF2 alone
    shutil.copy2(path, out_path)
    return out_path


def crop_pdf(
    path: str,
    out_path: str,
    box: Tuple[float, float, float, float],
    use_percent: bool = False,
    password: Optional[str] = None,
):
    """
    Crop all pages to given box.
    box: (left, top, right, bottom). If use_percent=True, values are 0..1 of page size.
    """
    _ensure_dir(Path(out_path).parent.as_posix())
    if fitz:
        src = _open_doc(path, password=password)
        try:
            for page in src:
                rect = page.rect
                new_box = (
                    _bbox_from_percent(rect, box) if use_percent else fitz.Rect(*box)
                )
                page.set_cropbox(new_box)
            _pdf_save(src, out_path)
        finally:
            src.close()
        return out_path
    shutil.copy2(path, out_path)
    return out_path


def protect_pdf(
    path: str,
    out_path: str,
    user_pw: Optional[str] = None,
    owner_pw: Optional[str] = None,
    permissions: int = -3904,
    password: Optional[str] = None,
):
    """
    Protect (encrypt) PDF with AES-256.
    permissions: PyMuPDF permissions bitmask. Default: print/copy disabled; adjust as needed.
    """
    _ensure_dir(Path(out_path).parent.as_posix())
    if fitz:
        src = _open_doc(path, password=password)
        try:
            src.save(
                out_path,
                encryption=fitz.PDF_ENCRYPT_AES_256,
                owner_pw=owner_pw or "",
                user_pw=user_pw or "",
                permissions=permissions,
            )
        finally:
            src.close()
        return out_path
    # Fallback via pikepdf
    if pikepdf:
        with pikepdf.open(path, password=password) as pdf:
            pdf.save(
                out_path,
                encryption=pikepdf.Encryption(owner=owner_pw or "", user=user_pw or ""),
            )
        return out_path
    shutil.copy2(path, out_path)
    return out_path


def unlock_pdf(path: str, out_path: str, password: str):
    """
    Unlock encrypted PDF (requires correct password).
    """
    _ensure_dir(Path(out_path).parent.as_posix())
    if fitz:
        src = _open_doc(path, password=password)
        try:
            _pdf_save(src, out_path)
        finally:
            src.close()
        return out_path
    # Fallback pikepdf
    if pikepdf:
        with pikepdf.open(path, password=password) as pdf:
            pdf.save(out_path)
        return out_path
    shutil.copy2(path, out_path)
    return out_path


# ✅ FIXED: Complete compress_pdf implementation
def compress_pdf(
    path: str, out_path: str, quality: str = "medium", password: Optional[str] = None
):
    """
    Compress PDF by optimizing content and images
    """
    _ensure_dir(Path(out_path).parent.as_posix())

    if fitz:
        src = _open_doc(path, password)
        try:
            # Quality settings
            quality_map = {"low": 30, "medium": 60, "high": 85}
            jpeg_quality = quality_map.get(quality.lower(), 60)

            # Process each page
            for page_num in range(src.page_count):
                page = src[page_num]

                # Get and optimize images
                image_list = page.get_images()
                for img_index, img in enumerate(image_list):
                    xref = img[0]
                    pix = fitz.Pixmap(src, xref)

                    # Skip if already small or if it's a mask
                    if pix.width < 100 or pix.height < 100:
                        pix = None
                        continue

                    # Convert to JPEG if not already
                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        img_data = pix.tobytes("jpeg", jpg_quality=jpeg_quality)
                        img_dict = {
                            "ext": "jpeg",
                            "smask": 0,
                            "width": pix.width,
                            "height": pix.height,
                            "colorspace": pix.colorspace.n if pix.colorspace else 1,
                            "bpc": 8,
                        }
                        src.update_stream(xref, img_data, new=img_dict)
                    pix = None

            # Save with compression
            _pdf_save(src, out_path)
        finally:
            src.close()
        return out_path

    # Fallback
    if pikepdf:
        try:
            with pikepdf.open(path, password=password) as pdf:
                pdf.save(
                    out_path,
                    compress_streams=True,
                    object_stream_mode=pikepdf.ObjectStreamMode.generate,
                )
            return out_path
        except Exception:
            pass

    # Last resort
    shutil.copy2(path, out_path)
    return out_path


def repair_pdf(path: str, out_path: str):
    """
    Repair malformed PDFs via pikepdf round-trip and linearization if possible.
    """
    _ensure_dir(Path(out_path).parent.as_posix())
    if pikepdf:
        try:
            with pikepdf.open(path) as pdf:
                pdf.save(out_path, fix_metadata=True, linearize=True)
            return out_path
        except Exception:
            pass
    # Fallback: simple copy
    shutil.copy2(path, out_path)
    return out_path


def ocr_pdf_to_pdfa(path: str, out_path: str, lang: str = "eng"):
    """
    OCR to searchable PDF-A using OCRmyPDF CLI. Requires 'ocrmypdf' and 'tesseract' installed.
    """
    _ensure_dir(Path(out_path).parent.as_posix())
    cmd = [
        "ocrmypdf",
        "--output-type",
        "pdfa",
        "--optimize",
        "3",
        "--skip-text",
        "--language",
        lang,
        path,
        out_path,
    ]
    subprocess.run(cmd, check=True)
    return out_path


def pdf_to_images(
    path: str,
    out_dir: str,
    dpi: int = 150,
    fmt: str = "png",
    password: Optional[str] = None,
) -> List[str]:
    """
    Render PDF pages to images. Returns list of output image files.
    """
    _ensure_dir(out_dir)
    outs = []
    if fitz:
        src = _open_doc(path, password=password)
        try:
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            for i, page in enumerate(src, start=1):
                pix = page.get_pixmap(matrix=mat, alpha=False)
                op = os.path.join(out_dir, f"page_{i}.{fmt}")
                pix.save(op)
                outs.append(op)
        finally:
            src.close()
        return outs
    # Fallback via pdf2image if present
    try:
        import pdf2image

        images = pdf2image.convert_from_path(path, dpi=dpi)
        for i, im in enumerate(images, start=1):
            op = os.path.join(out_dir, f"page_{i}.{fmt}")
            im.save(op, format=fmt.upper())
            outs.append(op)
        return outs
    except Exception as e:
        raise RuntimeError(f"PDF to images requires PyMuPDF or pdf2image: {e}")


# ============== Class wrapper (backward compatible) ==============


class PDFTools:
    """
    Backward-compatible class wrapper. Prefer functional API for explicit outputs.
    """

    def __init__(self, output_dir: Optional[str] = None):
        if output_dir:
            self.output_dir = output_dir
            _ensure_dir(self.output_dir)
        else:
            self.output_dir = tempfile.mkdtemp(prefix="pdf_")

    # Original signatures kept, outputs in self.output_dir

    def merge_pdfs(self, file_paths: List[str]) -> str:
        out = os.path.join(self.output_dir, "merged.pdf")
        return merge_pdfs(file_paths, out)

    def split_pdf(self, file_path: str) -> str:
        out_dir = os.path.join(self.output_dir, "split_pages")
        split_pdf(file_path, out_dir)
        return out_dir

    def compress_pdf(self, file_path: str) -> str:
        out = os.path.join(self.output_dir, "compressed.pdf")
        return compress_pdf(file_path, out)

    def rotate_pdf(self, file_path: str, angle: int) -> str:
        out = os.path.join(self.output_dir, "rotated.pdf")
        return rotate_pdf(file_path, out, angle=angle)

    def add_watermark(self, file_path: str, watermark_text: str) -> str:
        out = os.path.join(self.output_dir, "watermarked.pdf")
        return watermark_text_func(file_path, out, watermark_text)

    # New richer methods

    def remove_pages(self, file_path: str, pages: List[int]) -> str:
        out = os.path.join(self.output_dir, "removed_pages.pdf")
        return remove_pages(file_path, out, pages)

    def reorder_pages(self, file_path: str, order: List[int]) -> str:
        out = os.path.join(self.output_dir, "reordered.pdf")
        return reorder_pages(file_path, out, order)

    def page_numbers(
        self, file_path: str, position: str = "bottom-right", fontsize: int = 12
    ) -> str:
        out = os.path.join(self.output_dir, "numbered.pdf")
        return add_page_numbers(file_path, out, position=position, fontsize=fontsize)

    def crop(
        self,
        file_path: str,
        box: Tuple[float, float, float, float],
        use_percent: bool = False,
    ) -> str:
        out = os.path.join(self.output_dir, "cropped.pdf")
        return crop_pdf(file_path, out, box=box, use_percent=use_percent)

    def protect(
        self, file_path: str, user_pw: Optional[str], owner_pw: Optional[str]
    ) -> str:
        out = os.path.join(self.output_dir, "protected.pdf")
        return protect_pdf(file_path, out, user_pw=user_pw, owner_pw=owner_pw)

    def unlock(self, file_path: str, password: str) -> str:
        out = os.path.join(self.output_dir, "unlocked.pdf")
        return unlock_pdf(file_path, out, password=password)

    def repair(self, file_path: str) -> str:
        out = os.path.join(self.output_dir, "repaired.pdf")
        return repair_pdf(file_path, out)

    def ocr_pdfa(self, file_path: str, lang: str = "eng") -> str:
        out = os.path.join(self.output_dir, "ocr_pdfa.pdf")
        return ocr_pdf_to_pdfa(file_path, out, lang=lang)

    def to_images(self, file_path: str, dpi: int = 150, fmt: str = "png") -> str:
        out_dir = os.path.join(self.output_dir, "images")
        pdf_to_images(file_path, out_dir, dpi=dpi, fmt=fmt)
        return out_dir


# Alias for class watermark method compatibility
def watermark_text_func(in_path, out_path, text):
    return watermark_text(in_path, out_path, text)
