# test_archive_basic.py - Works with current installed packages
import tempfile
import os
from pathlib import Path

# Test what's currently working
def test_current_packages():
    """Test currently installed archive packages"""
    print("🚀 Testing Current Archive Dependencies")
    print("=" * 50)
    
    results = []
    
    # Test py7zr
    try:
        import py7zr
        print("✅ py7zr available - 7Z support enabled")
        
        # Basic 7z test
        temp_dir = tempfile.mkdtemp()
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("Test content for 7Z")
        
        archive_path = os.path.join(temp_dir, "test.7z")
        with py7zr.SevenZipFile(archive_path, 'w') as archive:
            archive.write(test_file, "test.txt")
        
        # Test extraction
        extract_dir = os.path.join(temp_dir, "extracted")
        os.makedirs(extract_dir)
        with py7zr.SevenZipFile(archive_path, 'r') as archive:
            archive.extractall(extract_dir)
        
        if os.path.exists(os.path.join(extract_dir, "test.txt")):
            print("✅ 7Z create/extract test passed!")
            results.append(True)
        else:
            print("❌ 7Z extraction failed")
            results.append(False)
            
    except Exception as e:
        print(f"❌ py7zr test failed: {e}")
        results.append(False)
    
    # Test rarfile
    try:
        import rarfile
        print("✅ rarfile available - RAR reading support enabled")
        results.append(True)
    except Exception as e:
        print(f"❌ rarfile test failed: {e}")
        results.append(False)
    
    # Test standard zipfile
    try:
        import zipfile
        print("✅ zipfile (built-in) - ZIP support enabled")
        
        # Basic ZIP test
        temp_dir = tempfile.mkdtemp()
        test_file = os.path.join(temp_dir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("Test content for ZIP")
        
        zip_path = os.path.join(temp_dir, "test.zip")
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(test_file, "test.txt")
        
        # Test extraction
        extract_dir = os.path.join(temp_dir, "zip_extracted")
        os.makedirs(extract_dir)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)
        
        if os.path.exists(os.path.join(extract_dir, "test.txt")):
            print("✅ ZIP create/extract test passed!")
            results.append(True)
        else:
            print("❌ ZIP extraction failed")
            results.append(False)
            
    except Exception as e:
        print(f"❌ zipfile test failed: {e}")
        results.append(False)
    
    # Test pyminizip availability
    try:
        import pyminizip
        print("✅ pyminizip available - Password-protected ZIP enabled")
        results.append(True)
    except ImportError:
        print("⚠️  pyminizip not available - No password-protected ZIP")
        print("   Install Microsoft Visual C++ Build Tools to enable")
        results.append(False)
    
    print("\n" + "=" * 50)
    print(f"📊 Working Dependencies: {sum(results)}/{len(results)}")
    
    if sum(results) >= 3:  # At least zipfile, py7zr, rarfile
        print("🎉 Archive converter can work with current setup!")
        print("\n💡 Available Features:")
        print("   • ZIP create/extract (standard)")
        print("   • 7Z create/extract with compression levels")
        print("   • RAR extract (if tools in PATH)")
        print("   • Archive format conversion")
        return True
    else:
        print("⚠️  Some core features unavailable")
        return False

if __name__ == "__main__":
    test_current_packages()
