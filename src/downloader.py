import os
import subprocess
import json
import re
import yt_dlp
import math
import shutil
import time
import random
import threading

# GPU session balancing variables for multi-GPU setups (Nvidia NVENC + Intel QSV + AMD AMF)
active_gpu_slots = {
    'h264_nvenc': 0,
    'h264_qsv': 0,
    'h264_amf': 0,
    'h264_mf': 0
}
gpu_slots_lock = threading.Lock()

def get_ffmpeg_paths():
    """Locate ffmpeg and ffprobe in the bin directory."""
    proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    bin_dir = os.path.join(proj_dir, "bin")
    
    ffmpeg_exe = os.path.join(bin_dir, "ffmpeg.exe")
    ffprobe_exe = os.path.join(bin_dir, "ffprobe.exe")
    
    # Fallback to system path if not found in bin
    if not os.path.exists(ffmpeg_exe):
        ffmpeg_exe = "ffmpeg"
    if not os.path.exists(ffprobe_exe):
        ffprobe_exe = "ffprobe"
        
    return ffmpeg_exe, ffprobe_exe

def score_youtube_title(title, artist, song_title):
    """
    Evaluate search result title to ensure it's a karaoke/instrumental version.
    Returns a score. High score = likely karaoke, negative score = likely vocal version.
    """
    title_lower = title.lower()
    artist_lower = artist.lower()
    song_title_lower = song_title.lower()
    
    score = 0
    has_positive = False
    
    # 0. Check for Multiplex Karaoke Channels (#right, #left, #r, #l) (+35 points)
    # If the title contains multiplex tags, we consider it a positive match and bypass vocal penalties
    has_multiplex = False
    multiplex_kws = ['#right', '#left', '#r', '#l']
    if any(kw in title_lower for kw in multiplex_kws):
        score += 35
        has_positive = True
        has_multiplex = True
    
    # 1. Super Positive Keywords: Clean Karaoke/No Vocal (+35 points)
    super_positives = [
        'no vocal', 'no vocals', 'tanpa vokal', 'tanpa vocal', 
        'off vocal', 'off-vocal', 'minus one', 'minus-one', 
        'backing track', 'backing-track'
    ]
    for kw in super_positives:
        if kw in title_lower:
            score += 35
            has_positive = True
            
    # 2. General Positive Keywords: Karaoke/Instrumental (+20 points)
    general_positives = [
        'karaoke', 'instrumental', 'instrumental cover', 'karaoke cover', 
        'instrumental version', 'karaoke version'
    ]
    for kw in general_positives:
        if kw in title_lower:
            score += 20
            has_positive = True
            
    # 3. Hard negative keywords: Explicitly contains vocals (Extremely penalized: -45 points)
    # Bypass this penalty if the title contains multiplex tags, as vocals can be turned off/removed
    if not has_multiplex:
        hard_negatives = [
            'with vocal', 'with vocals', 'dengan vokal', 'dengan vocal', 
            'ada vokal', 'ada vocal', 'vocal only', 'vocal version', 
            'clean vocals', 'vocal saja', 'lyric video with vocal',
            '+ vocal', '+ vokal', 'plus vocal', 'plus vokal',
            '(vocal)', '(vokal)', 'w/ vocal', 'w/vocal', 'vocals included',
            'with singer', 'ada penyanyi', 'vokal ada', 'vocals on'
        ]
        for kw in hard_negatives:
            if kw in title_lower:
                score -= 45
            
    # 4. Soft negative keywords (only penalized if NO positive keyword is found)
    # This prevents penalizing titles like "Official Karaoke Video" or "Original Instrumental"
    soft_negatives = ['original song', 'official music video', 'official video', 'official audio', 'original audio', 'live performance']
    if not has_positive:
        for kw in soft_negatives:
            if kw in title_lower:
                score -= 25
            
    # 5. Handle lyric videos (usually contain vocals unless marked as karaoke)
    if ('lyric' in title_lower or 'lirik' in title_lower) and not has_positive:
        score -= 20
        
    # 5. Check for relevance of Song Title
    words = re.findall(r'\w+', song_title_lower)
    match_words = 0
    for w in words:
        if len(w) > 1 and w in title_lower:
            match_words += 1
    if len(words) > 0:
        score += int((match_words / len(words)) * 10)
        
    # 6. Check for relevance of Artist
    artist_words = re.findall(r'\w+', artist_lower)
    match_artist = 0
    for w in artist_words:
        if len(w) > 1 and w in title_lower:
            match_artist += 1
    if len(artist_words) > 0:
        score += int((match_artist / len(artist_words)) * 10)
        
    # 7. Prioritize new/remake/cover versions for better audio/video quality (+15 score)
    # ONLY IF it is already identified as a karaoke track!
    if has_positive:
        remake_keywords = [
            'remake', 'cover', 'acoustic', 'akustik', 'piano', 'midi', 'keyboard', 
            'hd', '1080p', '720p', 'clean audio', 'high quality', 'hq', 'lirik cover'
        ]
        for kw in remake_keywords:
            if kw in title_lower:
                score += 15
            
    # 8. Deprioritize old/original/rip versions with lower quality (-12 score)
    original_keywords = [
        'original clip', 'klip asli', 'vokal asli', 'audio asli', 'dvd rip', 'vcd rip',
        'ld rip', 'ripan', 'vocal removed', 'vocal dihilangkan', 'vocal hilang'
    ]
    for kw in original_keywords:
        if kw in title_lower:
            score -= 12
            
    # 9. Strict Requirement: If no explicit karaoke/instrumental keyword is found, 
    # it is highly likely a vocal track. Heavily penalize it so it drops below 0.
    if not has_positive:
        score -= 50
            
    return score

