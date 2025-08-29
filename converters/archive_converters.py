import os
import sys
import shutil
import zipfile
import tarfile
import tempfile
import subprocess
from pathlib import Path

try:
    import rarfile  # pip install rarfile (requires unrar/bsdtar/unar in PATH)
except ImportError:
    rarfile = None


# ------------- Utilities -------------

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def _detect_tool(candidates):
    """
    Return first available executable name/path from candidates list using PATH lookup.
    """
    from shutil import which
    for name in candidates:
        p = which(name)
        if p:
            return p
    return None


def _zip_directory(src_dir: str, out_zip_path: str, compress=True):
    _ensure_dir(Path(out_zip_path).parent)
    compression = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    with zipfile.ZipFile(out_zip_path, "w", compression=compression) as zf:
        for root, _, files in os.walk(src_dir):
            for f in files:
                full = os.path.join(root, f)
                arc = os.path.relpath(full, src_dir)
                zf.write(full, arcname=arc)
    return out_zip_path

# --- Enhanced archive utility functions ---
import py7zr  # pip install py7zr

def create_7z_archive(src_dir: str, out_7z_path: str, password: str = None, compression_level: int = 5):
    """Create 7Z archive with optional password and compression level"""
    _ensure_dir(Path(out_7z_path).parent)
    filters = [{"id": py7zr.FILTER_LZMA2, "preset": compression_level}]
    with py7zr.SevenZipFile(out_7z_path, 'w', password=password, filters=filters) as archive:
        archive.writeall(src_dir, os.path.basename(src_dir))
    return out_7z_path

def extract_7z_archive(archive_path: str, out_dir: str, password: str = None):
    """Extract 7Z archive with password support"""
    _ensure_dir(out_dir)
    with py7zr.SevenZipFile(archive_path, mode='r', password=password) as archive:
        archive.extractall(path=out_dir)
    return out_dir

def create_password_protected_zip(src_dir: str, out_zip_path: str, password: str, compression_level: int = 6):
    """Create password-protected ZIP with compression levels"""
    import pyminizip  # pip install pyminizip
    _ensure_dir(Path(out_zip_path).parent)
    # Get all files in directory
    file_list = []
    prefix_list = []
    for root, dirs, files in os.walk(src_dir):
        for file in files:
            file_path = os.path.join(root, file)
            arc_name = os.path.relpath(file_path, src_dir)
            file_list.append(file_path)
            prefix_list.append(arc_name)
    # Create password-protected ZIP
    pyminizip.compress_multiple(file_list, prefix_list, out_zip_path, password, compression_level)
    return out_zip_path

# Alternative password ZIP using zipfile + subprocess
def create_password_zip_alternative(src_dir: str, out_zip_path: str, password: str):
    """Create password-protected ZIP using 7z command line"""
    sevenz = _detect_tool(["7z", "7za", "7zz"])
    if not sevenz:
        raise RuntimeError("7-Zip required for password-protected archives")
    cmd = [sevenz, "a", "-tzip", f"-p{password}", out_zip_path, f"{src_dir}/*"]
    subprocess.run(cmd, check=True)
    return out_zip_path

def split_archive(archive_path: str, part_size_mb: int = 10):
    """Split large archive into smaller parts"""
    part_size = part_size_mb * 1024 * 1024  # Convert to bytes
    base_name = os.path.splitext(archive_path)[0]
    part_files = []
    with open(archive_path, 'rb') as source:
        part_num = 1
        while True:
            chunk = source.read(part_size)
            if not chunk:
                break
            part_path = f"{base_name}.{part_num:03d}"
            with open(part_path, 'wb') as part_file:
                part_file.write(chunk)
            part_files.append(part_path)
            part_num += 1
    return part_files

def merge_archive_parts(part_files: list, output_path: str):
    """Merge split archive parts back into single file"""
    _ensure_dir(Path(output_path).parent)
    with open(output_path, 'wb') as output:
        for part_file in sorted(part_files):
            with open(part_file, 'rb') as part:
                shutil.copyfileobj(part, output)
    return output_path

def convert_archive_format(input_path: str, output_path: str, password: str = None, compression_level: int = 5):
    """Convert between different archive formats"""
    input_ext = Path(input_path).suffix.lower()
    output_ext = Path(output_path).suffix.lower()
    # Extract to temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        extract_dir = os.path.join(temp_dir, "extracted")
        # Extract based on input format
        if input_ext == '.zip':
            extract_archive(input_path, extract_dir, password)
        elif input_ext == '.rar':
            extract_archive(input_path, extract_dir, password)
        elif input_ext == '.7z':
            extract_7z_archive(input_path, extract_dir, password)
        else:
            raise ValueError(f"Unsupported input format: {input_ext}")
        # Create archive in output format
        if output_ext == '.zip':
            if password:
                return create_password_protected_zip(extract_dir, output_path, password, compression_level)
            else:
                return _zip_directory(extract_dir, output_path, compress=True)
        elif output_ext == '.7z':
            return create_7z_archive(extract_dir, output_path, password, compression_level)
        elif output_ext == '.rar':
            return zip_to_rar(f"{extract_dir}.zip", output_path, password)
        else:
            raise ValueError(f"Unsupported output format: {output_ext}")

