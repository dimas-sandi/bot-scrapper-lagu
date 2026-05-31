import subprocess

def test_gpu_query():
    print("=== MENGUJI QUERY GPU UNIVERSAL ===")
    try:
        # Universal WMI query for GPU 3D engine utilization percentage
        cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine | Where-Object { $_.Name -like '*engtype_3D*' } | Measure-Object -Property UtilizationPercentage -Sum | Select-Object -ExpandProperty Sum"]
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5, startupinfo=startupinfo)
        val = res.stdout.strip()
        print(f"Hasil GPU Usage: '{val}%'")
    except Exception as e:
        print("Gagal query GPU:", e)

def test_cpu_temp():
    print("\n=== MENGUJI QUERY SUHU CPU ===")
    try:
        cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance -Namespace root/wmi -ClassName MsAcpi_ThermalZoneTemperature | Select-Object -ExpandProperty CurrentTemperature"]
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5, startupinfo=startupinfo)
        val = res.stdout.strip()
        print(f"Hasil CPU Temp (Raw Kelvin*10): '{val}'")
    except Exception as e:
        print("Gagal query CPU Temp:", e)

if __name__ == "__main__":
    test_gpu_query()
    test_cpu_temp()
