# converters/media_converters.py - Complete Enhanced Version

import os
import uuid
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple

# Optional imports for enhanced features
try:
    from PIL import Image, ImageOps, ImageEnhance
except ImportError:
    Image = ImageOps = ImageEnhance = None

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def _unique_name(prefix: str, ext: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}{ext}"

def _ffmpeg_path() -> str:
    # 1) Use explicit env override if provided
    p = os.environ.get("FFMPEG_PATH")
    if p and os.path.exists(p):
        return p
    # 2) Try imageio-ffmpeg if available
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    # 3) Fallback: rely on PATH
    return "ffmpeg"

def _run(cmd: List[str]):
    # Pass a list (no shell), capture output only on failure
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}\nError: {e.stderr.decode()}") from e

# ============== AUDIO CONVERSION FUNCTIONS ==============

def mp3_to_wav(in_path: str, out_path: str, sample_rate: int = 44100, channels: int = 2):
    """MP3 -> WAV (PCM s16le)"""
    _ensure_dir(Path(out_path).parent.as_posix())
    cmd = [
        _ffmpeg_path(), "-y",
        "-i", in_path,
        "-vn",
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-c:a", "pcm_s16le",
        out_path
    ]
    _run(cmd)
    return out_path

def wav_to_mp3(in_path: str, out_path: str, bitrate: str = "192k", sample_rate: int = 44100, channels: int = 2):
    """WAV -> MP3 (libmp3lame)"""
    _ensure_dir(Path(out_path).parent.as_posix())
    cmd = [
        _ffmpeg_path(), "-y",
        "-i", in_path,
        "-vn",
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-c:a", "libmp3lame",
        "-b:a", bitrate,
        out_path
    ]
    _run(cmd)
    return out_path

def convert_audio_format(in_path: str, out_path: str, bitrate: str = "192k", sample_rate: int = 44100, channels: int = 2):
    """Universal audio converter - detects format from output extension"""
    _ensure_dir(Path(out_path).parent.as_posix())
    ext = Path(out_path).suffix.lower()
    
    # Select codec based on output format
    if ext == ".mp3":
        codec, extra_flags = "libmp3lame", ["-b:a", bitrate]
    elif ext in [".aac", ".m4a"]:
        codec, extra_flags = "aac", ["-b:a", bitrate]
    elif ext == ".ogg":
        codec, extra_flags = "libvorbis", ["-b:a", bitrate]
    elif ext == ".wav":
        codec, extra_flags = "pcm_s16le", []
    elif ext == ".flac":
        codec, extra_flags = "flac", []
    else:
        codec, extra_flags = "libmp3lame", ["-b:a", bitrate]  # Default to MP3
    
    cmd = [
        _ffmpeg_path(), "-y",
        "-i", in_path,
        "-vn",
        "-ar", str(sample_rate),
        "-ac", str(channels),
        "-c:a", codec,
        *extra_flags,
        out_path
    ]
    _run(cmd)
    return out_path

def extract_audio_from_video(in_path: str, out_path: str, bitrate: str = "192k", sample_rate: int = 44100, channels: int = 2):
    """Extract audio from video file"""
    return convert_audio_format(in_path, out_path, bitrate, sample_rate, channels)

def change_audio_bitrate(in_path: str, out_path: str, bitrate: str = "128k"):
    """Change audio bitrate without changing format"""
    _ensure_dir(Path(out_path).parent.as_posix())
    ext = Path(in_path).suffix.lower()
    
    if ext == ".mp3":
        codec = "libmp3lame"
    elif ext in [".aac", ".m4a"]:
        codec = "aac"
    elif ext == ".ogg":
        codec = "libvorbis"
    else:
        codec = "libmp3lame"  # Default
    
    cmd = [
        _ffmpeg_path(), "-y",
        "-i", in_path,
        "-vn",
        "-c:a", codec,
        "-b:a", bitrate,
        out_path
    ]
    _run(cmd)
    return out_path