def analyze_archive_info(archive_path: str):
    """Analyze archive and return compression statistics"""
    info = {
        'format': Path(archive_path).suffix.lower(),
        'size': os.path.getsize(archive_path),
        'files': [],
        'compression_ratio': 0,
        'total_uncompressed': 0
    }
    try:
        if info['format'] == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zf:
                info['files'] = zf.namelist()
                info['total_uncompressed'] = sum(f.file_size for f in zf.filelist)
        elif info['format'] == '.7z':
            with py7zr.SevenZipFile(archive_path, 'r') as archive:
                info['files'] = archive.getnames()
                # Calculate uncompressed size
                for file_info in archive.list():
                    info['total_uncompressed'] += file_info.uncompressed if file_info.uncompressed else 0
        elif info['format'] == '.rar' and _rarfile_can_extract():
            with rarfile.RarFile(archive_path) as rf:
                info['files'] = rf.namelist()
                info['total_uncompressed'] = sum(f.file_size for f in rf.infolist())
        # Calculate compression ratio
        if info['total_uncompressed'] > 0:
            info['compression_ratio'] = (1 - info['size'] / info['total_uncompressed']) * 100
    except Exception as e:
        info['error'] = str(e)
    return info

def extract_specific_files(archive_path: str, file_list: list, out_dir: str, password: str = None):
    """Extract only specific files from archive without extracting everything"""
    _ensure_dir(out_dir)
    ext = Path(archive_path).suffix.lower()
    if ext == '.zip':
        with zipfile.ZipFile(archive_path, 'r') as zf:
            if password:
                zf.setpassword(password.encode('utf-8'))
            for file_name in file_list:
                if file_name in zf.namelist():
                    zf.extract(file_name, out_dir)
    elif ext == '.7z':
        with py7zr.SevenZipFile(archive_path, 'r', password=password) as archive:
            archive.extract(targets=file_list, path=out_dir)
    elif ext == '.rar' and _rarfile_can_extract():
        with rarfile.RarFile(archive_path) as rf:
            for file_name in file_list:
                if file_name in rf.namelist():
                    rf.extract(file_name, out_dir, pwd=password)
    return out_dir

def _extract_with_7z(archive_path: str, out_dir: str, password: str | None = None):
    """
    Fallback extractor using 7z if installed. Supports many formats including RAR.
    """
    sevenz = _detect_tool(["7z", "7za", "7zz"])  # any 7-Zip CLI
    if not sevenz:
        raise RuntimeError("7-Zip (7z) not found. Install 7-Zip or add it to PATH.")
    cmd = [sevenz, "x", "-y", f"-o{out_dir}", archive_path]
    # 7z password flag
    if password:
        cmd.insert(2, f"-p{password}")
    subprocess.run(cmd, check=True)
    return out_dir

def _rarfile_can_extract():
    if not rarfile:
        return False
    # Try to configure tool for rarfile if env suggests a path
    tool_env = os.environ.get("RARFILE_UNRAR_TOOL") or os.environ.get("UNRAR_PATH")
    if tool_env and os.path.exists(tool_env):
        rarfile.UNRAR_TOOL = tool_env
    # rarfile supports unrar/bsdtar/unar/7z; it will probe PATH
    return True


# ------------- Functional API (recommended) -------------

def rar_to_zip(rar_path: str, out_zip_path: str, password: str | None = None):
    """
    Convert RAR -> ZIP by extracting to temp and rezipping.
    Requires one of:
      - rarfile + (unrar/bsdtar/unar/7z in PATH)
      - or 7z CLI in PATH (fallback)
    """
    if not os.path.exists(rar_path):
        raise FileNotFoundError(rar_path)

    with tempfile.TemporaryDirectory() as tmp:
        extract_dir = os.path.join(tmp, "extracted")
        _ensure_dir(extract_dir)

        extracted = False
        # Try rarfile first
        if _rarfile_can_extract():
            try:
                rf = rarfile.RarFile(rar_path)
                rf.extractall(extract_dir, pwd=password)
                extracted = True
            except Exception as e:
                # fall back to 7z
                extracted = False

        if not extracted:
            _extract_with_7z(rar_path, extract_dir, password=password)

        return _zip_directory(extract_dir, out_zip_path, compress=True)


