# app.py - Complete Updated Version (FIXED)
from rembg import remove
from PIL import Image
import os, shutil, uuid, tempfile, zipfile
from datetime import datetime
from functools import wraps

from flask import (
    Flask, request, render_template, jsonify, send_file,
    redirect, url_for, flash
)
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

# Import your converters
from converters import (
    pdf_tools, document_converters, image_converters,
    media_converters, archive_converters, data_converters
)

# ============== FLASK APP INITIALIZATION (MOVED TO TOP) ==============
app = Flask(__name__)
app.config.update(
    SECRET_KEY="universal-file-converter-2025",
    MAX_CONTENT_LENGTH=500*1024*1024  # 500 MB
)

# Paths
BASE = os.path.dirname(__file__)
UPLOAD = os.path.join(BASE, "uploads")
OUTPUT = os.path.join(BASE, "outputs") 
TEMP = os.path.join(BASE, "temp")
for d in (UPLOAD, OUTPUT, TEMP): os.makedirs(d, exist_ok=True)

# Stats tracking
STATS = dict(total_conversions=0, total_files_processed=0, start=datetime.now())

# Helper functions
def jerr(msg, code=400): return jsonify(error=msg), code
def unique(pref, ext): return f"{pref}_{uuid.uuid4().hex}{ext}"

def save(f, exts=None):
    if not f or not f.filename: raise RuntimeError("No file provided")
    name = secure_filename(f.filename); ext = os.path.splitext(name)[1].lower()
    if exts and ext not in exts: raise RuntimeError(f"Unsupported {ext}")
    p = os.path.join(UPLOAD, f"{uuid.uuid4().hex}_{name}"); f.save(p)
    STATS["total_files_processed"] += 1; return p

def clean(p): 
    try: shutil.rmtree(p, ignore_errors=True) if os.path.isdir(p) else os.remove(p)
    except Exception: pass

def safe(fn):
    @wraps(fn)
    def wrap(*a, **kw):
        try: return fn(*a, **kw)
        except RuntimeError as e: return jerr(str(e), 400)
        except Exception as e: app.logger.exception(e); return jerr(str(e), 500)
    return wrap

