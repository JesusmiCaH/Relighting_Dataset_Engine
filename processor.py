import json
import urllib.request
import urllib.parse
import urllib.error
import os
import shutil
import time
import job_queue
import websocket # pip install websocket-client
import uuid
import sys
import threading
import queue
import socket
import requests
import base64
from io import BytesIO
from PIL import Image
from websocket import create_connection

# =================================================================================
# CONFIGURATION
# =================================================================================

# We now scan for ports starting at 8188
BASE_COMFYUI_URL = "http://127.0.0.1"
START_PORT = 8188


OUTPUT_DIR = os.path.abspath("output_dataset")
WORKFLOW_FILE = "workflow_api.json"

# CRITICAL: UPDATE THESE IDS TO MATCH YOUR SPECIFIC WORKFLOW_API.JSON
# Open your workflow_api.json find the node class_types to identify the IDs.
NODE_IDS_LOAD_IMAGE = ["46"] # Array of LoadImage nodes (42 removed in V2)
NODE_ID_PROMPT_TEXT = "6"      # CLIP Text Encode
NODE_ID_RANDOM_NOISE = "25"    # RandomNoise
NODE_ID_FLUX_SCHEDULER = "48"  # Flux2Scheduler (Steps)
NODE_ID_FLUX_GUIDANCE = "26"   # FluxGuidance (CFG)
NODE_ID_SAMPLER_SELECT = "16"  # KSamplerSelect (Sampler)

SETTINGS_FILE = "settings.json"

def load_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f:
                return json.load(f)
        except:
             return {}
    return {}

# =================================================================================
# COMFYUI API CLIENT
# =================================================================================