# ============== VIDEO CONVERSION FUNCTIONS ==============

def convert_video_format(in_path: str, out_path: str, crf: int = 23, preset: str = "medium", audio_bitrate: str = "128k"):
    """Universal video converter - detects format from output extension"""
    _ensure_dir(Path(out_path).parent.as_posix())
    ext = Path(out_path).suffix.lower()
    
    # Base command
    cmd = [
        _ffmpeg_path(), "-y",
        "-i", in_path,
    ]
    
    # Video codec selection based on output format
    if ext == ".mp4":
        cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", preset, "-pix_fmt", "yuv420p"]
    elif ext == ".avi":
        cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", preset]
    elif ext == ".mkv":
        cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", preset]
    elif ext == ".mov":
        cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", preset, "-pix_fmt", "yuv420p"]
    elif ext == ".webm":
        cmd += ["-c:v", "libvpx-vp9", "-crf", str(crf), "-b:v", "0"]
    else:
        cmd += ["-c:v", "libx264", "-crf", str(crf), "-preset", preset]  # Default H.264
    
    # Audio settings
    if ext == ".webm":
        cmd += ["-c:a", "libvorbis", "-b:a", audio_bitrate]
    else:
        cmd += ["-c:a", "aac", "-b:a", audio_bitrate]
    
    # Output-specific flags
    if ext == ".mp4":
        cmd += ["-movflags", "+faststart"]
    
    cmd.append(out_path)
    _run(cmd)
    return out_path

def compress_video(in_path: str, out_path: str, crf: int = 28, preset: str = "medium", audio_bitrate: Optional[str] = None):
    """Re-encode to smaller size using CRF (quality-based)"""
    _ensure_dir(Path(out_path).parent.as_posix())
    cmd = [
        _ffmpeg_path(), "-y",
        "-i", in_path,
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", preset,
        "-pix_fmt", "yuv420p",
    ]
    if audio_bitrate:
        cmd += ["-c:a", "aac", "-b:a", audio_bitrate]
    else:
        cmd += ["-c:a", "copy"]
    cmd += ["-movflags", "+faststart", out_path]
    _run(cmd)
    return out_path

def resize_video(in_path: str, out_path: str, width: Optional[int] = None, height: Optional[int] = None, crf: int = 23, preset: str = "medium"):
    """Resize video while maintaining aspect ratio"""
    _ensure_dir(Path(out_path).parent.as_posix())
    
    if width and width > 0:
        scale = f"scale={width}:-2"
    elif height and height > 0:
        scale = f"scale=-2:{height}"
    else:
        raise ValueError("Provide width or height")

    cmd = [
        _ffmpeg_path(), "-y",
        "-i", in_path,
        "-vf", scale,
        "-c:v", "libx264",
        "-crf", str(crf),
        "-preset", preset,
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        out_path
    ]
    _run(cmd)
    return out_path

def change_video_framerate(in_path: str, out_path: str, fps: int = 30, crf: int = 23):
    """Change video framerate"""
    _ensure_dir(Path(out_path).parent.as_posix())
    cmd = [
        _ffmpeg_path(), "-y",
        "-i", in_path,
        "-filter:v", f"fps={fps}",
        "-c:v", "libx264",
        "-crf", str(crf),
        "-pix_fmt", "yuv420p",
        "-c:a", "copy",
        out_path
    ]
    _run(cmd)
    return out_path

def extract_video_frames(video_path: str, out_dir: str, fps: Optional[float] = None, start_time: Optional[str] = None, duration: Optional[str] = None):
    """Extract frames from video as PNG images"""
    _ensure_dir(out_dir)
    
    cmd = [_ffmpeg_path(), "-y"]
    
    if start_time:
        cmd += ["-ss", start_time]
    
    cmd += ["-i", video_path]
    
    if duration:
        cmd += ["-t", duration]
    
    if fps:
        cmd += ["-vf", f"fps={fps}"]
    
    cmd += [os.path.join(out_dir, "frame_%05d.png")]
    _run(cmd)
    return out_dir