# Tools Data (same as your old TOOLS_DATA)
TOOLS_DATA = {
    'pdf': {
        'title': 'PDF Tools',
        'icon': 'fas fa-file-pdf',
        'color': '#dc2626',
        'description': 'Professional PDF editing and conversion tools',
        'tools': [
            {
                'id': 'merge-pdf',
                'name': 'Merge PDFs',
                'description': 'Combine multiple PDF files into one document',
                'endpoint': '/pdf/merge',
                'input_type': 'multiple',
                'accept': '.pdf',
                'min_files': 2
            },
            {
                'id': 'split-pdf',
                'name': 'Split PDF',
                'description': 'Split PDF into individual pages',
                'endpoint': '/pdf/split',
                'input_type': 'single',
                'accept': '.pdf'
            },
            {
                'id': 'compress-pdf',
                'name': 'Compress PDF',
                'description': 'Reduce PDF file size',
                'endpoint': '/pdf/compress',
                'input_type': 'single',
                'accept': '.pdf'
            },
            {
                'id': 'rotate-pdf',
                'name': 'Rotate PDF',
                'description': 'Rotate PDF pages',
                'endpoint': '/pdf/rotate',
                'input_type': 'single',
                'accept': '.pdf',
                'options': [
                    {'name': 'angle', 'label': 'Rotation Angle', 'type': 'select', 'options_list': [90, 180, 270]}
                ]
            },
            {
                'id': 'watermark-pdf',
                'name': 'Add Watermark',
                'description': 'Add text watermark to PDF',
                'endpoint': '/pdf/watermark',
                'input_type': 'single',
                'accept': '.pdf',
                'options': [
                    {'name': 'watermark_text', 'label': 'Watermark Text', 'type': 'text', 'placeholder': 'CONFIDENTIAL'}
                ]
            }
        ]
    },
    'document': {
        'title': 'Document Tools',
        'icon': 'fas fa-file-word',
        'color': '#2563eb',
        'description': 'Convert between popular document formats',
        'tools': [
            {
                'id': 'pdf-to-word',
                'name': 'PDF → Word',
                'description': 'Convert PDF to editable Word format',
                'endpoint': '/convert/pdf/docx',
                'input_type': 'single',
                'accept': '.pdf'
            },
            {
                'id': 'word-to-pdf',
                'name': 'Word → PDF',
                'description': 'Convert Word to PDF format',
                'endpoint': '/convert/docx/pdf',
                'input_type': 'single',
                'accept': '.docx,.doc'
            },
            {
                'id': 'html-to-pdf',
                'name': 'HTML → PDF',
                'description': 'Convert web pages to PDF format',
                'endpoint': '/document/html-to-pdf',
                'input_type': 'single',
                'accept': '.html,.htm'
            },
            {
                'id': 'txt-to-pdf',
                'name': 'Text → PDF',
                'description': 'Convert plain text to PDF',
                'endpoint': '/document/txt-to-pdf',
                'input_type': 'single',
                'accept': '.txt',
                'options': [
                    {'name': 'font_size', 'label': 'Font Size', 'type': 'select', 'options_list': [10, 12, 14, 16, 18]}
                ]
            },
            {
                'id': 'merge-word',
                'name': 'Merge Word Docs',
                'description': 'Combine multiple Word documents',
                'endpoint': '/document/merge-word',
                'input_type': 'multiple',
                'accept': '.docx,.doc',
                'min_files': 2
            }
        ]
    },
    'image': {
        'title': 'Image Tools',
        'icon': 'fas fa-image',
        'color': '#059669',
        'description': 'Transform images between formats',
        'tools': [
            {
                'id': 'remove-bg',
                'name': 'Remove Background',
                'description': 'Remove background from photos automatically',
                'endpoint': '/image/remove-background',
                'input_type': 'single',
                'accept': '.jpg,.jpeg,.png,.bmp'
            },
            {
                'id': 'image-any-any',
                'name': 'Convert Format',
                'description': 'Convert between image formats',
                'endpoint': '/image/convert/any',
                'input_type': 'single',
                'accept': '.jpg,.jpeg,.png,.webp,.bmp,.tiff',
                'options': [
                    {'name': 'target', 'label': 'Target Format', 'type': 'select', 'options_list': ['jpg', 'png', 'webp', 'pdf']}
                ]
            }
        ]
    },
    'archive': {
        'title': 'Archive Tools',
        'icon': 'fas fa-file-archive',
        'color': '#ea580c',
        'description': 'Create, extract and convert archive formats',
        'tools': [
            {
                'name': 'Create ZIP Archive',
                'description': 'Create password-protected ZIP from multiple files',
                'endpoint': '/archive/create-zip',
                'input_type': 'multiple',
                'accept': '*',
                'options': [
                    {'name': 'password', 'label': 'Password (Optional)', 'type': 'password'},
                    {'name': 'compression', 'label': 'Compression Level', 'type': 'select',
                     'options_list': [1, 3, 5, 6, 9]}
                ]
            },
            {
                'name': 'Extract Archive',
                'description': 'Extract ZIP, RAR, 7Z archives',
                'endpoint': '/archive/extract',
                'input_type': 'single',
                'accept': '.zip,.rar,.7z,.tar,.gz',
                'options': [
                    {'name': 'password', 'label': 'Password (if needed)', 'type': 'password'}
                ]
            },
            {
                'name': 'Convert Archive Format',
                'description': 'Convert between ZIP, RAR, 7Z formats',
                'endpoint': '/archive/convert-format',
                'input_type': 'single',
                'accept': '.zip,.rar,.7z',
                'options': [
                    {'name': 'target_format', 'label': 'Target Format', 'type': 'select',
                     'options_list': ['zip', '7z', 'rar']},
                    {'name': 'password', 'label': 'Password (Optional)', 'type': 'password'},
                    {'name': 'compression', 'label': 'Compression', 'type': 'select',
                     'options_list': [1, 3, 5, 7, 9]}
                ]
            },
            {
                'name': 'Analyze Archive',
                'description': 'Get compression statistics and file list',
                'endpoint': '/archive/analyze',
                'input_type': 'single',
                'accept': '.zip,.rar,.7z'
            }
        ]
    },
    'data': {
        'title': 'Data Converters',
        'icon': 'fas fa-database',
        'color': '#0891b2',
        'description': 'Transform data between formats',
        'tools': [
            {
                'name': 'JSON → CSV',
                'description': 'Convert JSON data to CSV format',
                'endpoint': '/data/json-to-csv',
                'input_type': 'single',
                'accept': '.json'
            },
            {
                'name': 'CSV → JSON',
                'description': 'Convert CSV to JSON with options',
                'endpoint': '/data/csv-to-json',
                'input_type': 'single',
                'accept': '.csv',
                'options': [
                    {'name': 'orient', 'label': 'JSON Structure', 'type': 'select',
                     'options_list': ['records', 'values', 'index']}
                ]
            },
            {
                'name': 'Excel → JSON',
                'description': 'Convert Excel sheets to JSON',
                'endpoint': '/data/excel-to-json',
                'input_type': 'single',
                'accept': '.xlsx,.xls',
                'options': [
                    {'name': 'sheet_name', 'label': 'Sheet Name (Optional)', 'type': 'text'}
                ]
            },
            {
                'name': 'JSON → Excel',
                'description': 'Convert JSON to Excel format',
                'endpoint': '/data/json-to-excel',
                'input_type': 'single',
                'accept': '.json',
                'options': [
                    {'name': 'sheet_name', 'label': 'Sheet Name', 'type': 'text', 'placeholder': 'Data'}
                ]
            },
            {
                'name': 'Analyze Data Structure',
                'description': 'Get insights about your data file',
                'endpoint': '/data/analyze-structure',
                'input_type': 'single',
                'accept': '.json,.csv,.xlsx,.xml'
            }
        ]
    }
}