def adjust_score_for_popularity(score, entry):
    """
    Adjust the karaoke candidate score based on video popularity and channel credibility.
    Only applies boosts/penalties to candidates that already have a positive score (meaning they matched title-based karaoke indicators).
    """
    if score <= 0:
        return score
        
    # 1. View Count points
    views = entry.get('view_count')
    if views is not None:
        if views >= 10000000: # 10M+ views
            score += 30
        elif views >= 1000000: # 1M+ views
            score += 20
        elif views >= 100000: # 100k+ views
            score += 12
        elif views >= 10000: # 10k+ views
            score += 6
        elif views < 1000:
            score -= 15 # Penalize extremely low views
            
    # 2. Channel Verification
    if entry.get('channel_is_verified'):
        score += 15
        
    # 3. Known Premium/High-Quality Karaoke Channels
    good_channels = [
        'sing king', 'singking', 'karaoke academy', 'starlight karaoke',
        'sing2piano', 'sing2guitar', 'karaoke version', 'acoustic karaoke',
        'lofi karaoke', 'he karaoke', 'karaoke365', 'sunfly karaoke',
        'zoom karaoke', 'musiplay', 'grapix', 'i-karaoke', 'karaoke channel',
        'pop karaoke', 'bensound', 'karaoke id', 'karaoke indonesia'
    ]
    
    channel_name = (entry.get('channel') or '').lower()
    uploader_name = (entry.get('uploader') or '').lower()
    uploader_id = (entry.get('uploader_id') or '').lower()
    
    if any(gc in channel_name or gc in uploader_name or gc in uploader_id for gc in good_channels):
        score += 20
        
    return score

class CandidateList(list):
    """
    Custom list subclass that allows backward-compatibility.
    If accessed as a dictionary (e.g. video_info['url']), it redirects to the first candidate.
    """
    def __getitem__(self, key):
        if isinstance(key, str):
            if self:
                return self[0][key]
            raise KeyError(key)
        return super().__getitem__(key)
        
    def get(self, key, default=None):
        if self:
            return self[0].get(key, default)
        return default

