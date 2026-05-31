import os
import pandas as pd

def check_excel():
    excel_path = r"D:\list lagu.xls"
    if not os.path.exists(excel_path):
        print(f"File {excel_path} tidak ditemukan!")
        # Try finding in current directory
        proj_dir = os.path.dirname(os.path.abspath(__file__))
        local_files = [f for f in os.listdir(proj_dir) if f.endswith(('.xls', '.xlsx'))]
        print("File lokal:", local_files)
        return
        
    print(f"File {excel_path} ditemukan.")
    print(f"Ukuran file: {os.path.getsize(excel_path)} bytes")
    
    # Try reading all sheets
    try:
        xls = pd.ExcelFile(excel_path)
        print("Daftar sheet dalam Excel:")
        for sheet in xls.sheet_names:
            df = pd.read_excel(excel_path, sheet_name=sheet)
            print(f"  Sheet '{sheet}': {len(df)} baris, Kolom: {df.columns.tolist()[:5]}")
            
    except Exception as e:
        print("Gagal membaca Excel:", e)

if __name__ == "__main__":
    check_excel()
