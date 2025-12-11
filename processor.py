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
from websocket import create_connection

# =================================================================================
# CONFIGURATION
# =================================================================================

COMFYUI_URL = "http://127.0.0.1:8188"
# INPUT_DIR = os.path.abspath("input_dataset") # Removed V2
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
# LIGHTING PROMPTS
# =================================================================================

LIGHTING_PROMPTS = [
    # Directional & Natural
    "soft morning sunlight streaming from the left window",
    "bright mid-day sunlight from directly above, hard shadows",
    "warm golden hour sunset light casting long horizontal shadows",
    "cool blue hour twilight entering from windows",
    "soft silvery moonlight filtering through curtains",
    "overcast day diffuse flat lighting, no strong shadows",
    "strong dramatic side lighting from the right",
    "volumetric god rays beaming from a skylight",
    "rim lighting emphasizing silhouettes against a dark background",
    "hard spotlight highlighting the center of the room",

    # Artificial & Temperature
    "warm tungsten interior lamp lighting, cozy atmosphere",
    "cool white fluorescent office ceiling lights, clinical feel",
    "dim candle light flickering on surfaces, warm glow",
    "cold blue LED strip lighting accents",
    "neutral studio softbox lighting, balanced and even",
    "fireplace glow emanating from the hearth",
    "flickering TV static blue light in a dark room",

    # Artistic & Stylized
    "cyberpunk neon pink and cyan mixed lighting",
    "film noir high contrast directional shadow, black and white aesthetic",
    "intense red emergency alarm rotating light style",
    "ethereal dreamy soft focus glow, angels breath",
    "underwater caustic lighting patterns, aqua blue",
    "disco ball multi-colored reflections on walls",
    "bioluminescent alien ambient glow, purple and green",
    "low angle horror style up-lighting from the floor"
]

# =================================================================================
# COMFYUI API CLIENT
# =================================================================================

class ComfyUIClient:
    def __init__(self, url):
        self.url = url
        self.server_address = url.replace('http://', '')
        self.ws = websocket.WebSocket()
        self.client_id = str(uuid.uuid4())
        self.ws_url = f"{url.replace('http', 'ws')}/ws?clientId={self.client_id}"

    def connect(self):
        try:
            self.ws.connect(self.ws_url)
            print("Connected to ComfyUI WebSocket")
        except Exception as e:
            print(f"Failed to connect to ComfyUI: {e}")
            sys.exit(1)

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
        return outputs

# =================================================================================
# MAIN LOGIC
# =================================================================================