def zip_to_rar(zip_path: str, out_rar_path: str, password: str | None = None, volume_size: str | None = None):
    """
    Convert ZIP -> RAR using WinRAR/rar.exe. 7z cannot create .rar files.
    - zip_path: input .zip
    - out_rar_path: output .rar (will be overwritten)
    - password: optional RAR archive password
    - volume_size: like '5m' for 5MB volumes (optional)
    """
    if not os.path.exists(zip_path):
        raise FileNotFoundError(zip_path)

    # Find rar CLI
    rar_cli = _detect_tool(["rar", "winrar", "WinRAR"])
    if not rar_cli:
        raise RuntimeError("RAR creation requires WinRAR (rar.exe) in PATH.")

    with tempfile.TemporaryDirectory() as tmp:
        # Extract ZIP to a temp folder
        extract_dir = os.path.join(tmp, "zip_extract")
        _ensure_dir(extract_dir)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)

        # Prepare RAR command: run in extract_dir and add '.'
        cmd = [rar_cli, "a", "-r", "-ep1"]  # -r recurse, -ep1 strip base dir
        if password:
            cmd.append(f"-p{password}")  # rar uses -pPASSWORD
        if volume_size:
            cmd.append(f"-v{volume_size}")  # e.g., -v5m
        cmd.append(out_rar_path)
        cmd.append(".")  # add current directory

        # Run inside the folder so that '.' adds all
        subprocess.run(cmd, check=True, cwd=extract_dir)

    return out_rar_path


def create_archive(files_dir: str, out_path: str):
    """
    Create archive from directory.
    - out_path extension decides format: .zip, .tar, .tar.gz
    """
    ext = Path(out_path).suffix.lower()
    parent = Path(out_path).parent
    _ensure_dir(parent)

    if ext == ".zip":
        return _zip_directory(files_dir, out_path, compress=True)
    elif ext in (".tar", ".gz", ".tgz"):
        mode = "w"
        if ext in (".gz", ".tgz") or out_path.endswith(".tar.gz"):
            mode = "w:gz"
        with tarfile.open(out_path, mode) as tf:
            tf.add(files_dir, arcname=".")
        return out_path
    else:
        raise ValueError(f"Unsupported archive extension: {ext}")


def extract_archive(file_path: str, out_dir: str, password: str | None = None):
    """
    Extract archive into out_dir. Supports: .zip, .tar(.gz), .rar (via rarfile or 7z).
    """
    _ensure_dir(out_dir)
    lower = file_path.lower()

    if lower.endswith(".zip"):
        with zipfile.ZipFile(file_path, "r") as zf:
            # zipfile standard lib supports only plain or traditional ZipCrypto passwords
            if password:
                zf.setpassword(password.encode("utf-8"))
            zf.extractall(out_dir)
        return out_dir

    if lower.endswith(".tar") or lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        with tarfile.open(file_path, "r:*") as tf:
            tf.extractall(out_dir)
        return out_dir

    if lower.endswith(".rar"):
        if _rarfile_can_extract():
            try:
                rf = rarfile.RarFile(file_path)
                rf.extractall(out_dir, pwd=password)
                return out_dir
            except Exception:
                # fallback to 7z below
                pass
        return _extract_with_7z(file_path, out_dir, password=password)

    # Try 7z for other formats (7z, 7zip, etc.)
    try:
        return _extract_with_7z(file_path, out_dir, password=password)
    except Exception:
        raise ValueError(f"Unsupported archive type or missing extractor: {file_path}")


# ------------- Optional class wrapper (backward compatibility) -------------

class ArchiveConverters:
    """
    Backward-compatible wrapper that stores outputs in a temporary folder.
    Use functional API for better control of output paths.
    """
    def __init__(self, output_dir: str | None = None):
        self._owns_dir = False
        if output_dir:
            self.output_dir = output_dir
            _ensure_dir(self.output_dir)
        else:
            self.output_dir = tempfile.mkdtemp(prefix="archives_")
            self._owns_dir = True

    def __del__(self):
        if getattr(self, "_owns_dir", False):
            try:
                shutil.rmtree(self.output_dir, ignore_errors=True)
            except Exception:
                pass

    def rar_to_zip(self, file_path: str, password: str | None = None):
        out_zip = os.path.join(self.output_dir, "converted.zip")
        return rar_to_zip(file_path, out_zip, password=password)

    def zip_to_rar(self, file_path: str, password: str | None = None, volume_size: str | None = None):
        out_rar = os.path.join(self.output_dir, "converted.rar")
        return zip_to_rar(file_path, out_rar, password=password, volume_size=volume_size)

    def create_archive(self, files_dir: str, archive_type: str = 'zip'):
        out_name = f"archive.{archive_type}"
        out_path = os.path.join(self.output_dir, out_name)
        return create_archive(files_dir, out_path)

    def extract_archive(self, file_path: str, password: str | None = None):
        extract_dir = os.path.join(self.output_dir, "extracted")
        return extract_archive(file_path, extract_dir, password=password)