def search_youtube_karaoke(artist, title):
    """
    Search YouTube for the karaoke version of a song using multiple search entries
    and filtering by keyword scores to avoid vocal versions.
    Returns a CandidateList containing candidates with positive scores.
    """
    queries = [
        f"{artist} {title} karaoke",
        f"{artist} {title} instrumental"
    ]
    
    ffmpeg_exe, _ = get_ffmpeg_paths()
    ffmpeg_dir = os.path.dirname(ffmpeg_exe) if os.path.isabs(ffmpeg_exe) else None
    
    # We query up to 5 results to scan and select the best karaoke track
    ydl_opts = {
        'noplaylist': True,
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
        'no_warnings': True,
        'logger': MyLogger(),
    }
    if ffmpeg_dir:
        ydl_opts['ffmpeg_location'] = ffmpeg_dir

    candidates = []

    for query in queries:
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Search up to 5 results
                search_res = ydl.extract_info(f"ytsearch5:{query}", download=False)
                if search_res and 'entries' in search_res:
                    for entry in search_res['entries']:
                        entry_title = entry.get('title', '')
                        duration = entry.get('duration')
                        
                        # Validate duration (exclude compilation/long videos)
                        if duration and duration > 600: # 10 mins
                            continue
                            
                        # First pass: score based on title patterns only
                        score = score_youtube_title(entry_title, artist, title)
                        
                        candidates.append({
                            'url': entry.get('url') or f"https://www.youtube.com/watch?v={entry['id']}",
                            'title': entry_title,
                            'duration': duration,
                            'score': score,
                            'entry_flat': entry
                        })
        except Exception:
            continue

    if candidates:
        valid_candidates = [c for c in candidates if c['score'] > 0]
        if valid_candidates:
            # Sort by title-score descending to perform second-pass popularity scoring on top candidates
            valid_candidates.sort(key=lambda x: x['score'], reverse=True)
            
            # Setup full ydl options to fetch view count and channel info
            ydl_opts_full = dict(ydl_opts)
            ydl_opts_full['extract_flat'] = False
            
            # Retrieve full metadata only for top 3 candidates
            for c in valid_candidates[:3]:
                try:
                    with yt_dlp.YoutubeDL(ydl_opts_full) as ydl_full:
                        full_info = ydl_full.extract_info(c['url'], download=False)
                        if full_info:
                            c['score'] = adjust_score_for_popularity(c['score'], full_info)
                            c['title'] = full_info.get('title', c['title'])
                            c['duration'] = full_info.get('duration', c['duration'])
                except Exception:
                    # Fallback to adjusting with flat entry if full info retrieval fails
                    c['score'] = adjust_score_for_popularity(c['score'], c['entry_flat'])
            
            # Re-sort valid candidates after adjusting for popularity
            valid_candidates.sort(key=lambda x: x['score'], reverse=True)
            
            # Clean up temporary entry_flat key
            for c in valid_candidates:
                c.pop('entry_flat', None)
                
            return CandidateList(valid_candidates)
            
        # If no candidates have score > 0, raise the vocal exception using the highest score candidate
        candidates.sort(key=lambda x: x['score'], reverse=True)
        best_candidate = candidates[0]
        best_candidate.pop('entry_flat', None)
        raise Exception(f"Versi karaoke tidak ditemukan di YouTube (hanya ditemukan versi vokal: '{best_candidate['title']}')")
        
    raise Exception("Lagu tidak ditemukan di YouTube.")

def get_video_duration_ffprobe(filepath):
    """Get the duration of a video file using ffprobe."""
    _, ffprobe_exe = get_ffmpeg_paths()
    try:
        cmd = [
            ffprobe_exe, 
            '-v', 'error', 
            '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1', 
            filepath
        ]
        # In Windows, creationflags=0x08000000 hides the cmd window
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, startupinfo=startupinfo)
        return float(result.stdout.strip())
    except Exception:
        return None

def get_audio_codec_ffprobe(filepath):
    """Get the audio codec name of a video file using ffprobe."""
    _, ffprobe_exe = get_ffmpeg_paths()
    try:
        cmd = [
            ffprobe_exe, 
            '-v', 'error', 
            '-select_streams', 'a:0',
            '-show_entries', 'stream=codec_name', 
            '-of', 'default=noprint_wrappers=1:nokey=1', 
            filepath
        ]
        import subprocess
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True, startupinfo=startupinfo)
        return result.stdout.strip().lower()
    except Exception:
        return None

class MyLogger(object):
    def debug(self, msg):
        pass
    def warning(self, msg):
        pass
    def error(self, msg):
        pass

