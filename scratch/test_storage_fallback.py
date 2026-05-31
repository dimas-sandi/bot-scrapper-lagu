import sys
import os

# Add src path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import storage
from storage import StorageManager, find_best_alternative_drive

print("Running Storage Fallback Unit Tests...")

# Mock get_available_windows_drives to simulate different drive capacities
original_get_drives = storage.get_available_windows_drives

def mock_get_available_windows_drives():
    return [
        {'drive': 'C:\\', 'free_mb': 50000.0, 'total_mb': 250000.0},
        {'drive': 'D:\\', 'free_mb': 10000.0, 'total_mb': 100000.0},
        {'drive': 'E:\\', 'free_mb': 100.0, 'total_mb': 100000.0}, # Full! (free < 500 MB)
        {'drive': 'F:\\', 'free_mb': 80000.0, 'total_mb': 200000.0}, # F: has more free space than D:
    ]

storage.get_available_windows_drives = mock_get_available_windows_drives

# Test 1: Fallback from E:\ prioritizing D:\ even if F:\ has more space
print("\n--- Test 1: Prioritize D: from E: when D: is valid ---")
best_alt = find_best_alternative_drive('E:\\', threshold_mb=500)
print(f"Fallback drive from E:\\: {best_alt}")
assert best_alt is not None, "Should find alternative"
assert best_alt['drive'] == 'D:\\', f"Expected D:\\, got {best_alt['drive']}"
print("Pass!")

# Test 2: Fallback from E:\ when D:\ is also full
def mock_get_available_windows_drives_d_full():
    return [
        {'drive': 'C:\\', 'free_mb': 50000.0, 'total_mb': 250000.0},
        {'drive': 'D:\\', 'free_mb': 100.0, 'total_mb': 100000.0}, # D: is full too!
        {'drive': 'E:\\', 'free_mb': 100.0, 'total_mb': 100000.0}, # E: is full!
        {'drive': 'F:\\', 'free_mb': 80000.0, 'total_mb': 200000.0}, # F: has plenty of space
    ]

storage.get_available_windows_drives = mock_get_available_windows_drives_d_full
print("\n--- Test 2: Fallback to other drive if D: is also full ---")
best_alt2 = find_best_alternative_drive('E:\\', threshold_mb=500)
print(f"Fallback drive from E:\\ when D: is full: {best_alt2}")
assert best_alt2 is not None
assert best_alt2['drive'] == 'F:\\', f"Expected F:\\, got {best_alt2['drive']}"
print("Pass!")

# Test 3: Fallback from other drives (should use drive with most free space)
print("\n--- Test 3: Fallback from C: (should find F: as best since F has 80000MB) ---")
best_alt3 = find_best_alternative_drive('C:\\', threshold_mb=500)
print(f"Fallback drive from C:\\: {best_alt3}")
assert best_alt3 is not None
assert best_alt3['drive'] == 'F:\\', f"Expected F:\\, got {best_alt3['drive']}"
print("Pass!")

# Test 4: StorageManager path resolution
print("\n--- Test 4: StorageManager path resolution ---")
storage.get_available_windows_drives = mock_get_available_windows_drives
mgr = StorageManager('E:\\Karaoke_Downloads', min_free_mb=500)
# Mock check_disk_space to return False for E:\ path
def mock_check_disk_space(path, threshold_mb=500):
    if path.startswith('E:'):
        return False, 100.0
    return True, 10000.0

storage.check_disk_space = mock_check_disk_space

target_path = mgr.verify_and_get_path("Pop Indo", "Noah")
print(f"Target path: {target_path}")
assert target_path.startswith('D:\\'), f"Expected path to start with D:\\, got {target_path}"
print("Pass!")

print("\nAll unit tests passed successfully!")
