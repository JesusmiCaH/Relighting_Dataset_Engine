import os
import json
import shutil
import threading
import subprocess
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, send_file
import scrawler
import job_queue
import uploader
# import scraper (Removed V2)

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Config
BUFFER_DIR = "buffer"
OUTPUT_DATASET_DIR = "output_dataset"

# Ensure Dirs
if not os.path.exists(BUFFER_DIR):
    os.makedirs(BUFFER_DIR)
# Ensure Dirs
if not os.path.exists(BUFFER_DIR):
    os.makedirs(BUFFER_DIR)
if not os.path.exists(OUTPUT_DATASET_DIR):
    os.makedirs(OUTPUT_DATASET_DIR)

SETTINGS_FILE = "settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_settings_to_disk(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

@app.route('/')
def index():
    return redirect(url_for('view_search'))

# ==========================================
# SEARCH (Previously Buffer)
# ==========================================
@app.route('/search')
def view_search():
    images = []
    if os.path.exists(BUFFER_DIR):
        images = [f for f in os.listdir(BUFFER_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    images.sort()
    return render_template('search.html', images=images)

@app.route('/search/action', methods=['POST'])
def search_action():
    # Handle both single and multi-select
    # "filename" might be a list if multiple selected
    filenames = request.form.getlist('filename')
    action = request.form.get('action')
    
    if not filenames:
        # Fallback for single item submissions if not using list
        single = request.form.get('filename')
        if single:
            filenames = [single]

    count = 0
    for filename in filenames:
        src = os.path.join(BUFFER_DIR, filename)
        if not os.path.exists(src):
            continue
            
        if action == 'approve':
            # V2: Approve directly to output_dataset/stem/light0.jpg
            stem = os.path.splitext(filename)[0]
            
            # Smart Naming: Check if filename has keyword
            # Smart Naming: Check if filename has keyword
            # Format: keyword_idx or keyword___uuid (legacy)
            if "___" in stem:
                keyword = stem.split("___")[0]
            elif "_" in stem:
                # Try to split off the index
                parts = stem.rsplit("_", 1)
                if len(parts) == 2 and parts[1].isdigit():
                    keyword = parts[0]
                else:
                    keyword = stem
            else:
                keyword = stem # Fallback
                
            # Find next index for album
            # Expected: keyword_01, keyword_02
            idx = 1
            while True:
                candidate = f"{keyword}_{idx:02d}"
                if not os.path.exists(os.path.join(OUTPUT_DATASET_DIR, candidate)):
                    scene_name = candidate
                    break
                idx += 1
            
            scene_dir = os.path.join(OUTPUT_DATASET_DIR, scene_name)
            if not os.path.exists(scene_dir):
                os.makedirs(scene_dir)
                
            dst = os.path.join(scene_dir, "light0" + os.path.splitext(filename)[1])
            shutil.move(src, dst)
            
            count += 1
        elif action == 'delete':
            os.remove(src)
            count += 1
            
    flash(f"{action.title()}d {count} images")
    return redirect(url_for('view_search'))

@app.route('/api/search', methods=['POST'])
def run_search():
    mode = request.form.get('mode')
    
    keyword = ""
    if mode == "lucky":
        keyword = scrawler.get_lucky_prompt()
        flash(f"Feeling Lucky! Searching for: {keyword}")
    else:
        keyword = request.form.get('keyword')
        if not keyword:
            flash("Please enter a keyword.")
            return redirect(url_for('view_search'))
            
    # Clear buffer for new search? Or append? 
    # For V2 "Virtual Buffer", we might want to clear old "search results".
    # Let's clear buffer for now to keep it clean for the user.
    # Clear buffer removed as per request.
    # for f in os.listdir(BUFFER_DIR):
    #     try:
    #         os.remove(os.path.join(BUFFER_DIR, f))
    #     except:
    #         pass
        
    # Run Crawl
    # We download 10 images
    count = scrawler.google_crawl(keyword, max_num=10, buffer_dir=BUFFER_DIR)
    flash(f"Found {len(count)} images for '{keyword}'")
    
    return redirect(url_for('view_search'))

@app.route('/api/queue')
def get_queue_status():
    return job_queue.scan_all_jobs()

@app.route('/api/queue/overview')
def get_queue_overview():
    return job_queue.get_queue_overview()

@app.route('/api/delete_result', methods=['POST'])
def delete_result():
    scene_name = request.form.get('scene_name')
    filename = request.form.get('filename')
    
    if scene_name and filename:
        path = os.path.join(OUTPUT_DATASET_DIR, scene_name, filename)
        if os.path.exists(path):
            os.remove(path)
            flash(f"Deleted {filename}")
            
            # Update job status implicitly? 
            # scan_all_jobs will pick it up on next poll.
    
    return redirect(url_for('view_scene', scene_name=scene_name))

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(url_for('view_search'))
        
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(url_for('view_search'))
        
    if file:
        filename = file.filename
        # Simple secure check or just save
        # Ensure unique name to avoid overwrite? 
        # For now, let's just save.
        save_path = os.path.join(BUFFER_DIR, filename)
        file.save(save_path)
        flash(f"Uploaded {filename}")
        
    return redirect(url_for('view_search'))

@app.route('/api/buffer/clear', methods=['POST'])
def clear_buffer():
    if os.path.exists(BUFFER_DIR):
        for f in os.listdir(BUFFER_DIR):
            path = os.path.join(BUFFER_DIR, f)
            try:
                if os.path.isfile(path):
                    os.remove(path)
            except Exception as e:
                print(f"Error deleting {path}: {e}")
    flash("Buffer cleared!")
    return redirect(url_for('view_search'))

# ==========================================
# SETTINGS
# ==========================================
@app.route('/settings')
def view_settings():
    settings = load_settings()
    
    # Load Prompts
    prompts_list = []
    if os.path.exists("lighting_prompts.txt"):
        with open("lighting_prompts.txt", "r") as f:
            prompts_list = [line.strip() for line in f if line.strip()]
            
    system_prompt_content = ""
    if os.path.exists("system_prompt.txt"):
        with open("system_prompt.txt", "r") as f:
            system_prompt_content = f.read()
            
    return render_template('settings.html', settings=settings, prompts=prompts_list, system_prompt=system_prompt_content)

@app.route('/settings/save', methods=['POST'])
def save_settings():
    settings = load_settings()
    settings['steps'] = int(request.form.get('steps', 20))
    settings['cfg'] = float(request.form.get('cfg', 3.5))
    settings['sampler_name'] = request.form.get('sampler_name', 'euler')
    settings['scheduler'] = request.form.get('scheduler', 'normal')
    
    # Crawler Settings
    settings['crawler_source'] = request.form.get('crawler_source', 'Google')
    settings['images_per_batch'] = int(request.form.get('images_per_batch', 10))
    
    # Generation Mode
    settings['generation_mode'] = request.form.get('generation_mode', 'local')
    settings['api_max_parallel'] = int(request.form.get('api_max_parallel', 20))
    
    save_settings_to_disk(settings)
    
    # Save Prompts
    # Handle list input
    prompts = request.form.getlist('lighting_prompt')
    # Filter empty
    prompts = [p.strip() for p in prompts if p.strip()]
    
    if prompts:
        with open("lighting_prompts.txt", "w") as f:
            f.write("\n".join(prompts))
            
    sys_prompt = request.form.get('system_prompt')
    if sys_prompt:
        with open("system_prompt.txt", "w") as f:
            f.write(sys_prompt)

    flash("Settings saved!")
    return redirect(url_for('view_settings'))

# ==========================================
# DATASET (QUEUE)
# ==========================================
@app.route('/dataset')
def view_dataset():
    # V2: "Albums" are folders in OUTPUT_DATASET_DIR
    albums = []
    if os.path.exists(OUTPUT_DATASET_DIR):
        for name in os.listdir(OUTPUT_DATASET_DIR):
             if os.path.isdir(os.path.join(OUTPUT_DATASET_DIR, name)):
                 # Check if valid album (has light0?) - Optional, but good for cleanliness
                 if any(f.startswith('light0') for f in os.listdir(os.path.join(OUTPUT_DATASET_DIR, name))):
                     albums.append(name)
    albums.sort()
    return render_template('dataset.html', albums=albums)

@app.route('/api/process', methods=['POST'])
def run_processor():
    # Run processor in background for ALL
    subprocess.Popen(["python3", "processor.py"])
    flash("Started ComfyUI Processor for ALL...")
    return redirect(url_for('view_dataset'))

@app.route('/api/relight', methods=['POST'])
def run_relight():
    scene_name = request.form.get('scene_name')
    if not scene_name:
        flash("Error: No scene name provided")
        return redirect(url_for('view_dataset'))

    # Clean existing output for this scene EXCEPT light0
    # V2 Update: User requested non-destructive "Process" action.
    # We no longer delete existing files, just run processor to fill gaps.
    # scene_path = os.path.join(OUTPUT_DATASET_DIR, scene_name)
    # if os.path.exists(scene_path):
    #     for f in os.listdir(scene_path):
    #         if not f.startswith("light0"):
    #             try:
    #                 os.remove(os.path.join(scene_path, f))
    #             except:
    #                 pass
    
    # Run processor for TARGET ALBUM
    # Processor V2 accepts album name as target
    subprocess.Popen(["python3", "processor.py", "--target", scene_name])
    flash(f"Started Re-lighting for {scene_name}...")
    return redirect(url_for('view_dataset'))

# ==========================================
# GALLERY
# ==========================================
@app.route('/gallery')
def view_gallery():
    scenes = []
    if os.path.exists(OUTPUT_DATASET_DIR):
        scenes = [d for d in os.listdir(OUTPUT_DATASET_DIR) if os.path.isdir(os.path.join(OUTPUT_DATASET_DIR, d))]
    scenes.sort()
    return render_template('gallery.html', scenes=scenes)

@app.route('/gallery/<scene_name>')
def view_scene(scene_name):
    scene_path = os.path.join(OUTPUT_DATASET_DIR, scene_name)
    if not os.path.exists(scene_path):
        return "Scene not found", 404
        
    images = [f for f in os.listdir(scene_path) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    # Sort specifically to make light0 first, then light1..25
    def sort_key(s):
        # extract number
        try:
            num = int(''.join(filter(str.isdigit, s)))
            return num
        except:
            return 999
    images.sort(key=sort_key)
    
    images.sort(key=sort_key)
    
    # Load Metadata
    metadata = {}
    meta_path = os.path.join(OUTPUT_DATASET_DIR, "metadata.json")
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r') as f:
                metadata = json.load(f)
        except:
            pass

    return render_template('scene_detail.html', scene_name=scene_name, images=images, metadata=metadata)

# ==========================================
# FILE SERVING
# ==========================================
@app.route('/files/<path:filepath>')
def serve_file(filepath):
    # Security: prevents directory traversal attacks, though Flask's send_from_directory is relatively safe
    # We map 'buffer', 'input', 'output' prefixes to real dirs.
    if filepath.startswith("buffer/"):
        return send_from_directory(BUFFER_DIR, filepath.replace("buffer/", ""))
    elif filepath.startswith("output/"):
        # output/scene_name/image.png
        parts = filepath.split("/")
        if len(parts) >= 3 and parts[0] == "output":
             scene_dir = os.path.join(OUTPUT_DATASET_DIR, *parts[1:-1])
             filename = parts[-1]
             
             # Fallback for light0.jpg if strict request fails but png exists
             full_path = os.path.join(scene_dir, filename)
             if not os.path.exists(full_path):
                 # Try matching stem with other extensions?
                 stem, ext = os.path.splitext(filename)
                 if stem == "light0":
                     for try_ext in ['.png', '.jpg', '.jpeg', '.webp']:
                         if os.path.exists(os.path.join(scene_dir, stem + try_ext)):
                             return send_from_directory(scene_dir, stem + try_ext)
                             
             return send_from_directory(scene_dir, filename)
    return "File not found", 404

# ==========================================
# EXPORT
# ==========================================
@app.route('/export')
def view_export():
    return render_template('export.html')

@app.route('/api/backup', methods=['POST'])
def run_backup():
    # Check if credentials exist
    if not os.path.exists("credentials.json"):
        flash("Error: credentials.json not found. Please setup Google Drive API first.")
        return redirect(url_for('view_export'))
        
        return redirect(url_for('view_export'))
        
    subprocess.Popen(["python3", "uploader.py"])
    flash("Started Backup to Google Drive. Check terminal for authentication link if running for first time.")
    return redirect(url_for('view_export'))

@app.route('/api/download_zip', methods=['GET'])
def download_zip():
    try:
        # Create Zip (Synchronous to ensure it exists before sending)
        # Assuming dataset isn't massive, or this might timeout. 
        # For now, synchronous is safest for "download now".
        zip_path = uploader.create_zip_archive()
        return send_file(zip_path, as_attachment=True)
    except Exception as e:
        flash(f"Error creating zip: {e}")
        return redirect(url_for('view_export'))

@app.route('/api/import_drive', methods=['POST'])
def import_drive():
    link_or_id = request.form.get('drive_link')
    if not link_or_id:
        flash("Error: No link provided.")
        return redirect(url_for('view_export'))
        
    # Extract ID (simple heuristic)
    # If it contains "drive.google.com", try to extract ID
    file_id = link_or_id
    if "drive.google.com" in link_or_id:
        # Match /d/ID or id=ID
        # V1: split by /
        parts = link_or_id.split('/')
        for i, part in enumerate(parts):
            if part == 'd' and i + 1 < len(parts):
                file_id = parts[i+1]
                break
        # Handle ?id=...
        if 'id=' in link_or_id:
             import urllib.parse
             parsed = urllib.parse.urlparse(link_or_id)
             params = urllib.parse.parse_qs(parsed.query)
             if 'id' in params:
                 file_id = params['id'][0]

    # Download
    try:
        dest = "temp_restore.zip"
        uploader.download_file_from_google_drive(file_id, dest)
        if not os.path.exists(dest):
            flash("Download failed.")
            return redirect(url_for('view_export'))
            
        # Unzip
        uploader.unzip_dataset(dest)
        
        # Cleanup
        os.remove(dest)
        
        # Clear job queue so we rescan disk
        job_queue.clear_all_jobs()
        job_queue.scan_all_jobs()
        
        flash("Dataset restored successfully!")
    except Exception as e:
        flash(f"Restore failed: {e}")
        
    return redirect(url_for('view_export'))

if __name__ == '__main__':
    # Clear old task queue on startup as requested
    job_queue.clear_all_jobs()
    print("Cleared old task queue on startup.")
    
    app.run(debug=True, port=5000)