# ============== MAIN ROUTE ==============
@app.route("/")  # FIXED: Use @app.route instead of @app.get
def home():
    dashboard_stats = {
        'total_tools': sum(len(cat['tools']) for cat in TOOLS_DATA.values()),
        'total_categories': len(TOOLS_DATA),
        'total_conversions': STATS["total_conversions"],
        'total_files': STATS["total_files_processed"],
        'uptime_days': (datetime.now() - STATS["start"]).days
    }
    return render_template("index.html", 
                         tools_data=TOOLS_DATA, 
                         dashboard_stats=dashboard_stats)

# ============== PDF ROUTES ==============
@app.route("/pdf/merge", methods=['POST'])  # FIXED: Use @app.route with methods
@safe
def pdf_merge():
    files = request.files.getlist("files")
    if len(files) < 2: return jerr("Need ≥2 PDFs")
    paths=[save(f,{'.pdf'}) for f in files]
    out=os.path.join(OUTPUT,unique("merged",".pdf"))
    pdf_tools.merge_pdfs(paths,out)
    for p in paths: clean(p)
    STATS["total_conversions"] += 1
    return send_file(out, as_attachment=True, download_name="merged.pdf")

@app.route("/pdf/split", methods=['POST'])  # FIXED
@safe
def pdf_split():
    f=request.files.get("file"); src=save(f,{'.pdf'})
    tmp=tempfile.mkdtemp(dir=TEMP); pages=pdf_tools.split_pdf(src,tmp)
    zpath=os.path.join(OUTPUT,unique("split",".zip"))
    with zipfile.ZipFile(zpath,'w') as z:
        [z.write(p,os.path.basename(p)) for p in pages]
    clean(tmp); clean(src); STATS["total_conversions"]+=1
    return send_file(zpath,as_attachment=True,download_name="pages.zip")

@app.route("/pdf/compress", methods=['POST'])  # FIXED
@safe
def pdf_compress():
    f=request.files.get("file"); src=save(f,{'.pdf'})
    quality=request.form.get("quality","medium").lower()
    out=os.path.join(OUTPUT,unique("compressed",".pdf"))
    pdf_tools.compress_pdf(src,out,quality=quality)
    clean(src); STATS["total_conversions"]+=1
    return send_file(out,as_attachment=True,download_name="compressed.pdf")

@app.route("/pdf/rotate", methods=['POST'])  # FIXED
@safe
def pdf_rotate():
    f=request.files.get("file"); src=save(f,{'.pdf'})
    try: ang=int(request.form.get("angle",90)); ang=ang if ang in (90,180,270) else 90
    except: ang=90
    out=os.path.join(OUTPUT,unique("rotated",".pdf"))
    pdf_tools.rotate_pdf(src,out,angle=ang)
    clean(src); STATS["total_conversions"]+=1
    return send_file(out,as_attachment=True,download_name="rotated.pdf")

@app.route("/pdf/watermark", methods=['POST'])  # FIXED
@safe
def pdf_watermark():
    f=request.files.get("file"); src=save(f,{'.pdf'})
    text=request.form.get("watermark_text","CONFIDENTIAL")
    rot=int(request.form.get("rotation",0) or 0)
    out=os.path.join(OUTPUT,unique("watermarked",".pdf"))
    pdf_tools.watermark_text(src,out,text,rotation=rot)
    clean(src); STATS["total_conversions"]+=1
    return send_file(out,as_attachment=True,download_name="watermarked.pdf")