def create_video_from_images(image_dir: str, out_path: str, fps: int = 25, pattern: str = "frame_%05d.png"):
    """Create video from sequence of images"""
    _ensure_dir(Path(out_path).parent.as_posix())
    
    input_pattern = os.path.join(image_dir, pattern)
    cmd = [
        _ffmpeg_path(), "-y",
        "-framerate", str(fps),
        "-i", input_pattern,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "23",
        out_path
    ]
    _run(cmd)
    return out_path

# ============== IMAGE CONVERSION FUNCTIONS ==============

def convert_image_format(in_path: str, out_path: str, quality: int = 90):
    """Convert between image formats using PIL"""
    if not Image:
        raise RuntimeError("Pillow not installed. Run: pip install Pillow")
    
    _ensure_dir(Path(out_path).parent.as_posix())
    
    with Image.open(in_path) as img:
        # Handle transparency for formats that don't support it
        out_ext = Path(out_path).suffix.lower()
        if out_ext in ['.jpg', '.jpeg'] and img.mode in ['RGBA', 'LA']:
            # Create white background for JPEG
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[-1])  # Use alpha channel as mask
            else:
                background.paste(img)
            img = background
        
        # Save with appropriate parameters
        save_kwargs = {}
        if out_ext in ['.jpg', '.jpeg']:
            save_kwargs['quality'] = quality
            save_kwargs['optimize'] = True
        elif out_ext == '.png':
            save_kwargs['optimize'] = True
        elif out_ext == '.webp':
            save_kwargs['quality'] = quality
            save_kwargs['method'] = 6
        
        img.save(out_path, **save_kwargs)
    
    return out_path

def resize_image(in_path: str, out_path: str, width: Optional[int] = None, height: Optional[int] = None, maintain_aspect: bool = True, quality: int = 90):
    """Resize image with optional aspect ratio maintenance"""
    if not Image:
        raise RuntimeError("Pillow not installed. Run: pip install Pillow")
    
    _ensure_dir(Path(out_path).parent.as_posix())
    
    with Image.open(in_path) as img:
        if maintain_aspect:
            if width and height:
                img.thumbnail((width, height), Image.Resampling.LANCZOS)
            elif width:
                ratio = width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((width, new_height), Image.Resampling.LANCZOS)
            elif height:
                ratio = height / img.height
                new_width = int(img.width * ratio)
                img = img.resize((new_width, height), Image.Resampling.LANCZOS)
        else:
            if width and height:
                img = img.resize((width, height), Image.Resampling.LANCZOS)
        
        # Save with quality settings
        save_kwargs = {}
        out_ext = Path(out_path).suffix.lower()
        if out_ext in ['.jpg', '.jpeg']:
            if img.mode in ['RGBA', 'LA']:
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background
            save_kwargs['quality'] = quality
            save_kwargs['optimize'] = True
        elif out_ext == '.webp':
            save_kwargs['quality'] = quality
        
        img.save(out_path, **save_kwargs)
    
    return out_path

def compress_image(in_path: str, out_path: str, quality: int = 85, max_size_kb: Optional[int] = None):
    """Compress image to reduce file size"""
    if not Image:
        raise RuntimeError("Pillow not installed. Run: pip install Pillow")
    
    _ensure_dir(Path(out_path).parent.as_posix())
    
    with Image.open(in_path) as img:
        # Convert RGBA to RGB for JPEG
        out_ext = Path(out_path).suffix.lower()
        if out_ext in ['.jpg', '.jpeg'] and img.mode in ['RGBA', 'LA']:
            background = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[-1])
            else:
                background.paste(img)
            img = background
        
        # Progressive quality reduction if max_size_kb specified
        if max_size_kb and out_ext in ['.jpg', '.jpeg']:
            current_quality = quality
            while current_quality > 10:
                img.save(out_path, quality=current_quality, optimize=True)
                file_size_kb = os.path.getsize(out_path) / 1024
                if file_size_kb <= max_size_kb:
                    break
                current_quality -= 10
        else:
            save_kwargs = {'optimize': True}
            if out_ext in ['.jpg', '.jpeg']:
                save_kwargs['quality'] = quality
            elif out_ext == '.webp':
                save_kwargs['quality'] = quality
            img.save(out_path, **save_kwargs)
    
    return out_path

