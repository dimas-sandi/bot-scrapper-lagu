import os
import sys
import json
import time
import threading
import argparse
import subprocess
import urllib.request
import urllib.error
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import colorama
import psutil

# Add src folder to system path for safety
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import excel_handler
import downloader
import storage

# Initialize colorama for Windows ANSI support
colorama.init()

# ==========================================
# HARDWARE MONITORING HELPERS (LIGHTWEIGHT)
# ==========================================
def get_nvidia_gpu_info():
    """Queries Nvidia GPU utilization and temperature using official nvidia-smi (very fast and light)."""
    try:
        cmd = ["nvidia-smi", "--query-gpu=utilization.gpu,temperature.gpu", "--format=csv,noheader,nounits"]
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=1.5, startupinfo=startupinfo)
        parts = res.stdout.strip().split(',')
        if len(parts) == 2:
            return f"{parts[0].strip()}%", f"{parts[1].strip()}°C"
    except:
        pass
    return "N/A", "N/A"

def get_local_ip():
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

# ==========================================
# HTTP SERVER FOR LAN COMMUNICATION
# ==========================================
class HTTPServerThread(threading.Thread):
    def __init__(self, bot, host, port):
        super().__init__()
        self.bot = bot
        self.host = host
        self.port = port
        self.daemon = True
        self.server = None

    def run(self):
        import http.server
        import socketserver

        class RequestHandler(http.server.BaseHTTPRequestHandler):
            bot_ref = self.bot
            
            def log_message(self, format, *args):
                pass # Silent log to prevent TUI screen breaks
                
            def do_GET(self):
                try:
                    if self.path == '/get_work':
                        song = self.bot_ref.get_next_pending_song()
                        if song:
                            self.send_response(200)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps(song).encode('utf-8'))
                        else:
                            self.send_response(200)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({"status": "empty"}).encode('utf-8'))
                    else:
                        self.send_response(404)
                        self.end_headers()
                except Exception as e:
                    import traceback
                    log_file = os.path.join(self.bot_ref.proj_dir, "server_error.log")
                    try:
                        with open(log_file, "a", encoding="utf-8") as f:
                            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] GET {self.path} Error: {str(e)}\n")
                            traceback.print_exc(file=f)
                    except:
                        pass
                    try:
                        self.send_response(500)
                        self.end_headers()
                        self.wfile.write(str(e).encode('utf-8'))
                    except:
                        pass

            def do_POST(self):
                try:
                    if self.path == '/report_status':
                        content_length = int(self.headers['Content-Length'])
                        post_data = self.rfile.read(content_length)
                        try:
                            data = json.loads(post_data.decode('utf-8'))
                            self.bot_ref.update_helper_status(
                                workers=data.get('workers', []),
                                hw_data=data.get('hardware', {})
                            )
                            self.send_response(200)
                            self.end_headers()
                            self.wfile.write(b"OK")
                        except Exception as e:
                            self.send_response(400)
                            self.end_headers()
                            self.wfile.write(str(e).encode('utf-8'))
                            
                    elif self.path == '/release_task':
                        content_length = int(self.headers['Content-Length'])
                        post_data = self.rfile.read(content_length)
                        try:
                            data = json.loads(post_data.decode('utf-8'))
                            song_key = data.get('song_key')
                            error_msg = data.get('error_msg', 'Gagal di client')
                            
                            with self.bot_ref.history_lock:
                                self.bot_ref.active_helper_tasks.pop(song_key, None)
                                if song_key in self.bot_ref.history:
                                    retries = self.bot_ref.history[song_key].get('retry_count', 0)
                                    was_failed = self.bot_ref.history[song_key].get('status') == 'Failed'
                                    
                                    self.bot_ref.history[song_key].update({
                                        'status': 'Failed',
                                        'error_msg': error_msg,
                                        'retry_count': retries + 1
                                    })
                                    self.bot_ref.save_history()
                                    self.bot_ref.update_clean_playlist_excel()
                                    
                                    if not was_failed:
                                        self.bot_ref.failed_count += 1
                                    self.bot_ref.log_finished(f"{colorama.Fore.RED}[GAGAL LAPTOP]{colorama.Style.RESET_ALL} {song_key} - {error_msg[:30]}")
                            
                            self.send_response(200)
                            self.end_headers()
                            self.wfile.write(b"Released")
                        except Exception as e:
                            self.send_response(400)
                            self.end_headers()
                            self.wfile.write(str(e).encode('utf-8'))
                            
                    elif self.path == '/upload':
                        try:
                            song_key = self.headers.get('X-Song-Key')
                            category = self.headers.get('X-Category', 'Lainnya')
                            artist = self.headers.get('X-Artist', '')
                            title = self.headers.get('X-Title', '')
                            file_size_mb = float(self.headers.get('X-File-Size-MB', 0))
                            duration_str = self.headers.get('X-Duration-Str', '0:00')
                            multiplex_tag = self.headers.get('X-Multiplex-Tag', '').strip()
                            
                            with self.bot_ref.history_lock:
                                target_folder = self.bot_ref.storage_mgr.verify_and_get_path(category, artist)
                                
                            if multiplex_tag:
                                safe_filename = excel_handler.clean_filename(f"{artist} - {title} {multiplex_tag}.mp4")
                            else:
                                safe_filename = excel_handler.clean_filename(f"{artist} - {title}.mp4")
                            output_filepath = os.path.join(target_folder, safe_filename)
                            
                            content_length = int(self.headers['Content-Length'])
                            os.makedirs(os.path.dirname(output_filepath), exist_ok=True)
                            
                            with open(output_filepath, 'wb') as f:
                                remaining = content_length
                                chunk_size = 64 * 1024
                                while remaining > 0:
                                    chunk = self.rfile.read(min(remaining, chunk_size))
                                    if not chunk:
                                        break
                                    f.write(chunk)
                                    remaining -= len(chunk)
                                    
                            with self.bot_ref.history_lock:
                                self.bot_ref.active_helper_tasks.pop(song_key, None)
                                was_failed = song_key in self.bot_ref.history and self.bot_ref.history[song_key].get('status') == 'Failed'
                                
                                self.bot_ref.history[song_key] = {
                                    'artist': artist,
                                    'title': title,
                                    'category': category,
                                    'status': 'Completed',
                                    'file_path': output_filepath,
                                    'file_size_mb': file_size_mb,
                                    'duration_str': duration_str,
                                    'error_msg': '',
                                    'retry_count': self.bot_ref.history.get(song_key, {}).get('retry_count', 0)
                                }
                                self.bot_ref.save_history()
                                self.bot_ref.update_clean_playlist_excel()
                                self.bot_ref.success_count += 1
                                
                                if was_failed:
                                    self.bot_ref.failed_count = max(0, self.bot_ref.failed_count - 1)
                                    
                                self.bot_ref.log_finished(f"{colorama.Fore.GREEN}[SUKSES LAPTOP]{colorama.Style.RESET_ALL} {song_key} ({file_size_mb:.2f}MB)")
                                
                            self.send_response(200)
                            self.end_headers()
                            self.wfile.write(b"Uploaded successfully")
                        except Exception as e:
                            self.send_response(500)
                            self.end_headers()
                            self.wfile.write(f"Server error during upload: {str(e)}".encode('utf-8'))
                    else:
                        self.send_response(404)
                        self.end_headers()
                except Exception as e:
                    import traceback
                    log_file = os.path.join(self.bot_ref.proj_dir, "server_error.log")
                    try:
                        with open(log_file, "a", encoding="utf-8") as f:
                            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] POST {self.path} Error: {str(e)}\n")
                            traceback.print_exc(file=f)
                    except:
                        pass
                    try:
                        self.send_response(500)
                        self.end_headers()
                        self.wfile.write(str(e).encode('utf-8'))
                    except:
                        pass

        class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
            daemon_threads = True
            def handle_error(self, request, client_address):
                pass # Suppress standard traceback printing to console

        socketserver.TCPServer.allow_reuse_address = True
        self.server = ThreadingHTTPServer((self.host, self.port), RequestHandler)
        self.server.serve_forever()
        
    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()