class ComfyUIClient:
    def __init__(self, url):
        self.url = url
        self.server_address = url.replace('http://', '')
        self.ws = websocket.WebSocket()
        self.client_id = str(uuid.uuid4())
        # Fix: Ensure ws_url is correctly formed regardless of trailing slash
        base_ws = url.replace('http', 'ws').rstrip('/')
        self.ws_url = f"{base_ws}/ws?clientId={self.client_id}"

    def connect(self):
        try:
            self.ws.connect(self.ws_url)
            print(f"Connected to ComfyUI WebSocket at {self.url}")
        except Exception as e:
            print(f"Failed to connect to ComfyUI at {self.url}: {e}")
            # We don't exit here, just raise so the worker can handle it
            raise e

    def queue_prompt(self, prompt_workflow):
        p = {"prompt": prompt_workflow, "client_id": self.client_id}
        data = json.dumps(p).encode('utf-8')
        req = urllib.request.Request(f"{self.url}/prompt", data=data)
        try:
            return json.loads(urllib.request.urlopen(req).read())
        except urllib.error.HTTPError as e:
            print(f"HTTP Error: {e.code} - {e.reason}")
            print(e.read().decode('utf-8'))
            raise

    def get_history(self, prompt_id):
        with urllib.request.urlopen("http://{}/history/{}".format(self.server_address, prompt_id)) as response:
            return json.loads(response.read())

    def get_image(self, filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen("http://{}/view?{}".format(self.server_address, url_values)) as response:
            return response.read()

    def wait_for_completion(self, prompt_id):
        outputs = {}
        while True:
            try:
                out = self.ws.recv()
                if isinstance(out, str):
                    message = json.loads(out)
                    if message['type'] == 'executing':
                        data = message['data']
                        if data['node'] is None and data['prompt_id'] == prompt_id:
                            break # Done!
                    elif message['type'] == 'executed':
                        data = message['data']
                        if data['prompt_id'] == prompt_id:
                            node = data['node']
                            output = data['output']
                            outputs[node] = output
                else:
                    continue
            except Exception as e:
                print(f"WebSocket error on {self.url}: {e}")
                raise e
        return outputs

# =================================================================================
# FLUX API CLIENT
# =================================================================================

class FluxAPIClient:
    def __init__(self, api_key):
        self.api_key = api_key
        self.api_url = "https://api.bfl.ai/v1/flux-2-pro"
        
    def generate_image(self, image_path, prompt, output_path):
        # 1. Encode Image
        try:
            with Image.open(image_path) as img:
                # Convert to RGB to avoid issues with PNG alpha if needed, 
                # but API might handle it. Let's stick to simple first.
                buffered = BytesIO()
                img.save(buffered, format="JPEG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
        except Exception as e:
            print(f"Error preparing image {image_path}: {e}")
            raise e

        # 2. Submit Request
        try:
            response = requests.post(
                self.api_url,
                headers={
                    'accept': 'application/json',
                    'x-key': self.api_key,
                    'Content-Type': 'application/json',
                },
                json={
                    'prompt': prompt,
                    'input_image': img_str,
                },
            ).json()
        except Exception as e:
             print(f"API Request Failed: {e}")
             raise e

        if 'id' not in response:
            print(f"API Error Response: {response}")
            raise Exception(f"API Error: {response}")
            
        request_id = response["id"]
        polling_url = response["polling_url"]
        
        # 3. Poll for Completion
        while True:
            time.sleep(1) # Polling interval
            try:
                result = requests.get(
                    polling_url,
                    headers={
                        'accept': 'application/json',
                        'x-key': self.api_key,
                    },
                    params={'id': request_id}
                ).json()
                
                status = result.get('status')
                if status == 'Ready':
                    # Download result
                    sample_url = result['result']['sample']
                    img_data = requests.get(sample_url).content
                    with open(output_path, 'wb') as f:
                        f.write(img_data)
                    return True
                elif status in ['Error', 'Failed', 'Request Too Large']:
                    raise Exception(f"Generation failed: {result}")
                # Else: Pending or Processing, continue waiting
            except Exception as e:
                raise e

# =================================================================================
# DISCOVERY LOGIC
# =================================================================================



# =================================================================================
# MAIN LOGIC
# =================================================================================

LIGHTING_PROMPTS_FILE = "lighting_prompts.txt"
SYSTEM_PROMPT_FILE = "system_prompt.txt"

def load_text_file(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return [line.strip() for line in f if line.strip()]
    return []

def load_single_text_file(filepath):
    if os.path.exists(filepath):
        with open(filepath, 'r') as f:
            return f.read().strip()
    return ""

# Load Prompts
LIGHTING_PROMPTS = load_text_file(LIGHTING_PROMPTS_FILE)
# If empty, fallback (optional, or just leave empty)
if not LIGHTING_PROMPTS:
    # Minimal fallback or empty
    LIGHTING_PROMPTS = ["soft lighting"]
    
SYSTEM_PROMPT = load_single_text_file(SYSTEM_PROMPT_FILE)
# Fallback for system prompt
if not SYSTEM_PROMPT:
    SYSTEM_PROMPT = "High quality architectural photography, photorealistic, 8k."

def worker_thread(client_url, task_queue, workflow_template):
    """
    Worker function to process tasks from the queue using a specific ComfyUI client.
    """
    try:
        client = ComfyUIClient(client_url)
        client.connect()
    except Exception as e:
        print(f"Worker for {client_url} failed to connect: {e}")
        return

    print(f"Worker started for {client_url}")

    while True:
        try:
            # Get task from queue (non-blocking if possible, but we wait effectively)
            # We use a timeout to check for exit signals if needed, or just block
            task = task_queue.get(timeout=2) 
        except queue.Empty:
            # If queue is empty, we are done
            break

        album_name, light_idx, prompt_text = task
        
        # Construct expected file path
        scene_output_dir = os.path.join(OUTPUT_DIR, album_name)
        save_path = os.path.join(scene_output_dir, f"light{light_idx}.png")
        
        try:
            # 1. Double check existence (race condition redundant check but safe)
            if os.path.exists(save_path):
                 job_queue.update_task_status(album_name, light_idx - 1, 'done')
                 job_queue.update_job(album_name, 'processing', light_idx)
                 task_queue.task_done()
                 continue

            # 2. Get Input Image
            light0_file = None
            for f in os.listdir(scene_output_dir):
                 if f.startswith("light0."):
                     light0_file = f
                     break
            
            if not light0_file:
                print(f"  [Worker {client_url}] Skipping {album_name}: No light0 found.")
                task_queue.task_done()
                continue
                
            image_path_abs = os.path.abspath(os.path.join(scene_output_dir, light0_file))

            print(f"  [Worker {client_url}] Processing {album_name} - light{light_idx}")
            job_queue.update_task_status(album_name, light_idx - 1, 'processing')

            # 3. Clone & Modify Workflow
            workflow = json.loads(json.dumps(workflow_template))
            
            # Set Input Image
            for node_id in NODE_IDS_LOAD_IMAGE:
                if node_id in workflow:
                    workflow[node_id]["inputs"]["image"] = image_path_abs
                    workflow[node_id]["inputs"]["upload"] = "image"
            
            # Set Prompt
            if NODE_ID_PROMPT_TEXT in workflow:
                current_text = SYSTEM_PROMPT
                workflow[NODE_ID_PROMPT_TEXT]["inputs"]["text"] = f"{current_text} \n Relight the scene with: {prompt_text}"
            
            # Set Random Seed
            if NODE_ID_RANDOM_NOISE in workflow:
                 workflow[NODE_ID_RANDOM_NOISE]["inputs"]["noise_seed"] = int(time.time() * 1000) % 10000000000000
            
            # Settings
            settings = load_settings()
            if NODE_ID_FLUX_SCHEDULER in workflow:
                workflow[NODE_ID_FLUX_SCHEDULER]["inputs"]["steps"] = int(settings.get('steps', 18))
            if NODE_ID_FLUX_GUIDANCE in workflow:
                workflow[NODE_ID_FLUX_GUIDANCE]["inputs"]["guidance"] = float(settings.get('cfg', 4))
            if NODE_ID_SAMPLER_SELECT in workflow:
                workflow[NODE_ID_SAMPLER_SELECT]["inputs"]["sampler_name"] = settings.get('sampler_name', 'euler')

            # 4. Execute
            response = client.queue_prompt(workflow)
            prompt_id = response['prompt_id']
            outputs = client.wait_for_completion(prompt_id)
            
            # Save Output
            for node_id in outputs:
                node_output = outputs[node_id]
                if 'images' in node_output:
                    img_info = node_output['images'][0]
                    # Fetch and save
                    image_data = client.get_image(img_info['filename'], img_info['subfolder'], img_info['type'])
                    with open(save_path, 'wb') as f:
                        f.write(image_data)
                    print(f"  [Worker {client_url}] Finished {album_name} - light{light_idx}")
                    break
            
            job_queue.update_task_status(album_name, light_idx - 1, 'done')
            job_queue.update_job(album_name, 'processing', light_idx) # Rough progress update

        except Exception as e:
            print(f"  [Worker {client_url}] Error on {album_name} light{light_idx}: {e}")
            # Optional: Mark as error in queue? For now just log.
        
        finally:
            task_queue.task_done()

def api_worker_thread(task_queue, api_key):
    """
    Worker for Flux API requests
    """
    client = FluxAPIClient(api_key)
    
    while True:
        try:
            task = task_queue.get(timeout=2)
        except queue.Empty:
            break
            
        album_name, light_idx, prompt_text = task
        scene_output_dir = os.path.join(OUTPUT_DIR, album_name)
        save_path = os.path.join(scene_output_dir, f"light{light_idx}.png")
        
        try:
            # Check existence
            if os.path.exists(save_path):
                 job_queue.update_task_status(album_name, light_idx - 1, 'done')
                 job_queue.update_job(album_name, 'processing', light_idx)
                 task_queue.task_done()
                 continue
            
            # Find Input
            light0_file = None
            for f in os.listdir(scene_output_dir):
                 if f.startswith("light0."):
                     light0_file = f
                     break
            
            if not light0_file:
                print(f"  [API Worker] Skipping {album_name}: No light0 found.")
                task_queue.task_done()
                continue
                
            image_path_abs = os.path.join(scene_output_dir, light0_file)
            
            # Construct Prompt
            full_prompt = f"{SYSTEM_PROMPT} \n Relight the scene with: {prompt_text}"
            
            print(f"  [API Worker] Processing {album_name} - light{light_idx}")
            job_queue.update_task_status(album_name, light_idx - 1, 'processing')
            
            # Generate
            client.generate_image(image_path_abs, full_prompt, save_path)
            
            print(f"  [API Worker] Finished {album_name} - light{light_idx}")
            job_queue.update_task_status(album_name, light_idx - 1, 'done')
            job_queue.update_job(album_name, 'processing', light_idx)

        except Exception as e:
            print(f"  [API Worker] Error on {album_name} light{light_idx}: {e}")
            job_queue.update_task_status(album_name, light_idx - 1, 'error')
        
        finally:
            task_queue.task_done()

def process_dataset(target_file="all"):
    # 1. Setup
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # Save Metadata
    metadata = {}
    metadata["light0"] = "Original Image"
    for i, prompt in enumerate(LIGHTING_PROMPTS):
        metadata[f"light{i+1}"] = prompt
    
    with open(os.path.join(OUTPUT_DIR, "metadata.json"), 'w') as f:
        json.dump(metadata, f, indent=2)

    # Load Workflow Template
    try:
        with open(WORKFLOW_FILE, 'r') as f:
            workflow_template = json.load(f)
    except FileNotFoundError:
        print(f"Error: {WORKFLOW_FILE} not found.")
        return

    # Check for albums
    if target_file != "all":
        target_path = os.path.join(OUTPUT_DIR, target_file)
        if not os.path.exists(target_path):
             print(f"Error: Target album {target_file} not found.")
             return
        albums = [target_file]
    else:
        albums = []
        if os.path.exists(OUTPUT_DIR):
            for name in os.listdir(OUTPUT_DIR):
                path = os.path.join(OUTPUT_DIR, name)
                if os.path.isdir(path):
                     has_light0 = any(f.startswith("light0.") for f in os.listdir(path))
                     if has_light0:
                         albums.append(name)
        
    if not albums:
        print("No albums found in output_dataset.")
        return

    print(f"Found {len(albums)} albums to process.")

    # Initialize Queue in UI (V2)
    print("Initializing status queue...")
    for album_name in albums:
        job_queue.set_job_tasks(album_name, LIGHTING_PROMPTS)

    # -------------------------------------------------------------------------
    # PROCESSING SETUP
    # -------------------------------------------------------------------------
    
    settings = load_settings()
    mode = settings.get('generation_mode', 'local') # 'local' or 'api'
    
    if mode == 'api':
        api_key = os.environ.get("BFL_API_KEY")
        if not api_key:
            print("FATAL: Generation Mode is API but BFL_API_KEY is not set.")
            return

        max_workers = int(settings.get('api_max_parallel', 20))
        print(f"Starting API Processing with {max_workers} parallel workers...")
        
    else:
        # Local Mode
        # 1. Setup Client
        active_urls = [f"{BASE_COMFYUI_URL}:{START_PORT}"]
        print(f"Using ComfyUI instance at: {active_urls[0]}")

    # 2. Build Task Queue
    # We want to flatten the work: (Album, PromptIndex, PromptText)
    # This allows multiple workers to work on the SAME album in parallel if needed,
    # or different albums.
    # Note: Working on same album is fine as long as they write differnet files (light1, light2...)
    
    processing_queue = queue.Queue()
    
    total_tasks = 0
    for album_name in albums:
        scene_output_dir = os.path.join(OUTPUT_DIR, album_name)
        
        # Pre-check for completion to avoid filling queue with done tasks
        for i, prompt_text in enumerate(LIGHTING_PROMPTS):
            light_idx = i + 1
            expected_file = os.path.join(scene_output_dir, f"light{light_idx}.png")
            
            if os.path.exists(expected_file):
                # Ensure UI is updated
                job_queue.update_task_status(album_name, i, 'done')
                continue
            
            # Add to queue
            # Item: (album_name, light_idx, prompt_text)
            processing_queue.put((album_name, light_idx, prompt_text))
            total_tasks += 1
            
    print(f"Queued {total_tasks} generation tasks.")
    
    if total_tasks == 0:
        print("All tasks completed.")
        return

    # 3. Start Workers
    threads = []
    
    if mode == 'api':
        for _ in range(max_workers):
            t = threading.Thread(target=api_worker_thread, args=(processing_queue, api_key))
            t.start()
            threads.append(t)
    else:
        # Local workers
        for url in active_urls:
            t = threading.Thread(target=worker_thread, args=(url, processing_queue, workflow_template))
            t.start()
            threads.append(t)
        
    # 4. Wait
    for t in threads:
        t.join()

    print("\nBatch processing complete.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ComfyUI Relighting Processor")
    parser.add_argument("--target", type=str, help="Process a specific filename (e.g. image.jpg) or 'all'", default="all")
    args = parser.parse_args()
    
    process_dataset(target_file=args.target)