# ============== IMAGE ROUTES ==============
@app.route("/image/convert/any", methods=['POST'])  # FIXED
@safe
def image_convert():
    f=request.files.get("file"); src=save(f)
    target=(request.form.get("target") or "").strip().lower().lstrip(".")
    if not target: return jerr("Target format required")
    out=os.path.join(OUTPUT,unique("converted",f".{target}"))
    image_converters.convert_image(src,out)
    clean(src); STATS["total_conversions"]+=1
    return send_file(out,as_attachment=True,download_name=f"converted.{target}")

@app.route("/image/remove-background", methods=['POST'])  # FIXED
@safe
def image_remove_background():
    f = request.files.get("file")
    src = save(f, {'.jpg', '.jpeg', '.png', '.bmp'})
    # Use rembg for background removal
    input_image = Image.open(src)
    output_image = remove(input_image)
    out = os.path.join(OUTPUT, unique("bg_removed", ".png"))
    output_image.save(out, "PNG")
    clean(src)
    STATS["total_conversions"] += 1
    return send_file(out, as_attachment=True, download_name="background_removed.png")

# ============== DOCUMENT ROUTES ==============
@app.route("/convert/pdf/docx", methods=['POST'])  # FIXED
@safe
def pdf_to_word():
    f=request.files.get("file"); src=save(f,{'.pdf'})
    out=os.path.join(OUTPUT,unique("converted",".docx"))
    document_converters.pdf_to_docx(src,out)
    clean(src); STATS["total_conversions"]+=1
    return send_file(out,as_attachment=True,download_name="converted.docx")

@app.route("/convert/docx/pdf", methods=['POST'])  # FIXED
@safe
def word_to_pdf():
    f=request.files.get("file"); src=save(f,{'.docx','.doc'})
    out=os.path.join(OUTPUT,unique("converted",".pdf"))
    document_converters.docx_to_pdf(src,out)
    clean(src); STATS["total_conversions"]+=1
    return send_file(out,as_attachment=True,download_name="converted.pdf")

@app.route("/document/html-to-pdf", methods=['POST'])  # FIXED
@safe
def html_to_pdf_route():
    f = request.files.get("file")
    src = save(f, {'.html', '.htm'})
    out = os.path.join(OUTPUT, unique("converted", ".pdf"))
    document_converters.html_to_pdf(src, out)
    clean(src); STATS["total_conversions"] += 1
    return send_file(out, as_attachment=True, download_name="converted.pdf")

@app.route("/document/txt-to-pdf", methods=['POST'])  # FIXED
@safe
def txt_to_pdf_route():
    f = request.files.get("file")
    font_size = int(request.form.get("font_size", 12))
    src = save(f, {'.txt'})
    out = os.path.join(OUTPUT, unique("converted", ".pdf"))
    document_converters.txt_to_pdf(src, out, font_size=font_size)
    clean(src); STATS["total_conversions"] += 1
    return send_file(out, as_attachment=True, download_name="converted.pdf")

@app.route("/document/merge-word", methods=['POST'])  # FIXED
@safe
def merge_word_route():
    files = request.files.getlist("files")
    if len(files) < 2: return jerr("Need ≥2 Word documents")
    paths = [save(f, {'.docx', '.doc'}) for f in files]
    out = os.path.join(OUTPUT, unique("merged", ".docx"))
    document_converters.merge_word_documents(paths, out)
    for p in paths: clean(p)
    STATS["total_conversions"] += 1
    return send_file(out, as_attachment=True, download_name="merged.docx")

# ============== DATA ROUTES ==============
@app.route("/data/json-to-csv", methods=['POST'])  # FIXED
@safe
def json_to_csv_route():
    f = request.files.get("file")
    src = save(f, {'.json'})
    out = os.path.join(OUTPUT, unique("converted", ".csv"))
    data_converters.json_to_csv(src, out)
    clean(src); STATS["total_conversions"] += 1
    return send_file(out, as_attachment=True, download_name="converted.csv")

@app.route("/data/csv-to-json", methods=['POST'])  # FIXED
@safe
def csv_to_json_route():
    f = request.files.get("file")
    orient = request.form.get("orient", "records")
    src = save(f, {'.csv'})
    out = os.path.join(OUTPUT, unique("converted", ".json"))
    data_converters.csv_to_json(src, out, orient=orient)
    clean(src); STATS["total_conversions"] += 1
    return send_file(out, as_attachment=True, download_name="converted.json")