def convert_to_grayscale(in_path: str, out_path: str, quality: int = 90):
    """Convert image to grayscale"""
    if not Image:
        raise RuntimeError("Pillow not installed. Run: pip install Pillow")
    
    _ensure_dir(Path(out_path).parent.as_posix())
    
    with Image.open(in_path) as img:
        # Convert to grayscale
        gray_img = ImageOps.grayscale(img)
        
        # Save with quality settings
        save_kwargs = {}
        out_ext = Path(out_path).suffix.lower()
        if out_ext in ['.jpg', '.jpeg']:
            save_kwargs['quality'] = quality
            save_kwargs['optimize'] = True
        elif out_ext == '.png':
            save_kwargs['optimize'] = True
        
        gray_img.save(out_path, **save_kwargs)
    
    return out_path

def enhance_image(in_path: str, out_path: str, brightness: float = 1.0, contrast: float = 1.0, sharpness: float = 1.0, quality: int = 90):
    """Enhance image brightness, contrast, and sharpness"""
    if not Image or not ImageEnhance:
        raise RuntimeError("Pillow not installed. Run: pip install Pillow")
    
    _ensure_dir(Path(out_path).parent.as_posix())
    
    with Image.open(in_path) as img:
        # Apply enhancements
        if brightness != 1.0:
            enhancer = ImageEnhance.Brightness(img)
            img = enhancer.enhance(brightness)
        
        if contrast != 1.0:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(contrast)
        
        if sharpness != 1.0:
            enhancer = ImageEnhance.Sharpness(img)
            img = enhancer.enhance(sharpness)
        
        # Save with quality settings
        save_kwargs = {}
        out_ext = Path(out_path).suffix.lower()
        if out_ext in ['.jpg', '.jpeg']:
            if img.mode in ['RGBA', 'LA']:
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    background.paste(img, mask=img.split()[-1])
                else:
                    background.paste(img)
                img = background
            save_kwargs['quality'] = quality
            save_kwargs['optimize'] = True
        
        img.save(out_path, **save_kwargs)
    
    return out_path

# ============== ENHANCED CLASS WRAPPER ==============

