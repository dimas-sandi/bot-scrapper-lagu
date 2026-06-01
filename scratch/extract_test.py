import zipfile, os, shutil

def main():
    proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    zip_path = os.path.join(proj_dir, 'test_speed.zip')
    temp_dir = os.path.join(proj_dir, 'ffmpeg_temp_extract')
    bin_dir = os.path.join(proj_dir, 'bin')
    
    os.makedirs(temp_dir, exist_ok=True)
    os.makedirs(bin_dir, exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'r') as z:
        z.extractall(temp_dir)
        
    extracted = os.listdir(temp_dir)[0]
    extracted_bin = os.path.join(temp_dir, extracted, 'bin')
    
    shutil.copy(os.path.join(extracted_bin, 'ffmpeg.exe'), os.path.join(bin_dir, 'ffmpeg.exe'))
    shutil.copy(os.path.join(extracted_bin, 'ffprobe.exe'), os.path.join(bin_dir, 'ffprobe.exe'))
    
    shutil.rmtree(temp_dir)
    os.remove(zip_path)
    
    print("FFmpeg updated successfully!")

if __name__ == '__main__':
    main()
