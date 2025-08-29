import os
import io
import uuid
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageOps, ImageSequence

# Enhanced image_converters.py
def remove_background(in_path: str, out_path: str):
    """Remove background using rembg"""
    from rembg import remove
    from PIL import Image
    _ensure_dir(Path(out_path).parent.as_posix())
    input_image = Image.open(in_path)
    output_image = remove(input_image)
    output_image.save(out_path, "PNG")
    return out_path

def resize_image(in_path: str, out_path: str, width: int = None, height: int = None, keep_ratio: bool = True):
    """Resize image with optional aspect ratio preservation"""
    with _open_image_normalized(in_path) as im:
        if keep_ratio:
            im.thumbnail((width or im.width, height or im.height), Image.Resampling.LANCZOS)
        else:
            im = im.resize((width, height), Image.Resampling.LANCZOS)
        _ensure_dir(Path(out_path).parent.as_posix())
        im.save(out_path)
    return out_path

def compress_image(in_path: str, out_path: str, quality: int = 85, optimize: bool = True):
    """Compress image while maintaining quality"""
    with _open_image_normalized(in_path) as im:
        _ensure_dir(Path(out_path).parent.as_posix())
        if Path(out_path).suffix.lower() in ['.jpg', '.jpeg']:
            im = _flatten_if_needed(im)
            im.save(out_path, "JPEG", quality=quality, optimize=optimize, progressive=True)
        else:
            im.save(out_path, optimize=optimize)
    return out_path

# Optional plugins
_HAVE_HEIF = False
try:
    from pillow_heif import register_heif_opener  # pip install pillow-heif
    register_heif_opener()
    _HAVE_HEIF = True
except Exception:
    _HAVE_HEIF = False  # keep boolean consistent

# Optional SVG rasterizer
_HAVE_CAIROSVG = False
try:
    import cairosvg  # pip install cairosvg
    _HAVE_CAIROSVG = True
except Exception:
    _HAVE_CAIROSVG = False

# ============== Utils ==============

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def _unique_name(prefix: str, ext: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}{ext}"

def _open_image_normalized(in_path: str) -> Image.Image:
    """
    Open image with EXIF orientation fixed; returns a Pillow Image.
    SVG files are rasterized to PNG bytes (if CairoSVG available) before open.
    """
    ext = Path(in_path).suffix.lower()
    if ext == ".svg":
        if not _HAVE_CAIROSVG:
            raise RuntimeError("SVG input requires CairoSVG. Install with: pip install cairosvg")
        png_bytes = cairosvg.svg2png(url=in_path)
        im = Image.open(io.BytesIO(png_bytes))
    else:
        im = Image.open(in_path)
    try:
        im = ImageOps.exif_transpose(im)
    except Exception:
        pass
    return im

def _flatten_if_needed(im: Image.Image, bg=(255, 255, 255)) -> Image.Image:
    if im.mode in ("RGBA", "LA"):
        base = Image.new("RGB", im.size, bg)
        base.paste(im.convert("RGBA"), mask=im.split()[-1])
        return base
    if im.mode == "P" and "transparency" in im.info:
        return im.convert("RGBA").convert("RGB")
    if im.mode == "CMYK":
        return im.convert("RGB")
    return im

def _is_animated(im: Image.Image) -> bool:
    try:
        return getattr(im, "is_animated", False) and im.n_frames > 1
    except Exception:
        return False

def _ext_to_format(ext: str) -> str:
    ext = ext.lower().lstrip(".")
    mapping = {
        "jpg": "JPEG", "jpeg": "JPEG",
        "png": "PNG",
        "webp": "WEBP",
        "tif": "TIFF", "tiff": "TIFF",
        "bmp": "BMP",
        "gif": "GIF",
        "ico": "ICO",
        "ppm": "PPM", "pgm": "PPM", "pbm": "PPM", "pnm": "PPM",
        "qoi": "QOI",
        "heic": "HEIF", "heif": "HEIF", "avif": "HEIF",  # via pillow-heif
        "pdf": "PDF"
    }
    return mapping.get(ext, ext.upper())

def supported_inputs() -> List[str]:
    """
    Common formats supported by Pillow (+ optional plugins).
    """
    exts = [
        ".jpg", ".jpeg", ".png", ".webp",
        ".bmp", ".gif", ".ico",
        ".ppm", ".pgm", ".pbm", ".pnm", ".qoi",
        ".tif", ".tiff"  # keep internally supported; UI can hide
    ]
    if _HAVE_HEIF:
        exts += [".heic", ".heif", ".avif"]
    if _HAVE_CAIROSVG:
        exts += [".svg"]
    return exts

# ============== Generic any -> any ==============