# ==========================================
# MAIN BOT CLASS
# ==========================================
class KaraokeBot:
    def __init__(self, role_override=None, ip_override=None, port_override=None, clean_low_quality=False):
        self.proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.proj_dir, "config.json")
        self.history_path = os.path.join(self.proj_dir, "download_history.json")
        
        self.load_config()
        
        self.role = role_override or self.config.get("network", {}).get("role", "server")
        if self.role not in ["server", "client"]:
            self.role = "server"
            
        self.server_ip = ip_override or self.config.get("network", {}).get("server_ip", "127.0.0.1")
        self.server_port = port_override or self.config.get("network", {}).get("server_port", 8080)
        
        # Locks
        self.history_lock = threading.Lock()
        self.queue_lock = threading.Lock()
        self.worker_states_lock = threading.Lock()
        self.finished_queue_lock = threading.Lock()
        self.worker_id_lock = threading.Lock()
        self.helper_workers_lock = threading.Lock()
        self.client_worker_states_lock = threading.Lock()
        
        self.running = False
        self.failed_songs_keys = set()
        self.history_dirty = False
        self.clean_low_quality = clean_low_quality
        
        if self.role == "server":
            self.load_history()
            self.storage_mgr = storage.StorageManager(
                primary_dir=self.config['default_output_dir'],
                min_free_mb=self.config['min_disk_free_mb']
            )
            
            # Local workers
            self.max_workers = self.config['max_workers']
            self.worker_states = [{"song": "", "phase": "Idle", "percent": 0} for _ in range(self.max_workers)]
            self.thread_to_worker = {}
            
            # Remote Helper
            self.helper_workers = [{"song": "", "phase": "Idle", "percent": 0} for _ in range(10)]
            self.helper_last_seen = 0
            self.active_helper_tasks = {}
            
            # Hardware info variables (updated in background thread)
            self.local_hardware_info = "CPU: N/A | GPU AMD: N/A"
            self.helper_hardware_info = "CPU: N/A | GPU NVidia: N/A | GPU Intel: N/A"
            
            # Queue statistics (failed count loaded from history database to show cumulative stats)
            self.success_count = 0
            self.failed_count = sum(1 for info in self.history.values() if info.get('status') == 'Failed')
            self.skipped_count = 0
            self.total_songs = 0
            self.remaining_songs = []
            
            self.finished_queue = []
            self.first_draw = True
            self.tui_height = 38 # Consistent height for Server TUI (incorporates hardware rows)
            
        else: # Client/Laptop Helper Mode
            self.max_workers = 10
            self.client_worker_states = [{"song": "", "phase": "Idle", "percent": 0} for _ in range(self.max_workers)]
            self.client_thread_to_worker = {}
            self.client_first_draw = True
            
            # Client hardware variables (updated in background thread)
            self.client_hardware_data = {
                "cpu": "N/A",
                "nv_gpu": "N/A",
                "intel_gpu": "N/A"
            }
            
        self.session_start_time = time.time()
        
    def load_config(self):
        default_config = {
            "excel_path": "D:\\list lagu.xls",
            "target_size_mb": 15.0,
            "audio_bitrate_kbps": 192,
            "max_resolution": "720p",
            "min_disk_free_mb": 500,
            "max_workers": 6,
            "default_output_dir": "D:\\Karaoke_Downloads",
            "use_gpu_acceleration": True,
            "gpu_encoder": "h264_amf",
            "max_gpu_sessions": 2,
            "network": {
                "role": "server",
                "server_ip": "192.168.1.15",
                "server_port": 8080
            }
        }
        
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                for k, v in default_config.items():
                    if k not in self.config:
                        self.config[k] = v
            except:
                self.config = default_config
        else:
            self.config = default_config
            try:
                with open(self.config_path, 'w', encoding='utf-8') as f:
                    json.dump(self.config, f, indent=2)
            except:
                pass

    def load_history(self):
        if os.path.exists(self.history_path):
            if os.path.getsize(self.history_path) == 0:
                self.history = {}
                return
            try:
                with open(self.history_path, 'r', encoding='utf-8') as f:
                    self.history = json.load(f)
                
                # Reset stuck "Downloading" status to "Pending" on startup
                history_changed = False
                for key, info in self.history.items():
                    if info.get('status') == 'Downloading':
                        info['status'] = 'Pending'
                        history_changed = True
                if history_changed:
                    self.save_history()
            except Exception as e:
                backup_path = self.history_path + ".corrupted"
                try:
                    import shutil
                    shutil.copy2(self.history_path, backup_path)
                except:
                    pass
                print(f"\n[ERROR] File history '{self.history_path}' rusak: {e}")
                print(f"Cadangan file rusak telah disimpan di: {backup_path}")
                input("Tekan Enter untuk keluar...")
                sys.exit(1)
        else:
            self.history = {}

    def save_history(self, force=False):
        if not force and self.running:
            self.history_dirty = True
            return
            
        with self.history_lock:
            history_copy = json.loads(json.dumps(self.history))
            
        try:
            tmp_path = self.history_path + ".tmp"
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(history_copy, f, indent=2)
            os.replace(tmp_path, self.history_path)
        except Exception:
            try:
                with open(self.history_path, 'w', encoding='utf-8') as f:
                    json.dump(history_copy, f, indent=2)
            except:
                pass

    def update_clean_playlist_excel(self, force=False):
        if not force and self.running:
            self.history_dirty = True
            return
            
        with self.history_lock:
            history_copy = json.loads(json.dumps(self.history))
            
        output_excel = os.path.join(self.storage_mgr.active_dir, "Karaoke_Playlist_Clean.xlsx")
        report_data = []
        for key, info in history_copy.items():
            report_data.append({
                'category': info.get('category', 'Lainnya'),
                'artist': info.get('artist', ''),
                'title': info.get('title', ''),
                'status': info.get('status', 'Pending'),
                'file_path': info.get('file_path', ''),
                'file_size_mb': info.get('file_size_mb', 0),
                'duration_str': info.get('duration_str', ''),
                'error_msg': info.get('error_msg', '')
            })
            
        if report_data:
            try:
                excel_handler.write_clean_playlist(report_data, output_excel)
            except:
                pass

    def get_local_worker_id(self):
        ident = threading.get_ident()
        with self.worker_id_lock:
            if ident not in self.thread_to_worker:
                used_ids = set(self.thread_to_worker.values())
                for i in range(self.max_workers):
                    if i not in used_ids:
                        self.thread_to_worker[ident] = i
                        break
            return self.thread_to_worker.get(ident, 0)

    def get_client_worker_id(self):
        ident = threading.get_ident()
        with self.worker_id_lock:
            if ident not in self.client_thread_to_worker:
                used_ids = set(self.client_thread_to_worker.values())
                for i in range(self.max_workers):
                    if i not in used_ids:
                        self.client_thread_to_worker[ident] = i
                        break
            return self.client_thread_to_worker.get(ident, 0)

    def update_local_worker(self, worker_id, song, phase, percent):
        with self.worker_states_lock:
            self.worker_states[worker_id] = {
                "song": song,
                "phase": phase,
                "percent": percent
            }

    def update_client_worker(self, worker_id, song, phase, percent):
        with self.client_worker_states_lock:
            self.client_worker_states[worker_id] = {
                "song": song,
                "phase": phase,
                "percent": percent
            }

    def update_helper_status(self, workers, hw_data):
        with self.helper_workers_lock:
            self.helper_workers = workers
            self.helper_last_seen = time.time()
            
            # Format and save helper hardware data
            cpu = hw_data.get("cpu", "N/A")
            nv = hw_data.get("nv_gpu", "N/A")
            intel = hw_data.get("intel_gpu", "N/A")
            self.helper_hardware_info = f"CPU: {cpu} | GPU NVidia: {nv} | GPU Intel: {intel}"

    def log_finished(self, log_msg):
        with self.finished_queue_lock:
            self.finished_queue = [log_msg] + self.finished_queue[:4]

    def make_progress_bar(self, percent, width=15):
        completed = int((percent / 100) * width)
        completed = max(0, min(width, completed))
        remaining = width - completed
        return "[" + "=" * completed + "-" * remaining + "]"

    # ==========================================
    # SERVER SCHEDULING - QUEUE POP (O(1) SPEEDS)
    # ==========================================
    def check_and_enqueue_failed_songs(self):
        """
        Check if all normal tasks are completely done (no remaining normal songs and no active tasks).
        If so, scan history and enqueue any failed songs with retry_count < 2 back into remaining_songs.
        Must be called under self.queue_lock!
        """
        if self.remaining_songs:
            return False
            
        # Count active helper tasks
        active_helper = len(self.active_helper_tasks)
        
        # Count active local tasks
        active_local = 0
        with self.worker_states_lock:
            active_local = sum(1 for w in self.worker_states if w['song'] != "")
            
        # If there are still active tasks, we don't start retries yet because we are waiting for normal tasks to finish
        if active_helper > 0 or active_local > 0:
            return False
            
        # Scan history for failed songs to retry
        failed_to_retry = []
        with self.history_lock:
            for key, info in self.history.items():
                if info.get('status') == 'Failed':
                    retries = info.get('retry_count', 0)
                    if retries < 2:
                        failed_to_retry.append({
                            'artist': info.get('artist', ''),
                            'title': info.get('title', ''),
                            'category': info.get('category', 'Lainnya')
                        })
                        # Reset status to Pending so they aren't skipped
                        info['status'] = 'Pending'
            
            if failed_to_retry:
                self.save_history()
                
        if failed_to_retry:
            self.remaining_songs = failed_to_retry
            # Add keys to failed_songs_keys so downloader can use fast search delays
            for s in failed_to_retry:
                self.failed_songs_keys.add(f"{s['artist']} - {s['title']}")
                
            self.log_finished(f"{colorama.Fore.YELLOW}[PENCARIAN ULANG]{colorama.Style.RESET_ALL} Memulai kembali {len(failed_to_retry)} lagu yang gagal...")
            return True
            
        return False

    def get_next_pending_song(self):
        """Atomic Queue Pop (O(1)) for helper laptops."""
        with self.queue_lock:
            if not self.remaining_songs:
                self.check_and_enqueue_failed_songs()
                
            while self.remaining_songs:
                song = self.remaining_songs[0]
                song_key = f"{song['artist']} - {song['title']}"
                with self.history_lock:
                    hist = self.history.get(song_key)
                    if hist and (hist.get('status') == 'Completed' or hist.get('status') == 'Downloading'):
                        self.remaining_songs.pop(0)
                        continue
                        
                    self.history[song_key] = {
                        'artist': song['artist'],
                        'title': song['title'],
                        'category': song['category'],
                        'status': 'Downloading',
                        'file_path': '',
                        'file_size_mb': 0,
                        'duration_str': '',
                        'error_msg': ''
                    }
                    self.save_history()
                    
                self.remaining_songs.pop(0)
                
                self.active_helper_tasks[song_key] = {
                    "start_time": time.time(),
                    "song": song
                }
                return song
            return None

    def get_next_pending_song_local(self):
        """Atomic Queue Pop (O(1)) for PC local threads."""
        with self.queue_lock:
            if not self.remaining_songs:
                self.check_and_enqueue_failed_songs()
                
            while self.remaining_songs:
                song = self.remaining_songs[0]
                song_key = f"{song['artist']} - {song['title']}"
                with self.history_lock:
                    hist = self.history.get(song_key)
                    if hist and (hist.get('status') == 'Completed' or hist.get('status') == 'Downloading'):
                        self.remaining_songs.pop(0)
                        continue
                        
                    self.history[song_key] = {
                        'artist': song['artist'],
                        'title': song['title'],
                        'category': song['category'],
                        'status': 'Downloading',
                        'file_path': '',
                        'file_size_mb': 0,
                        'duration_str': '',
                        'error_msg': ''
                    }
                    self.save_history()
                    
                self.remaining_songs.pop(0)
                return song
            return None

    def process_song_local(self, song):
        artist = song['artist']
        title = song['title']
        category = song['category']
        song_key = f"{artist} - {title}"
        worker_id = self.get_local_worker_id()
        
        # Check if song is a retry from the failed songs queue
        is_retry = song_key in self.failed_songs_keys
        
        with self.history_lock:
            if song_key in self.history and self.history[song_key].get('status') == 'Completed':
                if os.path.exists(self.history[song_key].get('file_path', '')):
                    self.skipped_count += 1
                    return
                    
        try:
            self.update_local_worker(worker_id, song_key, "Cek Simpan", 0)
            with self.history_lock:
                target_folder = self.storage_mgr.verify_and_get_path(category, artist)
        except Exception as e:
            err_msg = f"Disk error: {str(e)}"
            with self.history_lock:
                was_failed = song_key in self.history and self.history[song_key].get('status') == 'Failed'
                self.history[song_key] = {
                    'artist': artist,
                    'title': title,
                    'category': category,
                    'status': 'Failed',
                    'error_msg': err_msg,
                    'retry_count': self.history.get(song_key, {}).get('retry_count', 0) + 1
                }
                self.save_history()
                self.update_clean_playlist_excel()
                
                if not was_failed:
                    self.failed_count += 1
                self.log_finished(f"{colorama.Fore.RED}[GAGAL]{colorama.Style.RESET_ALL} {song_key} - HDD error")
                self.update_local_worker(worker_id, "", "Idle", 0)
            return

        safe_filename = excel_handler.clean_filename(f"{artist} - {title}.mp4")
        output_filepath = os.path.join(target_folder, safe_filename)
        
        def progress_callback(percent, phase):
            self.update_local_worker(worker_id, song_key, phase, percent)

        # Search Youtube
        try:
            self.update_local_worker(worker_id, song_key, "Mencari Link", 0)
            candidates_list = downloader.search_youtube_karaoke(artist, title)
        except Exception as e:
            with self.history_lock:
                was_failed = song_key in self.history and self.history[song_key].get('status') == 'Failed'
                self.history[song_key] = {
                    'artist': artist,
                    'title': title,
                    'category': category,
                    'status': 'Failed',
                    'error_msg': str(e),
                    'retry_count': self.history.get(song_key, {}).get('retry_count', 0) + 1
                }
                self.save_history()
                self.update_clean_playlist_excel()
                
                if not was_failed:
                    self.failed_count += 1
                self.log_finished(f"{colorama.Fore.RED}[GAGAL]{colorama.Style.RESET_ALL} {song_key} - Tidak ditemukan")
                self.update_local_worker(worker_id, "", "Idle", 0)
            return

        # Download & Transcode locally (try each candidate in order of score)
        success = False
        last_error = ""
        res = None
        final_output_filepath = ""
        
        for index, cand in enumerate(candidates_list):
            video_url = cand['url']
            duration = cand['duration']
            duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else "0:00"
            
            with self.history_lock:
                self.history[song_key]['duration_str'] = duration_str
                self.save_history()
                
            # Detect multiplex tag to append to final filename
            cand_title_lower = cand['title'].lower()
            tag_to_append = ""
            if '#right' in cand_title_lower or '#r' in cand_title_lower:
                tag_to_append = " #RIGHT"
            elif '#left' in cand_title_lower or '#l' in cand_title_lower:
                tag_to_append = " #LEFT"
                
            if tag_to_append:
                safe_filename = excel_handler.clean_filename(f"{artist} - {title}{tag_to_append}.mp4")
            else:
                safe_filename = excel_handler.clean_filename(f"{artist} - {title}.mp4")
            cand_output_filepath = os.path.join(target_folder, safe_filename)
            
            try:
                msg_suffix = f" (Coba {index+1}/{len(candidates_list)})" if len(candidates_list) > 1 else ""
                def local_progress_callback(percent, phase):
                    progress_callback(percent, f"{phase}{msg_suffix}")
                    
                res = downloader.download_and_compress(
                    video_url=video_url,
                    output_filepath=cand_output_filepath,
                    target_size_mb=self.config['target_size_mb'],
                    audio_bitrate_kbps=self.config['audio_bitrate_kbps'],
                    max_resolution=self.config.get('max_resolution', '720p'),
                    progress_callback=local_progress_callback,
                    use_gpu=self.config.get('use_gpu_acceleration', True),
                    gpu_encoder=[self.config.get('gpu_encoder', 'h264_amf'), "h264_mf"],
                    max_gpu_sessions=self.config.get('max_gpu_sessions', 2),
                    cpu_threads=2,
                    is_retry=is_retry
                )
                success = True
                final_output_filepath = cand_output_filepath
                break
            except Exception as e:
                last_error = str(e)
                continue
                
        if success and res:
            with self.history_lock:
                was_failed = song_key in self.history and self.history[song_key].get('status') == 'Failed'
                self.history[song_key].update({
                    'status': 'Completed',
                    'file_path': final_output_filepath,
                    'file_size_mb': res['file_size_mb'],
                    'duration_str': res['duration_str'],
                    'error_msg': ''
                })
                self.save_history()
                self.update_clean_playlist_excel()
                self.success_count += 1
                
                if was_failed:
                    self.failed_count = max(0, self.failed_count - 1)
                    
                self.log_finished(f"{colorama.Fore.GREEN}[SUKSES]{colorama.Style.RESET_ALL} {song_key} ({res['file_size_mb']}MB)")
                self.update_local_worker(worker_id, "", "Idle", 0)
        else:
            with self.history_lock:
                was_failed = song_key in self.history and self.history[song_key].get('status') == 'Failed'
                self.history[song_key].update({
                    'status': 'Failed',
                    'error_msg': last_error,
                    'retry_count': self.history.get(song_key, {}).get('retry_count', 0) + 1
                })
                self.save_history()
                self.update_clean_playlist_excel()
                
                if not was_failed:
                    self.failed_count += 1
                
                # Show specific failure type in log
                if "mendownload" in last_error or "YouTube" in last_error:
                    err_lbl = "Download error"
                else:
                    err_lbl = "Transcode error"
                self.log_finished(f"{colorama.Fore.RED}[GAGAL]{colorama.Style.RESET_ALL} {song_key} - {err_lbl}")
                self.update_local_worker(worker_id, "", "Idle", 0)

    # ==========================================
    # BACKGROUND MONITOR FOR HARDWARE (LIGHTWEIGHT)
    # ==========================================
    def hardware_monitor_loop(self):
        while self.running:
            try:
                cpu_usage = f"{psutil.cpu_percent():.0f}%"
                
                # Fetch temp and AMD GPU stats
                ps_script = """
                $cpuTemp = "N/A"
                $gpuAmdUsage = "N/A"
                $gpuAmdTemp = "N/A"
                try {
                    $lhm = Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor -ErrorAction SilentlyContinue | Where-Object { $_.SensorType -eq 'Temperature' -and ($_.Name -like '*Core*' -or $_.Name -like '*CPU Package*') } | Select-Object -First 1 -ExpandProperty Value
                    if ($lhm) { $cpuTemp = "$([math]::Round($lhm))°C" }
                } catch {}
                if ($cpuTemp -eq "N/A") {
                    try {
                        $ohm = Get-CimInstance -Namespace root/OpenHardwareMonitor -ClassName Sensor -ErrorAction SilentlyContinue | Where-Object { $_.SensorType -eq 'Temperature' -and ($_.Name -like '*CPU*' -or $_.Name -like '*Core*') } | Select-Object -First 1 -ExpandProperty Value
                        if ($ohm) { $cpuTemp = "$([math]::Round($ohm))°C" }
                    } catch {}
                }
                if ($cpuTemp -eq "N/A") {
                    try {
                        $acpi = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty CurrentTemperature
                        if ($acpi) { $cpuTemp = "$([math]::Round(($acpi / 10) - 273.15))°C" }
                    } catch {}
                }
                $hasAmd = $false
                try {
                    $vc = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '*Radeon*' -or $_.Name -like '*AMD*' }
                    if ($vc) { $hasAmd = $true }
                } catch {}
                if ($hasAmd) {
                    try {
                        $util = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '*engtype_3D*' } | Measure-Object -Property UtilizationPercentage -Sum | Select-Object -ExpandProperty Sum
                        if ($util -ne $null) { $gpuAmdUsage = "$util%" }
                    } catch {}
                    try {
                        $gtemp = Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor -ErrorAction SilentlyContinue | Where-Object { $_.SensorType -eq 'Temperature' -and $_.Name -like '*GPU*' } | Select-Object -First 1 -ExpandProperty Value
                        if ($gtemp) { $gpuAmdTemp = "$([math]::Round($gtemp))°C" }
                    } catch {}
                }
                $res = @{ cpuTemp = $cpuTemp; gpuAmdUsage = $gpuAmdUsage; gpuAmdTemp = $gpuAmdTemp }
                $res | ConvertTo-Json
                """
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8, startupinfo=startupinfo)
                if res.stdout.strip():
                    stats = json.loads(res.stdout.strip())
                    cpu_temp = stats.get("cpuTemp", "N/A")
                    amd_usage = stats.get("gpuAmdUsage", "N/A")
                    amd_temp = stats.get("gpuAmdTemp", "N/A")
                else:
                    cpu_temp, amd_usage, amd_temp = "N/A", "N/A", "N/A"
                
                self.local_hardware_info = f"CPU: {cpu_usage} ({cpu_temp}) | GPU AMD: {amd_usage} ({amd_temp})"
            except Exception:
                pass
            time.sleep(5)

    def client_hardware_monitor_loop(self):
        while self.running:
            try:
                cpu_usage = f"{psutil.cpu_percent():.0f}%"
                nv_usage, nv_temp = get_nvidia_gpu_info()
                
                # Fetch CPU temp and Intel GPU stats
                ps_script = """
                $cpuTemp = "N/A"
                $intelUsage = "N/A"
                $intelTemp = "N/A"
                try {
                    $lhm = Get-CimInstance -Namespace root/LibreHardwareMonitor -ClassName Sensor -ErrorAction SilentlyContinue | Where-Object { $_.SensorType -eq 'Temperature' -and ($_.Name -like '*Core*' -or $_.Name -like '*CPU Package*') } | Select-Object -First 1 -ExpandProperty Value
                    if ($lhm) { $cpuTemp = "$([math]::Round($lhm))°C" }
                } catch {}
                if ($cpuTemp -eq "N/A") {
                    try {
                        $ohm = Get-CimInstance -Namespace root/OpenHardwareMonitor -ClassName Sensor -ErrorAction SilentlyContinue | Where-Object { $_.SensorType -eq 'Temperature' -and ($_.Name -like '*CPU*' -or $_.Name -like '*Core*') } | Select-Object -First 1 -ExpandProperty Value
                        if ($ohm) { $cpuTemp = "$([math]::Round($ohm))°C" }
                    } catch {}
                }
                if ($cpuTemp -eq "N/A") {
                    try {
                        $acpi = Get-CimInstance -Namespace root/wmi -ClassName MSAcpi_ThermalZoneTemperature -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty CurrentTemperature
                        if ($acpi) { $cpuTemp = "$([math]::Round(($acpi / 10) - 273.15))°C" }
                    } catch {}
                }
                try {
                    $intelLuid = $null
                    $mems = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUAdapterMemory -ErrorAction SilentlyContinue
                    $intelVC = Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '*Intel*' -or $_.AdapterCompatibility -like '*Intel*' }
                    if ($intelVC) {
                        foreach ($m in $mems) {
                            if ($m.DedicatedUsage -lt 500000000) {
                                if ($m.Name -match "luid_(0x[0-9a-fA-F]+_0x[0-9a-fA-F]+)") {
                                    $intelLuid = $Matches[1]
                                    break
                                }
                            }
                        }
                    }
                    if ($intelLuid) {
                        $util = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUEngine -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*$intelLuid*" -and $_.Name -like '*engtype_3D*' } | Measure-Object -Property UtilizationPercentage -Sum | Select-Object -ExpandProperty Sum
                        if ($util -ne $null) { $intelUsage = "$util%" }
                    }
                } catch {}
                if ($cpuTemp -ne "N/A") {
                    $intelTemp = $cpuTemp
                }
                $res = @{ cpuTemp = $cpuTemp; intelUsage = $intelUsage; intelTemp = $intelTemp }
                $res | ConvertTo-Json
                """
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=8, startupinfo=startupinfo)
                if res.stdout.strip():
                    stats = json.loads(res.stdout.strip())
                    cpu_temp = stats.get("cpuTemp", "N/A")
                    intel_usage = stats.get("intelUsage", "N/A")
                    intel_temp = stats.get("intelTemp", "N/A")
                else:
                    cpu_temp, intel_usage, intel_temp = "N/A", "N/A", "N/A"
                
                self.client_hardware_data = {
                    "cpu": f"{cpu_usage} ({cpu_temp})",
                    "nv_gpu": f"{nv_usage} ({nv_temp})",
                    "intel_gpu": f"{intel_usage} ({intel_temp})"
                }
            except Exception:
                pass
            time.sleep(5)

    # ==========================================
    # UNIFIED SERVER CLI DRAW TUI
    # ==========================================
    def draw_dashboard(self):
        lines = []
        width = 70
        
        lines.append(f"{colorama.Fore.CYAN}=================== YOUTUBE KARAOKE BOT ==================={colorama.Style.RESET_ALL}")
        
        # Hardware Status PC Server
        local_ip = get_local_ip()
        lines.append(f"  {colorama.Fore.GREEN}PC UTAMA (Server){colorama.Style.RESET_ALL} : {self.local_hardware_info}")
        lines.append(f"  LAN IP/Port       : {colorama.Fore.YELLOW}{local_ip}:{self.server_port}{colorama.Style.RESET_ALL} | Sisa Antrean: {len(self.remaining_songs)} lagu")
        lines.append(f"{colorama.Fore.CYAN}-----------------------------------------------------------{colorama.Style.RESET_ALL}")
        
        # 1. Local PC Workers
        lines.append(f"{colorama.Fore.YELLOW}STATUS WORKER PC LOKAL:{colorama.Style.RESET_ALL}")
        with self.worker_states_lock:
            for i, w in enumerate(self.worker_states):
                slot_num = i + 1
                if w['song']:
                    song_disp = w['song']
                    if len(song_disp) > 35:
                        song_disp = song_disp[:32] + "..."
                    phase_str = f"{w['phase']:12}"
                    percent_str = f"({w['percent']:.0f}%)" if w['percent'] > 0 else ""
                    color = colorama.Fore.GREEN
                    if "Cari" in w['phase']:
                        color = colorama.Fore.BLUE
                    elif "HDD" in w['phase']:
                        color = colorama.Fore.MAGENTA
                    lines.append(f"  {slot_num}. {color}{phase_str}{colorama.Style.RESET_ALL} : {song_disp} {colorama.Fore.WHITE}{percent_str}{colorama.Style.RESET_ALL}")
                else:
                    lines.append(f"  {slot_num}. {colorama.Fore.LIGHTBLACK_EX}Idle{colorama.Style.RESET_ALL}")
                    
        lines.append(f"{colorama.Fore.CYAN}-----------------------------------------------------------{colorama.Style.RESET_ALL}")
        
        # 2. Remote Laptop Helper Workers & HW
        is_helper_active = (time.time() - self.helper_last_seen) <= 35
        if is_helper_active:
            lines.append(f"  {colorama.Fore.GREEN}LAPTOP HELPER (Aktif){colorama.Style.RESET_ALL} : {self.helper_hardware_info}")
            lines.append(f"{colorama.Fore.YELLOW}STATUS WORKER LAPTOP HELPER:{colorama.Style.RESET_ALL}")
            with self.helper_workers_lock:
                for i, w in enumerate(self.helper_workers):
                    slot_num = i + 1
                    song = w.get('song', '')
                    if song:
                        song_disp = song
                        if len(song_disp) > 35:
                            song_disp = song_disp[:32] + "..."
                        phase_str = f"{w.get('phase', 'Idle'):12}"
                        percent_str = f"({w.get('percent', 0):.0f}%)" if w.get('percent', 0) > 0 else ""
                        color = colorama.Fore.GREEN
                        if "Cari" in phase_str:
                            color = colorama.Fore.BLUE
                        elif "HDD" in phase_str:
                            color = colorama.Fore.MAGENTA
                        lines.append(f"  {slot_num}. {color}{phase_str}{colorama.Style.RESET_ALL} : {song_disp} {colorama.Fore.WHITE}{percent_str}{colorama.Style.RESET_ALL}")
                    else:
                        lines.append(f"  {slot_num}. {colorama.Fore.LIGHTBLACK_EX}Idle{colorama.Style.RESET_ALL}")
        else:
            lines.append(f"  {colorama.Fore.RED}LAPTOP HELPER (Disconnected / Inactive){colorama.Style.RESET_ALL}")
            lines.append(f"{colorama.Fore.YELLOW}STATUS WORKER LAPTOP HELPER: {colorama.Fore.RED}helper disconnected{colorama.Style.RESET_ALL}")
            for _ in range(10):
                lines.append("")
                
        lines.append(f"{colorama.Fore.CYAN}-----------------------------------------------------------{colorama.Style.RESET_ALL}")
        
        # 3. History logs (Last finished)
        lines.append(f"{colorama.Fore.YELLOW}RIWAYAT UNDUHAN TERAKHIR:{colorama.Style.RESET_ALL}")
        with self.finished_queue_lock:
            for log in self.finished_queue:
                log_disp = log
                if len(log_disp) > width - 4:
                    log_disp = log_disp[:width - 7] + "..."
                lines.append(f"  * {log_disp}")
            for _ in range(5 - len(self.finished_queue)):
                lines.append("")
                
        lines.append(f"{colorama.Fore.CYAN}-----------------------------------------------------------{colorama.Style.RESET_ALL}")
        
        # 4. Overall statistics
        processed_count = self.success_count + self.failed_count + self.skipped_count
        percent_total = (processed_count / self.total_songs) * 100.0 if self.total_songs > 0 else 0.0
        
        pbar = self.make_progress_bar(percent_total, width=15)
        
        # Calculate ETA
        processed_in_session = self.success_count + self.failed_count
        if processed_in_session > 0:
            elapsed = time.time() - self.session_start_time
            time_per_song = elapsed / processed_in_session
            remaining_to_process = max(0, self.total_songs - processed_count)
            meta_seconds = remaining_to_process * time_per_song
            
            el_h = int(elapsed // 3600)
            el_m = int((elapsed % 3600) // 60)
            el_s = int(elapsed % 60)
            elapsed_str = f"{el_h:02d}:{el_m:02d}:{el_s:02d}"
            
            eta_h = int(meta_seconds // 3600)
            eta_m = int((meta_seconds % 3600) // 60)
            eta_s = int(meta_seconds % 60)
            eta_str = f"{eta_h}j {eta_m}m {eta_s}d" if eta_h > 0 else (f"{eta_m}m {eta_s}d" if eta_m > 0 else f"{eta_s}d")
        else:
            elapsed_str = "00:00:00"
            eta_str = "--:--"
            
        lines.append(f"  Progress Total: {pbar} {percent_total:.1f}% ({processed_count}/{self.total_songs})")
        lines.append(f"  Status        : {colorama.Fore.GREEN}Sukses: {self.success_count + self.skipped_count}{colorama.Style.RESET_ALL} | {colorama.Fore.RED}Gagal (Total): {self.failed_count}{colorama.Style.RESET_ALL} | Skip: {self.skipped_count}")
        lines.append(f"  Waktu Jalan   : {elapsed_str} | Sisa Waktu (ETA): {eta_str}")
        lines.append(f"  Penyimpanan   : {self.storage_mgr.active_dir}")
        lines.append(f"{colorama.Fore.CYAN}==========================================================={colorama.Style.RESET_ALL}")
        
        CL = "\033[K"
        output = f"{CL}\n".join(lines) + CL
        
        if not self.first_draw:
            sys.stdout.write(f"\033[{self.tui_height}A\r")
            
        sys.stdout.write(output + "\n")
        sys.stdout.flush()
        self.first_draw = False

    def dashboard_loop(self):
        while self.running:
            if self.role == "server":
                self.draw_dashboard()
            time.sleep(0.3)

    def history_saver_loop(self):
        while self.running:
            time.sleep(5)
            if getattr(self, 'history_dirty', False):
                self.history_dirty = False
                self.save_history(force=True)
                self.update_clean_playlist_excel(force=True)

    def monitor_helper_timeout(self):
        while self.running:
            time.sleep(5)
            now = time.time()
            if self.helper_last_seen > 0 and (now - self.helper_last_seen > 60):
                tasks_to_release = []
                with self.history_lock:
                    tasks_to_release = list(self.active_helper_tasks.keys())
                    for song_key in tasks_to_release:
                        task_info = self.active_helper_tasks.pop(song_key, None)
                        if task_info:
                            if song_key in self.history:
                                self.history[song_key]['status'] = 'Pending'
                                self.history[song_key]['error_msg'] = 'Helper disconnected / RTO'
                                self.save_history()
                                self.log_finished(f"{colorama.Fore.YELLOW}[RE-QUEUE]{colorama.Style.RESET_ALL} {song_key} - Helper RTO")

    def local_worker_thread(self):
        while self.running:
            song = self.get_next_pending_song_local()
            if not song:
                # If there are no songs currently in queue, check if we are still waiting
                # for other active local workers or helper tasks to finish.
                active_local = 0
                with self.worker_states_lock:
                    active_local = sum(1 for w in self.worker_states if w['song'] != "")
                    
                has_active_work = False
                with self.queue_lock:
                    # If helper tasks are active, or queue still has songs, or other local workers are active
                    if self.remaining_songs or self.active_helper_tasks or (active_local > 1):
                        has_active_work = True
                        
                if has_active_work:
                    time.sleep(0.5)
                    continue
                else:
                    break
            self.process_song_local(song)
            time.sleep(0.01)

    # ==========================================
    # CLIENT MODE (LAPTOP HELPER) IMPLEMENTATION
    # ==========================================
    def draw_client_dashboard(self):
        lines = []
        lines.append(f"{colorama.Fore.CYAN}=================== LAPTOP HELPER WORKERS ==================={colorama.Style.RESET_ALL}")
        lines.append(f"  Terhubung ke PC Utama: {colorama.Fore.GREEN}{self.server_ip}:{self.server_port}{colorama.Style.RESET_ALL}")
        cpu = self.client_hardware_data.get("cpu", "N/A")
        nv = self.client_hardware_data.get("nv_gpu", "N/A")
        intel = self.client_hardware_data.get("intel_gpu", "N/A")
        lines.append(f"  CPU Usage            : {cpu}")
        lines.append(f"  RTX 3050 | Intel Xe  : {nv} | {intel}")
        
        status_msg = getattr(self, 'client_status_msg', 'Normal')
        if "Gagal" in status_msg or "Error" in status_msg or "Diskoneksi" in status_msg or "Koneksi" in status_msg:
            color = colorama.Fore.RED
        else:
            color = colorama.Fore.GREEN
        lines.append(f"  Status Jaringan LAN  : {color}{status_msg}{colorama.Style.RESET_ALL}")
        
        lines.append(f"{colorama.Fore.CYAN}-------------------------------------------------------------{colorama.Style.RESET_ALL}")
        
        with self.client_worker_states_lock:
            for i, w in enumerate(self.client_worker_states):
                slot_num = i + 1
                if w['song']:
                    song_disp = w['song']
                    if len(song_disp) > 35:
                        song_disp = song_disp[:32] + "..."
                    phase_str = f"{w['phase']:12}"
                    percent_str = f"({w['percent']:.0f}%)" if w['percent'] > 0 else ""
                    color = colorama.Fore.GREEN
                    if "Cari" in w['phase']:
                        color = colorama.Fore.BLUE
                    lines.append(f"  {slot_num}. {color}{phase_str}{colorama.Style.RESET_ALL} : {song_disp} {colorama.Fore.WHITE}{percent_str}{colorama.Style.RESET_ALL}")
                else:
                    lines.append(f"  {slot_num}. {colorama.Fore.LIGHTBLACK_EX}Idle{colorama.Style.RESET_ALL}")
                    
        lines.append(f"{colorama.Fore.CYAN}============================================================={colorama.Style.RESET_ALL}")
        
        CL = "\033[K"
        output = f"{CL}\n".join(lines) + CL
        
        if not self.client_first_draw:
            sys.stdout.write(f"\033[17A\r")
        sys.stdout.write(output + "\n")
        sys.stdout.flush()
        self.client_first_draw = False

    def client_reporter_loop(self):
        """Sends heartbeats and hardware data to PC server."""
        while self.running:
            try:
                url = f"http://{self.server_ip}:{self.server_port}/report_status"
                with self.client_worker_states_lock:
                    states_payload = list(self.client_worker_states)
                
                payload = {
                    "workers": states_payload,
                    "hardware": self.client_hardware_data
                }
                
                data = json.dumps(payload).encode('utf-8')
                req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
                with urllib.request.urlopen(req, timeout=3) as resp:
                    resp.read()
            except Exception:
                pass
            time.sleep(0.5)

    def process_song_client(self, song, worker_id):
        artist = song['artist']
        title = song['title']
        category = song['category']
        song_key = f"{artist} - {title}"
        
        # Check if it's a retry/failed song
        is_retry = song_key in self.failed_songs_keys
        
        temp_dir = os.path.join(self.proj_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        safe_filename = excel_handler.clean_filename(f"{artist} - {title}.mp4")
        temp_output_path = os.path.join(temp_dir, f"client_{worker_id}_{safe_filename}")
        
        def progress_callback(percent, phase):
            self.update_client_worker(worker_id, song_key, phase, percent)

        # 1. Search YouTube
        try:
            self.update_client_worker(worker_id, song_key, "Mencari Link", 0)
            candidates_list = downloader.search_youtube_karaoke(artist, title)
        except Exception as e:
            try:
                url = f"http://{self.server_ip}:{self.server_port}/release_task"
                data = json.dumps({"song_key": song_key, "error_msg": f"Tidak ditemukan: {str(e)}"}).encode('utf-8')
                req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
                with urllib.request.urlopen(req, timeout=5) as resp:
                    resp.read()
            except:
                pass
            self.update_client_worker(worker_id, "", "Idle", 0)
            return

        # 2. Download & Compress locally using GPU (try each candidate in order of score)
        success = False
        last_error = ""
        res = None
        duration_str = "0:00"
        
        for index, cand in enumerate(candidates_list):
            video_url = cand['url']
            duration = cand['duration']
            duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else "0:00"
            
            if os.path.exists(temp_output_path):
                try: os.remove(temp_output_path)
                except: pass
                
            try:
                msg_suffix = f" (Coba {index+1}/{len(candidates_list)})" if len(candidates_list) > 1 else ""
                def client_progress_callback(percent, phase):
                    progress_callback(percent, f"{phase}{msg_suffix}")
                    
                res = downloader.download_and_compress(
                    video_url=video_url,
                    output_filepath=temp_output_path,
                    target_size_mb=self.config['target_size_mb'],
                    audio_bitrate_kbps=self.config['audio_bitrate_kbps'],
                    max_resolution=self.config.get('max_resolution', '720p'),
                    progress_callback=client_progress_callback,
                    use_gpu=self.config.get('use_gpu_acceleration', True),
                    gpu_encoder=["h264_nvenc", "h264_qsv"],
                    max_gpu_sessions=5,
                    cpu_threads=1,
                    is_retry=is_retry
                )
                success = True
                break
            except Exception as e:
                last_error = str(e)
                continue
                
        if success and res:
            try:
                # 3. Upload completed video file to Server PC
                self.update_client_worker(worker_id, song_key, "Mengunggah...", 98)
                url = f"http://{self.server_ip}:{self.server_port}/upload"
                file_size_mb = res['file_size_mb']
                
                headers = {
                    'X-Song-Key': song_key,
                    'X-Category': category,
                    'X-Artist': artist,
                    'X-Title': title,
                    'X-File-Size-MB': str(file_size_mb),
                    'X-Duration-Str': duration_str,
                    'Content-Type': 'application/octet-stream',
                    'Content-Length': str(os.path.getsize(temp_output_path))
                }
                
                with open(temp_output_path, 'rb') as f:
                    req = urllib.request.Request(url, data=f, headers=headers, method='POST')
                    with urllib.request.urlopen(req, timeout=180) as resp:
                        resp.read()
                        
                try: os.remove(temp_output_path)
                except: pass
                self.update_client_worker(worker_id, "", "Idle", 0)
            except Exception as e:
                if os.path.exists(temp_output_path):
                    try: os.remove(temp_output_path)
                    except: pass
                try:
                    url = f"http://{self.server_ip}:{self.server_port}/release_task"
                    data = json.dumps({"song_key": song_key, "error_msg": f"Upload error: {str(e)}"}).encode('utf-8')
                    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        resp.read()
                except:
                    pass
                self.update_client_worker(worker_id, "", "Idle", 0)
        else:
            if os.path.exists(temp_output_path):
                try: os.remove(temp_output_path)
                except: pass
            try:
                url = f"http://{self.server_ip}:{self.server_port}/release_task"
                # Show specific failure type
                if "mendownload" in last_error or "YouTube" in last_error:
                    err_lbl = "Download error"
                else:
                    err_lbl = "Transcode error"
                data = json.dumps({"song_key": song_key, "error_msg": f"{err_lbl}: {last_error}"}).encode('utf-8')
                req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
                with urllib.request.urlopen(req, timeout=5) as resp:
                    resp.read()
            except:
                pass
            self.update_client_worker(worker_id, "", "Idle", 0)

    def run_client_loop(self):
        self.client_status_msg = "Menghubungkan..."
        
        # Start reporter and hardware monitoring threads
        self.running = True
        reporter_thread = threading.Thread(target=self.client_reporter_loop)
        reporter_thread.daemon = True
        reporter_thread.start()
        
        client_hw_thread = threading.Thread(target=self.client_hardware_monitor_loop)
        client_hw_thread.daemon = True
        client_hw_thread.start()
        
        # Clear screen for TUI drawing
        os.system('cls' if os.name == 'nt' else 'clear')
        
        def client_tui_loop():
            while self.running:
                self.draw_client_dashboard()
                time.sleep(0.3)
                
        tui_thread = threading.Thread(target=client_tui_loop)
        tui_thread.daemon = True
        tui_thread.start()
        
        executor = ThreadPoolExecutor(max_workers=self.max_workers)
        
        while self.running:
            # Check physically IDLE workers in client states (anti-drift check)
            with self.client_worker_states_lock:
                idle_count = sum(1 for w in self.client_worker_states if w['song'] == "")
                
            if idle_count == 0:
                time.sleep(0.1)
                continue
                
            try:
                url = f"http://{self.server_ip}:{self.server_port}/get_work"
                req = urllib.request.Request(url, method='GET')
                
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                
                self.client_status_msg = "Terhubung (Mencari Pekerjaan...)"
                    
                if data.get('status') == 'empty':
                    time.sleep(1)
                    continue
                elif 'artist' in data:
                    # Find a free worker slot and reserve it
                    worker_id = -1
                    with self.client_worker_states_lock:
                        for i in range(self.max_workers):
                            if self.client_worker_states[i]['song'] == "":
                                self.client_worker_states[i]['song'] = f"{data['artist']} - {data['title']}"
                                self.client_worker_states[i]['phase'] = "Reserved"
                                self.client_worker_states[i]['percent'] = 0
                                worker_id = i
                                break
                    if worker_id != -1:
                        # Submit task to the free worker slot
                        executor.submit(self.process_song_client, data, worker_id)
                
            except Exception as e:
                import traceback
                log_file = os.path.join(self.proj_dir, "client_error.log")
                try:
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error in run_client_loop: {str(e)}\n")
                        traceback.print_exc(file=f)
                except:
                    pass
                self.client_status_msg = f"Koneksi Gagal ({str(e)[:25]})"
                time.sleep(1)

    def check_and_replace_poor_downloads(self):
        """
        Scan completed history, check local file size and duration.
        If file size is < 4MB or duration < 60s, delete file and set status back to Pending.
        """
        print("\n[PEMBERSIHAN] Memulai pemindaian file berkualitas rendah...")
        cleaned_count = 0
        history_changed = False
        
        with self.history_lock:
            history_copy = list(self.history.items())
            
        for song_key, info in history_copy:
            if info.get('status') == 'Completed':
                filepath = info.get('file_path', '')
                if not filepath:
                    continue
                    
                file_exists = os.path.exists(filepath)
                should_clean = False
                reason = ""
                
                if not file_exists:
                    should_clean = True
                    reason = "File tidak ditemukan di disk"
                else:
                    try:
                        size_bytes = os.path.getsize(filepath)
                        size_mb = size_bytes / (1024 * 1024)
                        
                        dur_str = info.get('duration_str', '0:00')
                        duration_secs = 0
                        if ':' in dur_str:
                            parts = dur_str.split(':')
                            if len(parts) == 2:
                                duration_secs = int(parts[0]) * 60 + int(parts[1])
                            elif len(parts) == 3:
                                duration_secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                        else:
                            try:
                                duration_secs = float(dur_str)
                            except:
                                pass
                                
                        if size_mb < 4.0:
                            should_clean = True
                            reason = f"Ukuran terlalu kecil ({size_mb:.2f} MB)"
                        elif duration_secs > 0 and duration_secs < 60:
                            should_clean = True
                            reason = f"Durasi terlalu pendek ({dur_str})"
                    except Exception as e:
                        should_clean = True
                        reason = f"Gagal membaca file: {str(e)}"
                        
                if should_clean:
                    print(f"  [RESET] {song_key} -> {reason}")
                    if file_exists:
                        try:
                            os.remove(filepath)
                        except Exception as e:
                            print(f"    Gagal menghapus file: {e}")
                            
                    with self.history_lock:
                        self.history[song_key].update({
                            'status': 'Pending',
                            'file_path': '',
                            'file_size_mb': 0,
                            'duration_str': '',
                            'error_msg': f'Dibersihkan otomatis: {reason}',
                            'retry_count': 0
                        })
                    cleaned_count += 1
                    history_changed = True
                    
        if history_changed:
            self.save_history(force=True)
            self.update_clean_playlist_excel(force=True)
            
        print(f"[PEMBERSIHAN] Selesai! Berhasil me-reset {cleaned_count} lagu berkualitas rendah ke status Pending.\n")

    def check_custom_redownload_list(self):
        """
        Check if a file 're_download_list.txt' exists in the main directory.
        If it exists, read line-by-line and delete local files & reset history status to Pending.
        """
        list_file = os.path.join(self.proj_dir, "re_download_list.txt")
        if not os.path.exists(list_file):
            return
            
        print(f"\n[DAFTAR KUSTOM] Ditemukan '{list_file}'. Memproses permintaan download ulang...")
        processed_count = 0
        history_changed = False
        
        try:
            with open(list_file, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"  [ERROR] Gagal membaca file: {e}")
            return
            
        for line in lines:
            target_key = None
            
            with self.history_lock:
                if line in self.history:
                    target_key = line
                else:
                    line_lower = line.lower()
                    for key in self.history.keys():
                        if key.lower() == line_lower:
                            target_key = key
                            break
                    if not target_key:
                        for key, info in self.history.items():
                            artist = info.get('artist', '')
                            title = info.get('title', '')
                            if (artist.lower() in line_lower and title.lower() in line_lower) or \
                               (line_lower == title.lower()):
                                target_key = key
                                break
                                
            if target_key:
                with self.history_lock:
                    info = self.history[target_key]
                    filepath = info.get('file_path', '')
                    
                print(f"  [HAPUS & RESET] {target_key}")
                if filepath and os.path.exists(filepath):
                    try:
                        os.remove(filepath)
                    except Exception as e:
                        print(f"    Gagal menghapus file: {e}")
                        
                with self.history_lock:
                    self.history[target_key].update({
                        'status': 'Pending',
                        'file_path': '',
                        'file_size_mb': 0,
                        'duration_str': '',
                        'error_msg': 'Permintaan download ulang kustom',
                        'retry_count': 0
                    })
                processed_count += 1
                history_changed = True
            else:
                print(f"  [LEWAT] Lagu '{line}' tidak ditemukan di database history.")
                
        if history_changed:
            self.save_history(force=True)
            self.update_clean_playlist_excel(force=True)
            
        processed_file = os.path.join(self.proj_dir, "re_download_list.processed.txt")
        try:
            if os.path.exists(processed_file):
                os.remove(processed_file)
            os.rename(list_file, processed_file)
            print(f"[DAFTAR KUSTOM] Selesai! {processed_count} lagu di-reset. File daftar diganti nama menjadi 're_download_list.processed.txt'.\n")
        except Exception as e:
            print(f"  [PERINGATAN] Gagal mengganti nama file daftar: {e}")

    def start(self):
        if self.role == "client":
            self.run_client_loop()
            return
            
        # SERVER / HOST MODE
        if self.clean_low_quality:
            self.check_and_replace_poor_downloads()
            
        self.check_custom_redownload_list()
        
        excel_path = self.config['excel_path']
        if not os.path.exists(excel_path):
            print(f"\n[Peringatan] File Excel tidak ditemukan di: {excel_path}")
            print("Mencari file Excel di folder proyek saat ini...")
            local_files = [f for f in os.listdir(self.proj_dir) if f.endswith(('.xls', '.xlsx'))]
            if local_files:
                print("Ditemukan file Excel lokal:")
                for i, f in enumerate(local_files):
                    print(f" [{i+1}] {f}")
                choice = input("Pilih nomor file (atau masukkan path lengkap file Anda): ").strip()
                if choice.isdigit() and 1 <= int(choice) <= len(local_files):
                    excel_path = os.path.join(self.proj_dir, local_files[int(choice)-1])
                elif choice:
                    excel_path = choice
            else:
                excel_path = input("Silakan masukkan path lengkap file Excel list lagu Anda: ").strip()
                excel_path = excel_path.replace('"', '').replace("'", "")

        if not excel_path or not os.path.exists(excel_path):
            print("File Excel input tidak valid. Bot dihentikan.")
            return

        print(f"\nMembaca list lagu dari: {excel_path}...")
        try:
            songs = excel_handler.read_song_list(excel_path)
            self.total_songs = len(songs)
            print(f"Berhasil membaca {self.total_songs} lagu.")
        except Exception as e:
            print(f"Gagal membaca file Excel: {e}")
            return
            
        if self.total_songs == 0:
            print("Daftar lagu kosong. Silakan isi file Excel Anda.")
            return
            
        self.update_clean_playlist_excel()
        
        # Check skipped / remaining (Reorder failed to the back, skip permanently if retried >= 2)
        normal_songs = []
        failed_songs = []
        history_changed = False
        
        for s in songs:
            song_key = f"{s['artist']} - {s['title']}"
            if song_key in self.history:
                hist = self.history[song_key]
                if hist.get('status') == 'Completed':
                    filepath = hist.get('file_path', '')
                    
                    # Smart check: if original path doesn't exist, check alternative active folder
                    if filepath and not os.path.exists(filepath):
                        marker = "Karaoke_Downloads"
                        if marker in filepath:
                            parts = filepath.split(marker, 1)
                            relative_part = parts[1].lstrip('\\/')
                            alt_path = os.path.join(self.storage_mgr.active_dir, relative_part)
                            if os.path.exists(alt_path):
                                hist['file_path'] = alt_path
                                filepath = alt_path
                                history_changed = True
                                
                    if filepath and os.path.exists(filepath):
                        self.skipped_count += 1
                        continue
                elif hist.get('status') == 'Failed':
                    retries = hist.get('retry_count', 0)
                    if retries >= 2: # Max 2 retries to prevent infinite loops
                        self.skipped_count += 1
                        continue
                    else:
                        failed_songs.append(s)
                        self.failed_songs_keys.add(song_key)
                        continue
            normal_songs.append(s)
            
        if history_changed:
            with self.history_lock:
                self.save_history()
            
        self.remaining_songs = normal_songs + failed_songs
            
        print(f"\nStatus: {self.skipped_count} lagu sudah selesai didownload (Skip).")
        print(f"Jumlah lagu yang perlu diproses: {len(self.remaining_songs)} lagu.")
        
        if not self.remaining_songs:
            print("\nSemua lagu dalam list sudah selesai didownload! Playlist Anda sudah ter-update rapi.")
            return
            
        print("\nMenyiapkan Server Jaringan LAN dan TUI Dashboard...")
        
        # Start HTTP Server
        server_thread = HTTPServerThread(self, "0.0.0.0", self.server_port)
        server_thread.start()
        
        time.sleep(1.5)
        
        self.session_start_time = time.time()
        os.system('cls' if os.name == 'nt' else 'clear')
        
        self.running = True
        
        # Start TUI dashboard thread
        dashboard_thread = threading.Thread(target=self.dashboard_loop)
        dashboard_thread.daemon = True
        dashboard_thread.start()
        
        # Start watchdog thread to cleanup helper tasks
        watchdog_thread = threading.Thread(target=self.monitor_helper_timeout)
        watchdog_thread.daemon = True
        watchdog_thread.start()
        
        # Start hardware monitoring thread
        hw_thread = threading.Thread(target=self.hardware_monitor_loop)
        hw_thread.daemon = True
        hw_thread.start()
        
        # Start background history saver thread
        saver_thread = threading.Thread(target=self.history_saver_loop)
        saver_thread.daemon = True
        saver_thread.start()
        
        # Run local PC worker threadpool
        try:
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for _ in range(self.max_workers):
                    futures.append(executor.submit(self.local_worker_thread))
                for future in as_completed(futures):
                    pass
        except KeyboardInterrupt:
            self.running = False
        finally:
            self.running = False
            server_thread.stop()
            dashboard_thread.join(timeout=1.0)
            
            # Final forced save of history and Excel playlist on exit
            self.save_history(force=True)
            self.update_clean_playlist_excel(force=True)
            
            # Final drawing
            self.draw_dashboard()
            print("\n==================================================")
            print("             SUMMARY DOWNLOAD KARAOKE             ")
            print("==================================================")
            print(f"Total Lagu di Excel  : {self.total_songs}")
            print(f"Lagu Berhasil Diunduh: {self.success_count}")
            print(f"Lagu Gagal Diunduh   : {self.failed_count}")
            print(f"Lagu Sudah Ada (Skip): {self.skipped_count}")
            print(f"Playlist Output Excel: {os.path.join(self.storage_mgr.active_dir, 'Karaoke_Playlist_Clean.xlsx')}")
            print("==================================================")
            print("Terima kasih telah menggunakan YouTube Karaoke Bot!\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YouTube Karaoke Downloader Bot")
    parser.add_argument("--role", choices=["server", "client"], default=None, help="Force role (server/client)")
    parser.add_argument("--ip", default=None, help="Override server IP")
    parser.add_argument("--port", type=int, default=None, help="Override server port")
    parser.add_argument("--clean-low-quality", action="store_true", help="Scan completed downloads and delete/reset those that are likely low quality (short duration or small file size).")
    args = parser.parse_args()
    
    bot = KaraokeBot(
        role_override=args.role,
        ip_override=args.ip,
        port_override=args.port,
        clean_low_quality=args.clean_low_quality
    )
    bot.start()
