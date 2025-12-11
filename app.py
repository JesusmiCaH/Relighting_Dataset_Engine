import os
import json
import shutil
import threading
import subprocess
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash
import scrawler
import job_queue
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
            scene_dir = os.path.join(OUTPUT_DATASET_DIR, stem)
            if not os.path.exists(scene_dir):
                os.makedirs(scene_dir)
                
            dst = os.path.join(scene_dir, "light0" + os.path.splitext(filename)[1]) # Keep extension or force jpg?
            # actually processor expects light0.jpg, let's rename/convert if needed or just copy
            # flexible approach: copy as is, processor will read it
            shutil.move(src, dst)
            
            # Rename to standard light0.jpg if we want strictness?
            # Let's simple move for now.
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
    for f in os.listdir(BUFFER_DIR):
        try:
            os.remove(os.path.join(BUFFER_DIR, f))
        except:
            pass
        
    # Run Crawl
    # We download 10 images
    count = scrawler.google_crawl(keyword, max_num=10, buffer_dir=BUFFER_DIR)
    flash(f"Found {len(count)} images for '{keyword}'")
    
    return redirect(url_for('view_search'))

@app.route('/api/queue')
def get_queue_status():
    return job_queue.scan_all_jobs()

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
    return render_template('settings.html', settings=settings)

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
    
    save_settings_to_disk(settings)
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
             real_path = os.path.join(OUTPUT_DATASET_DIR, *parts[1:-1])
             return send_from_directory(real_path, parts[-1])
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
        
    subprocess.Popen(["python3", "uploader.py"])
    flash("Started Backup to Google Drive. Check terminal for authentication link if running for first time.")
    return redirect(url_for('view_export'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