def convert_image(
    in_path: str,
    out_path: str,
    *,
    quality: int = 90,
    background: Tuple[int, int, int] = (255, 255, 255),
    keep_animation: bool = True,
    webp_lossless: bool = False,
    tiff_compression: str = "tiff_deflate",
    ico_sizes: Optional[List[Tuple[int, int]]] = None
):
    """
    Convert any supported image to target format inferred from out_path.
    """
    _ensure_dir(Path(out_path).parent.as_posix())
    target_ext = Path(out_path).suffix.lower().lstrip(".")
    target_fmt = _ext_to_format(target_ext)

    with _open_image_normalized(in_path) as im:
        # Animated sequence?
        if _is_animated(im) and keep_animation and target_fmt in ("GIF", "WEBP", "TIFF"):
            frames = []
            durations = []
            try:
                for frame in ImageSequence.Iterator(im):
                    frame = ImageOps.exif_transpose(frame)
                    if target_fmt == "GIF":
                        fr = frame.convert("RGBA").convert("RGB")
                    else:
                        fr = frame.convert("RGBA")
                    frames.append(fr)
                try:
                    for i in range(im.n_frames):
                        im.seek(i)
                        durations.append(im.info.get("duration", 100))
                except Exception:
                    durations = [4] * len(frames)
            except Exception:
                frames = [im.convert("RGBA")]
                durations = [4]

            save_kwargs = {}
            if target_fmt == "GIF":
                save_kwargs.update(dict(save_all=True, loop=0, duration=durations))
            elif target_fmt == "WEBP":
                save_kwargs.update(dict(save_all=True, quality=quality, lossless=webp_lossless, method=6))
            elif target_fmt == "TIFF":
                save_kwargs.update(dict(save_all=True, compression=tiff_compression))

            frames.save(out_path, target_fmt, append_images=frames[1:] if len(frames) > 1 else None, **save_kwargs)
            return out_path

        # Static image
        if target_fmt in ("JPEG", "ICO"):
            im = _flatten_if_needed(im, bg=background)
        else:
            if im.mode not in ("RGB", "RGBA", "L"):
                im = im.convert("RGBA" if target_fmt in ("PNG", "WEBP", "TIFF") else "RGB")

        if target_fmt == "JPEG":
            im = im.convert("RGB")
            im.save(out_path, target_fmt, quality=quality, optimize=True, progressive=True)
        elif target_fmt == "PNG":
            im.save(out_path, target_fmt, optimize=True)
        elif target_fmt == "WEBP":
            im.save(out_path, target_fmt, quality=quality, lossless=webp_lossless, method=6)
        elif target_fmt == "TIFF":
            im.save(out_path, target_fmt, compression=tiff_compression)
        elif target_fmt == "ICO":
            sizes = ico_sizes or [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
            icons = []
            for w, h in sizes:
                tmp = im.copy()
                tmp = ImageOps.fit(tmp, (w, h), method=Image.Resampling.LANCZOS)
                icons.append(tmp)
            icons.save(out_path, target_fmt, sizes=sizes)
        elif target_fmt == "PDF":
            im2 = im.convert("RGB") if im.mode != "RGB" else im
            im2.save(out_path, "PDF", resolution=150.0)
        else:
            im.save(out_path, target_fmt)
    return out_path

# Convenience wrappers (kept for compatibility)

def jpg_to_png(in_path: str, out_path: str):
    return convert_image(in_path, out_path)

def png_to_jpg(in_path: str, out_path: str, quality: int = 90, background: Tuple[int, int, int] = (255, 255, 255), progressive: bool = True):
    return convert_image(in_path, out_path, quality=quality, background=background)

def image_to_pdf(in_path: str, out_path: str, dpi: int = 150):
    return images_to_pdf([in_path], out_path, dpi=dpi)

# ============== Images <-> PDF ==============

def images_to_pdf(in_paths: List[str], out_path: str, dpi: int = 150):
    if not in_paths:
        raise ValueError("No input images provided")
    _ensure_dir(Path(out_path).parent.as_posix())

    imgs = []
    try:
        for p in in_paths:
            with _open_image_normalized(p) as im:
                imgs.append((im.convert("RGB")).copy())
        first, rest = imgs, imgs[1:]
        first.save(out_path, "PDF", resolution=float(dpi), save_all=True, append_images=rest)
    finally:
        for im in imgs:
            try:
                im.close()
            except Exception:
                pass
    return out_path

def pdf_to_images(in_path: str, out_dir: str, dpi: int = 150, fmt: str = "png"):
    _ensure_dir(out_dir)
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(in_path)
        try:
            out_files = []
            zoom = dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)
            for i, page in enumerate(doc, start=1):
                pix = page.get_pixmap(matrix=mat, alpha=False)
                op = os.path.join(out_dir, f"page_{i}.{fmt}")
                pix.save(op)
                out_files.append(op)
            return out_files
        finally:
            doc.close()
    except Exception:
        pass

    try:
        import pdf2image
        images = pdf2image.convert_from_path(in_path, dpi=dpi)
        out_files = []
        for i, im in enumerate(images, start=1):
            op = os.path.join(out_dir, f"page_{i}.{fmt}")
            im.save(op, format=fmt.upper())
            out_files.append(op)
        return out_files
    except Exception as e:
        raise RuntimeError(f"PDF to images failed (need PyMuPDF or pdf2image+Poppler): {e}")

# ============== Batch helpers ==============

def batch_convert(in_paths: List[str], out_dir: str, target_ext: str, **kwargs) -> List[str]:
    if not in_paths:
        raise ValueError("No input images provided")
    _ensure_dir(out_dir)
    target_ext = target_ext if target_ext.startswith(".") else f".{target_ext}"
    outs = []
    for p in in_paths:
        base = Path(p).stem
        op = os.path.join(out_dir, f"{base}{target_ext}")
        convert_image(p, op, **kwargs)
        outs.append(op)
    return outs

# ============== Class wrapper ==============

class ImageConverters:
    def __init__(self, output_dir: Optional[str] = None):
        if output_dir:
            self.output_dir = output_dir
            _ensure_dir(self.output_dir)
            self._owns_dir = False
        else:
            self.output_dir = os.path.join(os.getcwd(), f"images_{uuid.uuid4().hex}")
            _ensure_dir(self.output_dir)
            self._owns_dir = True

    def convert_any(self, in_path: str, out_ext: str, **kwargs) -> str:
        out_ext = out_ext if out_ext.startswith(".") else f".{out_ext}"
        out = os.path.join(self.output_dir, f"converted{out_ext}")
        convert_image(in_path, out, **kwargs)
        return out

    def images_to_pdf(self, file_paths: List[str]) -> str:
        out = os.path.join(self.output_dir, "images.pdf")
        return images_to_pdf(file_paths, out)
