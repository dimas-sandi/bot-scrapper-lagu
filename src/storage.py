import os
import shutil
import string
import psutil

def get_drive_from_path(path):
    """Extract drive letter or mount point from path."""
    abs_path = os.path.abspath(path)
    drive = os.path.splitdrive(abs_path)[0]
    if drive:
        return drive + '\\'
    # Fallback for systems without drive letters (e.g. Linux/Mac)
    return '/'

def get_disk_free_space_mb(path):
    """Return free disk space in Megabytes for the drive containing path."""
    try:
        total, used, free = shutil.disk_usage(path)
        return free / (1024 * 1024)
    except Exception:
        # Fallback using psutil
        try:
            drive = get_drive_from_path(path)
            usage = psutil.disk_usage(drive)
            return usage.free / (1024 * 1024)
        except Exception:
            return 999999.0  # Return a very high number on error so we don't block downloads

def check_disk_space(path, threshold_mb=500):
    """Check if the disk containing the path has free space above threshold_mb."""
    free_mb = get_disk_free_space_mb(path)
    return free_mb >= threshold_mb, free_mb

def get_available_windows_drives():
    """List all available Windows drives with their free space in MB."""
    drives = []
    # Standard drive letters in Windows
    for letter in string.ascii_uppercase:
        drive_path = f"{letter}:\\"
        if os.path.exists(drive_path):
            try:
                total, used, free = shutil.disk_usage(drive_path)
                free_mb = free / (1024 * 1024)
                drives.append({
                    'drive': drive_path,
                    'free_mb': free_mb,
                    'total_mb': total / (1024 * 1024)
                })
            except Exception:
                pass
    return drives

def find_best_alternative_drive(current_drive, threshold_mb=500):
    """
    Finds the drive with the most free space that is NOT the current_drive.
    Must have free space greater than threshold_mb.
    If the current drive is E:\, we specifically check and prioritize D:\.
    """
    current_drive = current_drive.upper().rstrip('\\') + '\\'
    drives = get_available_windows_drives()
    
    # Filter out current drive and those with insufficient space
    alternatives = [d for d in drives if d['drive'].upper() != current_drive and d['free_mb'] > threshold_mb]
    
    if not alternatives:
        return None
        
    # Specific requirement: if current is E:\, prioritize D:\ as fallback
    if current_drive == 'E:\\':
        d_drive = [d for d in alternatives if d['drive'].upper() == 'D:\\']
        if d_drive:
            return d_drive[0]
            
    # Sort by free space descending
    alternatives.sort(key=lambda x: x['free_mb'], reverse=True)
    return alternatives[0]

class StorageManager:
    def __init__(self, primary_dir, min_free_mb=500):
        self.primary_dir = os.path.abspath(primary_dir)
        self.active_dir = self.primary_dir
        self.min_free_mb = min_free_mb
        
    def verify_and_get_path(self, category, artist):
        """
        Verifies if active drive is full.
        If full, auto-switches to the best alternative drive.
        Returns the path to save the song under category/artist.
        """
        is_ok, free_mb = check_disk_space(self.active_dir, self.min_free_mb)
        
        if not is_ok:
            current_drive = get_drive_from_path(self.active_dir)
            print(f"\n[Penyimpanan Penuh] Drive {current_drive} sisa {free_mb:.1f} MB (Batas: {self.min_free_mb} MB). Mencari drive cadangan...")
            
            alt_drive_info = find_best_alternative_drive(current_drive, self.min_free_mb)
            if alt_drive_info:
                alt_drive = alt_drive_info['drive']
                # Create Karaoke_Downloads folder on alternative drive
                self.active_dir = os.path.join(alt_drive, "Karaoke_Downloads")
                print(f"[Penyimpanan Beralih] Folder download baru dipindahkan ke: {self.active_dir} (Sisa ruang: {alt_drive_info['free_mb']:.1f} MB)")
            else:
                print(f"[Peringatan Kritis] Tidak ada drive cadangan yang cukup lega! Tetap menggunakan penyimpanan aktif: {self.active_dir}")
                
        # Resolve song subdirectories
        target_folder = os.path.join(self.active_dir, category, artist)
        os.makedirs(target_folder, exist_ok=True)
        return target_folder