def process_dataset(target_file="all"):
    # 1. Setup
    # INPUT_DIR check removed for V2
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # Save Metadata (Descriptions for each light index)
    metadata = {}
    metadata["light0"] = "Original Image"
    for i, prompt in enumerate(LIGHTING_PROMPTS):
        metadata[f"light{i+1}"] = prompt
    
    with open(os.path.join(OUTPUT_DIR, "metadata.json"), 'w') as f:
        json.dump(metadata, f, indent=2)
    print("Saved metadata.json to output_dataset/")

    # Load Workflow Template
    try:
        with open(WORKFLOW_FILE, 'r') as f:
            workflow_template = json.load(f)
    except FileNotFoundError:
        print(f"Error: {WORKFLOW_FILE} not found.")
        return

    # Check for albums in output_dataset
    if target_file != "all":
        # Process specific album (folder name)
        target_path = os.path.join(OUTPUT_DIR, target_file)
        if not os.path.exists(target_path):
             print(f"Error: Target album {target_file} not found in output_dataset.")
             return
        albums = [target_file] # The folder name
    else:
        # Scan all folders in OUTPUT_DIR that have a light0 image
        albums = []
        if os.path.exists(OUTPUT_DIR):
            for name in os.listdir(OUTPUT_DIR):
                path = os.path.join(OUTPUT_DIR, name)
                if os.path.isdir(path):
                     # Check if it has a light0 file (any extension)
                     has_light0 = any(f.startswith("light0.") for f in os.listdir(path))
                     if has_light0:
                         albums.append(name)
        
    if not albums:
        print("No albums found in output_dataset.")
        return

    print(f"Found {len(albums)} albums to process.")

    # V2: Pre-initialize ALL jobs in queue so they show up as "Pending" immediately
    # We do this BEFORE connecting to ComfyUI so the UI shows the queue even if backend is down.
    print("Initializing queue for all albums...")
    for album_name in albums:
        job_queue.set_job_tasks(album_name, LIGHTING_PROMPTS)
    
    # Initialize Client
    client = ComfyUIClient(COMFYUI_URL)
    client.connect()

    for idx, album_name in enumerate(albums):
        print(f"\n[{idx+1}/{len(albums)}] Processing Album: {album_name}")
        
        job_queue.update_job(album_name, 'processing', 0)
        
        scene_output_dir = os.path.join(OUTPUT_DIR, album_name)
        
        # Find the source image (light0)
        # We need the absolute path for ComfyUI
        light0_file = None
        for f in os.listdir(scene_output_dir):
             if f.startswith("light0."):
                 light0_file = f
                 break
        
        if not light0_file:
            print("  Skipping: No light0 file found inside.")
            continue
            
        image_path = os.path.join(scene_output_dir, light0_file)
        image_path_abs = os.path.abspath(image_path) # ComfyUI needs accurate path if not in input


        # Iterate Lighting Prompts
        for i, prompt_text in enumerate(LIGHTING_PROMPTS):
            light_idx = i + 1
            
            # V2 Logic: Check if image already exists (Upscaling/Resume support)
            # Check for both .png and .jpg just in case, though we output png
            expected_file = os.path.join(scene_output_dir, f"light{light_idx}.png")
            if os.path.exists(expected_file):
                print(f"  Skipping light{light_idx}: Already exists.")
                job_queue.update_task_status(album_name, i, 'done')
                job_queue.update_job(album_name, 'processing', light_idx)
                continue

            print(f"  Generating light{light_idx}: '{prompt_text[:40]}...'")

            # Clone workflow
            workflow = json.loads(json.dumps(workflow_template))

            # Modify Workflow
            # 1. Set Input Image (Must be absolute path or relative to ComfyUI input dir)
            # Since ComfyUI usually needs images in its input folder, strict automation often requires
            # uploading the image first OR pointing to an absolute path if enabled.
            # Here we assume the input_dataset is accessible or we rely on the user to copy images to ComfyUI input.
            # A common hack: Use absolute path if ComfyUI allows it (server arg --enable-cors-header * often needed)
            # OR better: The script copies the image to ComfyUI 'input' folder if needed.
            # For simplicity in this script, we assume Input Image Node supports the path we give it.
            # *IMPORTANT*: We pass the absolute path to the node.
            
            # 1. Set Input Image
            # We must provide the path. Since we are pointing to a file OUTSIDE regular comfy input, 
            # we rely on configured nodes supporting full paths or symlinks.
            # *CRITICAL CHANGE*: The new structure means images are in output_dataset/ALBUM/light0.jpg
            
            for node_id in NODE_IDS_LOAD_IMAGE:
                if node_id in workflow:
                    workflow[node_id]["inputs"]["image"] = image_path_abs
                    workflow[node_id]["inputs"]["upload"] = "image" # Force upload strategy if needed? Usually "image" input accepts path.
                else:
                    print(f"    Warning: Node ID {node_id} not found in workflow!")

            # 2. Set Prompt
            if NODE_ID_PROMPT_TEXT in workflow:
                current_text = workflow[NODE_ID_PROMPT_TEXT]["inputs"]["text"]
                workflow[NODE_ID_PROMPT_TEXT]["inputs"]["text"] = f"{current_text}, {prompt_text}"
            
            # 3. Set Random Seed
            if NODE_ID_RANDOM_NOISE in workflow:
                 workflow[NODE_ID_RANDOM_NOISE]["inputs"]["noise_seed"] = int(time.time() * 1000) % 10000000000000

            # 4. Apply Settings (Steps, CFG, Sampler)
            settings = load_settings()
            
            # Steps
            if NODE_ID_FLUX_SCHEDULER in workflow:
                # Default is 18
                steps = settings.get('steps', 18)
                workflow[NODE_ID_FLUX_SCHEDULER]["inputs"]["steps"] = int(steps)
                print(f"    Steps: {steps}")
            
            # Guidance
            if NODE_ID_FLUX_GUIDANCE in workflow:
                # Default is 4
                cfg = settings.get('cfg', 4)
                workflow[NODE_ID_FLUX_GUIDANCE]["inputs"]["guidance"] = float(cfg)
                print(f"    Guidance: {cfg}")
            
            # Sampler
            if NODE_ID_SAMPLER_SELECT in workflow:
                # Default is euler
                sampler = settings.get('sampler_name', 'euler')
                workflow[NODE_ID_SAMPLER_SELECT]["inputs"]["sampler_name"] = sampler
                print(f"    Sampler: {sampler}")


            # Update Task Status
            job_queue.update_task_status(album_name, i, 'processing')

            # Execute
            try:
                response = client.queue_prompt(workflow)
                prompt_id = response['prompt_id']
                
                # Wait for completion and get outputs
                outputs = client.wait_for_completion(prompt_id)
                
                # Save Output Image
                # Look for SaveImage node (ID 9) or whatever is saving
                # In standard API, we get 'executed' with output images
                saved = False
                for node_id in outputs:
                    node_output = outputs[node_id]
                    if 'images' in node_output:
                        img_info = node_output['images'][0]
                        filename = img_info['filename']
                        subfolder = img_info['subfolder']
                        folder_type = img_info['type']
                        
                        # Fetch image data
                        image_data = client.get_image(filename, subfolder, folder_type)
                        
                        # Save to destination
                        save_path = os.path.join(scene_output_dir, f"light{light_idx}.png")
                        with open(save_path, 'wb') as f:
                            f.write(image_data)
                        
                        print(f"    Saved -> light{light_idx}.png")
                        break
                
                # Update Task Done
                job_queue.update_task_status(album_name, i, 'done')
                
            except Exception as e:
                print(f"    Failed to generate variant {light_idx}: {e}")

            # Update Job Queue Progress
            job_queue.update_job(album_name, 'processing', light_idx)

    print("\nBatch processing complete.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="ComfyUI Relighting Processor")
    parser.add_argument("--target", type=str, help="Process a specific filename (e.g. image.jpg) or 'all'", default="all")
    args = parser.parse_args()
    
    process_dataset(target_file=args.target)