@app.route("/data/excel-to-json", methods=['POST'])  # FIXED
@safe
def excel_to_json_route():
    f = request.files.get("file")
    sheet_name = request.form.get("sheet_name", "").strip() or None
    src = save(f, {'.xlsx', '.xls'})
    out = os.path.join(OUTPUT, unique("converted", ".json"))
    data_converters.excel_to_json(src, out, sheet_name=sheet_name)
    clean(src); STATS["total_conversions"] += 1
    return send_file(out, as_attachment=True, download_name="converted.json")

@app.route("/data/json-to-excel", methods=['POST'])  # FIXED
@safe
def json_to_excel_route():
    f = request.files.get("file")
    sheet_name = request.form.get("sheet_name", "Data")
    src = save(f, {'.json'})
    out = os.path.join(OUTPUT, unique("converted", ".xlsx"))
    data_converters.json_to_excel(src, out, sheet_name=sheet_name)
    clean(src); STATS["total_conversions"] += 1
    return send_file(out, as_attachment=True, download_name="converted.xlsx")

@app.route("/data/analyze-structure", methods=['POST'])  # FIXED
@safe
def analyze_data_route():
    f = request.files.get("file")
    src = save(f, {'.json', '.csv', '.xlsx', '.xml'})
    analysis = data_converters.analyze_data_structure(src)
    clean(src)
    return jsonify(analysis)

# ============== ARCHIVE ROUTES ==============
@app.route("/archive/create-zip", methods=['POST'])  # FIXED
@safe
def create_zip_archive():
    files = request.files.getlist("files")
    password = request.form.get("password", "").strip()
    compression = int(request.form.get("compression", 6))
    
    if not files:
        return jerr("No files provided")
    
    # Save files to temp directory
    temp_dir = tempfile.mkdtemp()
    for f in files:
        file_path = os.path.join(temp_dir, secure_filename(f.filename))
        f.save(file_path)
    
    # Create ZIP
    out_path = os.path.join(OUTPUT, unique("archive", ".zip"))
    if password:
        archive_converters.create_password_protected_zip(temp_dir, out_path, password, compression)
    else:
        archive_converters._zip_directory(temp_dir, out_path, compress=True)
    
    shutil.rmtree(temp_dir)
    STATS["total_conversions"] += 1
    return send_file(out_path, as_attachment=True, download_name="archive.zip")

@app.route("/archive/extract", methods=['POST'])  # FIXED
@safe  
def extract_archive_route():
    f = request.files.get("file")
    password = request.form.get("password", "").strip() or None
    
    src = save(f, {'.zip', '.rar', '.7z', '.tar', '.gz'})
    
    # Extract to temp directory
    extract_dir = tempfile.mkdtemp()
    archive_converters.extract_archive(src, extract_dir, password)
    
    # Create ZIP of extracted files for download
    out_path = os.path.join(OUTPUT, unique("extracted", ".zip"))
    archive_converters._zip_directory(extract_dir, out_path)
    
    clean(src)
    shutil.rmtree(extract_dir)
    STATS["total_conversions"] += 1
    return send_file(out_path, as_attachment=True, download_name="extracted.zip")

@app.route("/archive/convert-format", methods=['POST'])  # FIXED
@safe
def convert_archive_format_route():
    f = request.files.get("file")
    target_format = request.form.get("target_format", "zip").lower()
    password = request.form.get("password", "").strip() or None
    compression = int(request.form.get("compression", 5))
    
    src = save(f, {'.zip', '.rar', '.7z'})
    out_path = os.path.join(OUTPUT, unique("converted", f".{target_format}"))
    
    archive_converters.convert_archive_format(src, out_path, password, compression)
    
    clean(src)
    STATS["total_conversions"] += 1
    return send_file(out_path, as_attachment=True, download_name=f"converted.{target_format}")

@app.route("/archive/analyze", methods=['POST'])  # FIXED
@safe
def analyze_archive_route():
    f = request.files.get("file")
    src = save(f, {'.zip', '.rar', '.7z'})
    
    info = archive_converters.analyze_archive_info(src)
    clean(src)
    
    return jsonify(info)

# ============== ERROR HANDLERS ==============
@app.errorhandler(RequestEntityTooLarge)
def big_file(_): return jerr("Max 500 MB allowed", 413)
@app.errorhandler(404)
def _404(_): return jerr("Not found", 404)
@app.errorhandler(500)
def _500(_): return jerr("Server error", 500)

# ============== RUN APPLICATION ==============
if __name__ == "__main__":
    print("🚀 Universal-Converter running → http://127.0.0.1:5000")
    app.run(debug=True)