class MediaConverters:
    """Enhanced media converter with all audio, video, and image features"""
    
    def __init__(self, output_dir: Optional[str] = None):
        if output_dir:
            self.output_dir = output_dir
            _ensure_dir(self.output_dir)
        else:
            self.output_dir = os.path.join(os.getcwd(), f"media_{uuid.uuid4().hex}")
            _ensure_dir(self.output_dir)

    # Audio conversion methods
    def mp3_to_wav(self, file_path: str, sample_rate: int = 44100, channels: int = 2) -> str:
        out = os.path.join(self.output_dir, "converted.wav")
        return mp3_to_wav(file_path, out, sample_rate, channels)

    def wav_to_mp3(self, file_path: str, bitrate: str = "192k", sample_rate: int = 44100, channels: int = 2) -> str:
        out = os.path.join(self.output_dir, "converted.mp3")
        return wav_to_mp3(file_path, out, bitrate, sample_rate, channels)

    def convert_audio(self, file_path: str, target_format: str, bitrate: str = "192k", sample_rate: int = 44100, channels: int = 2) -> str:
        out = os.path.join(self.output_dir, f"converted.{target_format}")
        return convert_audio_format(file_path, out, bitrate, sample_rate, channels)

    def extract_audio(self, file_path: str, target_format: str = "mp3", bitrate: str = "192k") -> str:
        out = os.path.join(self.output_dir, f"extracted_audio.{target_format}")
        return extract_audio_from_video(file_path, out, bitrate)

    def change_bitrate(self, file_path: str, bitrate: str = "128k") -> str:
        ext = Path(file_path).suffix
        out = os.path.join(self.output_dir, f"reencoded{ext}")
        return change_audio_bitrate(file_path, out, bitrate)

    # Video conversion methods
    def convert_video(self, file_path: str, target_format: str, crf: int = 23, preset: str = "medium") -> str:
        out = os.path.join(self.output_dir, f"converted.{target_format}")
        return convert_video_format(file_path, out, crf, preset)

    def compress_video(self, file_path: str, crf: int = 28, preset: str = "medium", audio_bitrate: Optional[str] = None) -> str:
        out = os.path.join(self.output_dir, "compressed.mp4")
        return compress_video(file_path, out, crf, preset, audio_bitrate)

    def resize_video(self, file_path: str, width: Optional[int] = None, height: Optional[int] = None, crf: int = 23) -> str:
        out = os.path.join(self.output_dir, "resized.mp4")
        return resize_video(file_path, out, width, height, crf)

    def change_framerate(self, file_path: str, fps: int = 30) -> str:
        out = os.path.join(self.output_dir, f"fps_{fps}.mp4")
        return change_video_framerate(file_path, out, fps)

    def extract_frames(self, video_path: str, fps: Optional[float] = None) -> str:
        out_dir = os.path.join(self.output_dir, "frames")
        return extract_video_frames(video_path, out_dir, fps)

    # Image conversion methods
    def convert_image(self, file_path: str, target_format: str, quality: int = 90) -> str:
        out = os.path.join(self.output_dir, f"converted.{target_format}")
        return convert_image_format(file_path, out, quality)

    def resize_image(self, file_path: str, width: Optional[int] = None, height: Optional[int] = None, quality: int = 90) -> str:
        ext = Path(file_path).suffix
        out = os.path.join(self.output_dir, f"resized{ext}")
        return resize_image(file_path, out, width, height, quality=quality)

    def compress_image(self, file_path: str, quality: int = 85, max_size_kb: Optional[int] = None) -> str:
        ext = Path(file_path).suffix
        out = os.path.join(self.output_dir, f"compressed{ext}")
        return compress_image(file_path, out, quality, max_size_kb)

    def to_grayscale(self, file_path: str, quality: int = 90) -> str:
        ext = Path(file_path).suffix
        out = os.path.join(self.output_dir, f"grayscale{ext}")
        return convert_to_grayscale(file_path, out, quality)

    def enhance_image(self, file_path: str, brightness: float = 1.0, contrast: float = 1.0, sharpness: float = 1.0) -> str:
        ext = Path(file_path).suffix
        out = os.path.join(self.output_dir, f"enhanced{ext}")
        return enhance_image(file_path, out, brightness, contrast, sharpness)

# ============== UTILITY FUNCTIONS ==============

def get_media_info(file_path: str) -> dict:
    """Get media file information using ffprobe"""
    try:
        cmd = [
            _ffmpeg_path().replace('ffmpeg', 'ffprobe'),
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            file_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        import json
        return json.loads(result.stdout)
    except Exception as e:
        return {"error": str(e)}

def test_ffmpeg_installation():
    """Test if FFmpeg is properly installed and accessible"""
    try:
        cmd = [_ffmpeg_path(), '-version']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return True, result.stdout.split('\n')[0]
    except Exception as e:
        return False, str(e)

if __name__ == "__main__":
    # Test FFmpeg installation
    success, info = test_ffmpeg_installation()
    if success:
        print(f"✅ FFmpeg available: {info}")
    else:
        print(f"❌ FFmpeg not found: {info}")
    
    # Test PIL availability
    if Image:
        print("✅ Pillow available for image processing")
    else:
        print("❌ Pillow not available. Install with: pip install Pillow")
    
    print("🎬 MediaConverters module loaded successfully!")
