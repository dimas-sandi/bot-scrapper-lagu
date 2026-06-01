import os
import sys
import zipfile
import urllib.request
import shutil

def main():
    proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bin_dir = os.path.join(proj_dir, "bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    zip_url = "https://github.com/GyanD/codexffmpeg/releases/download/7.1/ffmpeg-7.1-essentials_build.zip"
    zip_path = os.path.join(proj_dir, "ffmpeg_release.zip")
    
    print("==================================================")
    print("      DOWNLOADING FFMPEG ESSENTIALS VIA PYTHON    ")
    print("==================================================")
    print(f"Downloading from: {zip_url}")
    
    # Download with simple progress reporting
    def reporthook(blocknum, blocksize, totalsize):
        readsofar = blocknum * blocksize
        if totalsize > 0:
            percent = readsofar * 1e2 / totalsize
            s = f"\rProgress: {percent:.1f}% ({readsofar//(1024*1024)}MB / {totalsize//(1024*1024)}MB)"
            sys.stdout.write(s)
            sys.stdout.flush()
        else:
            sys.stdout.write(f"\rRead {readsofar} bytes")
            sys.stdout.flush()

    try:
        urllib.request.urlretrieve(zip_url, zip_path, reporthook)
        print("\n[OK] Download complete. Extracting binaries...")
    except Exception as e:
        print(f"\n[ERROR] Failed to download FFmpeg: {e}")
        return
        
    temp_extract = os.path.join(proj_dir, "ffmpeg_temp_extract")
    os.makedirs(temp_extract, exist_ok=True)
    
    try:
        # Extract using python's zipfile
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract)
            
        print("[OK] Extraction complete. Moving binaries to bin/...")
        
        # Find extracted folder
        extracted_dirs = [d for d in os.listdir(temp_extract) if os.path.isdir(os.path.join(temp_extract, d))]
        if not extracted_dirs:
            print("[ERROR] Extracted directory not found.")
            return
            
        extracted_dir = os.path.join(temp_extract, extracted_dirs[0])
        extracted_bin = os.path.join(extracted_dir, "bin")
        
        ffmpeg_src = os.path.join(extracted_bin, "ffmpeg.exe")
        ffprobe_src = os.path.join(extracted_bin, "ffprobe.exe")
        
        ffmpeg_dst = os.path.join(bin_dir, "ffmpeg.exe")
        ffprobe_dst = os.path.join(bin_dir, "ffprobe.exe")
        
        if os.path.exists(ffmpeg_src):
            shutil.copy2(ffmpeg_src, ffmpeg_dst)
            print(f"[OK] Copied ffmpeg.exe to {ffmpeg_dst}")
        else:
            print("[ERROR] ffmpeg.exe not found in extracted folder.")
            
        if os.path.exists(ffprobe_src):
            shutil.copy2(ffprobe_src, ffprobe_dst)
            print(f"[OK] Copied ffprobe.exe to {ffprobe_dst}")
        else:
            print("[ERROR] ffprobe.exe not found in extracted folder.")
            
    except Exception as e:
        print(f"[ERROR] Failed to extract FFmpeg: {e}")
    finally:
        print("Cleaning up temporary files...")
        if os.path.exists(zip_path):
            try:
                os.remove(zip_path)
            except Exception:
                pass
        if os.path.exists(temp_extract):
            try:
                shutil.rmtree(temp_extract)
            except Exception:
                pass
        print("==================================================")
        print("                 SETUP FINISHED!                  ")
        print("==================================================")

if __name__ == "__main__":
    main()
