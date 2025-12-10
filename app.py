import os
import shutil
import threading
import subprocess
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Config
BUFFER_DIR = os.path.abspath("buffer")
INPUT_DATASET_DIR = os.path.abspath("input_dataset")
OUTPUT_DATASET_DIR = os.path.abspath("output_dataset")

# Ensure dirs exist
for d in [BUFFER_DIR, INPUT_DATASET_DIR, OUTPUT_DATASET_DIR]:
    if not os.path.exists(d):
        os.makedirs(d)

@app.route('/')
def index():
    return redirect(url_for('view_buffer'))

# ==========================================
# BUFFER
# ==========================================
@app.route('/buffer')
def view_buffer():
    images = []
    if os.path.exists(BUFFER_DIR):
        images = [f for f in os.listdir(BUFFER_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    images.sort()
    return render_template('buffer.html', images=images)

@app.route('/buffer/action', methods=['POST'])
def buffer_action():
    filename = request.form.get('filename')
    action = request.form.get('action')
    
    src = os.path.join(BUFFER_DIR, filename)
    
    if action == 'approve':
        dst = os.path.join(INPUT_DATASET_DIR, filename)
        shutil.move(src, dst)
        flash(f"Approved {filename}")
    elif action == 'delete':
        os.remove(src)
        flash(f"Deleted {filename}")
        
    return redirect(url_for('view_buffer'))

@app.route('/api/scrape', methods=['POST'])
def run_scraper():
    count = request.form.get('count', 5)
    # Run script in background
    subprocess.Popen(["python3", "scraper.py", "--count", str(count)])
    flash(f"Started scraping {count} images...")
    return redirect(url_for('view_buffer'))

# ==========================================
# DATASET (QUEUE)
# ==========================================
@app.route('/dataset')
def view_dataset():
    images = []
    if os.path.exists(INPUT_DATASET_DIR):
        images = [f for f in os.listdir(INPUT_DATASET_DIR) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    images.sort()
    return render_template('dataset.html', images=images)

@app.route('/api/process', methods=['POST'])
def run_processor():
    # Run processor in background
    subprocess.Popen(["python3", "processor.py"])
    flash("Started ComfyUI Processor...")
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
    
    return render_template('scene_detail.html', scene_name=scene_name, images=images)

# ==========================================
# FILE SERVING
# ==========================================
@app.route('/files/<path:filepath>')
def serve_file(filepath):
    # Security: prevents directory traversal attacks, though Flask's send_from_directory is relatively safe
    # We map 'buffer', 'input', 'output' prefixes to real dirs.
    if filepath.startswith("buffer/"):
        return send_from_directory(BUFFER_DIR, filepath.replace("buffer/", ""))
    elif filepath.startswith("input/"):
        return send_from_directory(INPUT_DATASET_DIR, filepath.replace("input/", ""))
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