def download_and_compress(video_url, output_filepath, target_size_mb=9.5, audio_bitrate_kbps=128, max_resolution="480p", progress_callback=None, use_gpu=True, gpu_encoder="h264_mf", max_gpu_sessions=2, cpu_threads=2, is_retry=False):
    """
    Downloads the YouTube video and compresses it using FFmpeg to meet format/size constraints.
    """
    acquired_encoder = None
    temp_output_filepath = None
    
    # Convert gpu_encoder to a list of encoders to try
    encoders_to_try = [gpu_encoder] if isinstance(gpu_encoder, str) else list(gpu_encoder)
    
    # Extract resolution height
    res_height = 480
    if max_resolution:
        res_match = re.search(r'(\d+)', str(max_resolution))
        if res_match:
            res_height = int(res_match.group(1))
            
    proj_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    temp_dir = os.path.join(proj_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    ffmpeg_exe, ffprobe_exe = get_ffmpeg_paths()
    ffmpeg_dir = os.path.dirname(ffmpeg_exe) if os.path.isabs(ffmpeg_exe) else None
    
    # Unique temporary files
    song_id = re.sub(r'\W+', '', os.path.basename(output_filepath))
    temp_download_tmpl = os.path.join(temp_dir, f"{song_id}_raw.%(ext)s")
    
    # Progress hook for yt-dlp
    def ytdl_hook(d):
        if progress_callback and d['status'] == 'downloading':
            total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
            downloaded = d.get('downloaded_bytes', 0)
            percent = 0.0
            if total > 0:
                percent = (downloaded / total) * 100.0
            progress_callback(percent * 0.5, "Mendownload...")

    # yt-dlp options (limiting socket timeouts and retries to prevent long hangs on bad videos)
    ydl_opts = {
        'format': f'bestvideo[height<={res_height}]+bestaudio/best[height<={res_height}]/best',
        'outtmpl': temp_download_tmpl,
        'quiet': True,
        'no_warnings': True,
        'logger': MyLogger(),
        'progress_hooks': [ytdl_hook],
        'socket_timeout': 10,
        'retries': 1,
    }
    if ffmpeg_dir:
        ydl_opts['ffmpeg_location'] = ffmpeg_dir

    # Use a faster delay (0.1 - 0.4s) for retry/failed songs to speed up processing
    delay = random.uniform(0.1, 0.4) if is_retry else random.uniform(1.0, 3.0)
    time.sleep(delay)

    # 1. Download Video
    downloaded_file = None
    try:
        if progress_callback:
            progress_callback(5.0, "Mencari link...")
            
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)
            temp_filename = ydl.prepare_filename(info)
            base_temp, _ = os.path.splitext(temp_filename)
            
            for f in os.listdir(temp_dir):
                f_path = os.path.join(temp_dir, f)
                if f_path.startswith(base_temp) and f_path != temp_download_tmpl:
                    downloaded_file = f_path
                    break
                    
            if not downloaded_file or not os.path.exists(downloaded_file):
                files = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if song_id in f and "_raw" in f]
                if files:
                    downloaded_file = files[0]
                    
        if not downloaded_file or not os.path.exists(downloaded_file):
            raise Exception("File hasil download tidak ditemukan di folder temp.")
            
    except Exception as e:
        if downloaded_file and os.path.exists(downloaded_file):
            try: os.remove(downloaded_file)
            except: pass
        raise Exception(f"Gagal mendownload dari YouTube: {str(e)}")

    # 2. Transcode & Compress using FFmpeg
    try:
        if progress_callback:
            progress_callback(55.0, "Membaca durasi video...")
            
        # Try to acquire a GPU encoding session slot
        if use_gpu:
            with gpu_slots_lock:
                for enc in encoders_to_try:
                    limit = 5 if enc in ['h264_nvenc', 'h264_qsv'] else max_gpu_sessions
                    if active_gpu_slots.get(enc, 0) < limit:
                        active_gpu_slots[enc] = active_gpu_slots.get(enc, 0) + 1
                        acquired_encoder = enc
                        break
            
        duration = get_video_duration_ffprobe(downloaded_file)
        if not duration:
            duration = info.get('duration') or 240.0
            
        target_bits = target_size_mb * 1024 * 1024 * 8
        total_bitrate_bps = target_bits / duration
        audio_bitrate_bps = audio_bitrate_kbps * 1024
        
        video_bitrate_bps = total_bitrate_bps - audio_bitrate_bps
        video_bitrate_kbps = video_bitrate_bps / 1024
        
        if video_bitrate_kbps < 80:
            video_bitrate_kbps = 80
            audio_bitrate_kbps = max(96, audio_bitrate_kbps - 32)
        elif video_bitrate_kbps > 1500:
            video_bitrate_kbps = 1500
            
        temp_output_filepath = os.path.join(temp_dir, f"{song_id}_compressed.mp4")
        
        audio_codec = get_audio_codec_ffprobe(downloaded_file)
        audio_args = ['-c:a', 'copy'] if audio_codec == 'aac' else ['-c:a', 'aac', '-b:a', f"{audio_bitrate_kbps}k"]
        
        commands_to_try = []
        if acquired_encoder:
            gpu_cmd = [
                ffmpeg_exe,
                '-y',
                '-i', downloaded_file,
                '-threads', str(cpu_threads),
                '-vf', f'scale=-2:min({res_height}\\,ih)',
                '-c:v', acquired_encoder,
                '-b:v', f"{video_bitrate_kbps:.0f}k"
            ] + audio_args + [temp_output_filepath]
            commands_to_try.append((gpu_cmd, True))
            
        cpu_cmd = [
            ffmpeg_exe,
            '-y',
            '-i', downloaded_file,
            '-threads', str(cpu_threads),
            '-vf', f'scale=-2:min({res_height}\\,ih)',
            '-c:v', 'libx264',
            '-b:v', f"{video_bitrate_kbps:.0f}k",
            '-maxrate:v', f"{video_bitrate_kbps * 1.5:.0f}k",
            '-bufsize:v', f"{video_bitrate_kbps * 2:.0f}k",
            '-preset', 'veryfast'
        ] + audio_args + [temp_output_filepath]
        commands_to_try.append((cpu_cmd, False))
        
        time_pattern = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')
        success = False
        last_error = ""
        
        for cmd, is_gpu in commands_to_try:
            try:
                encoder_lbl = "GPU" if is_gpu else "CPU"
                if progress_callback:
                    progress_callback(60.0, f"Mengompres ({encoder_lbl})...")
                
                # Cleanup any partial files from previous attempts
                if os.path.exists(temp_output_filepath):
                    try: os.remove(temp_output_filepath)
                    except: pass
                    
                startupinfo = None
                if os.name == 'nt':
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    
                process = subprocess.Popen(
                    cmd, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE, 
                    text=True, 
                    bufsize=1, 
                    universal_newlines=True,
                    startupinfo=startupinfo
                )
                
                while True:
                    line = process.stderr.readline()
                    if not line:
                        break
                    
                    match = time_pattern.search(line)
                    if match and progress_callback:
                        hours, minutes, seconds = map(float, match.groups())
                        current_time = hours * 3600 + minutes * 60 + seconds
                        percent = min(100.0, (current_time / duration) * 100.0)
                        total_progress = 60.0 + (percent * 0.35)
                        progress_callback(total_progress, f"Mengompres ({encoder_lbl})...")
                        
                process.wait()
                
                if process.returncode == 0:
                    success = True
                    break
                else:
                    stderr_out = process.stderr.read()
                    last_error = f"FFmpeg {encoder_lbl} exit code {process.returncode}. Stderr: {stderr_out}"
            except Exception as e:
                last_error = str(e)
                continue
                
        if not success:
            raise Exception(f"Gagal melakukan transcode: {last_error}")
            
        # Move the completed file from NVMe (C:) to final destination (HDD)
        if progress_callback:
            progress_callback(97.0, "Memindahkan ke HDD...")
            
        # Prepare directory for final output
        final_dir = os.path.dirname(output_filepath)
        os.makedirs(final_dir, exist_ok=True)
        
        shutil.move(temp_output_filepath, output_filepath)
        
        if progress_callback:
            progress_callback(100.0, "Selesai!")
            
        # Get final file statistics
        file_size_bytes = os.path.getsize(output_filepath)
        file_size_mb = file_size_bytes / (1024 * 1024)
        
        # Return summary info
        return {
            'success': True,
            'file_size_mb': round(file_size_mb, 2),
            'duration_str': f"{int(duration // 60)}:{int(duration % 60):02d}"
        }
        
    except Exception as e:
        if temp_output_filepath and os.path.exists(temp_output_filepath):
            try: os.remove(temp_output_filepath)
            except: pass
        if os.path.exists(output_filepath):
            try: os.remove(output_filepath)
            except: pass
        raise Exception(f"Gagal mengompres video: {str(e)}")
        
    finally:
        # Release GPU session if acquired
        if acquired_encoder:
            with gpu_slots_lock:
                active_gpu_slots[acquired_encoder] = max(0, active_gpu_slots.get(acquired_encoder, 0) - 1)
                
        # Cleanup temporary downloaded file
        if downloaded_file and os.path.exists(downloaded_file):
            try: os.remove(downloaded_file)
            except: pass
            
        # Clear other temporary files matching song_id
        try:
            for f in os.listdir(temp_dir):
                if song_id in f:
                    os.remove(os.path.join(temp_dir, f))
        except:
            pass
