import json
import urllib.request
import urllib.parse
import os
import shutil
import time
import websocket # pip install websocket-client
import uuid
import sys

# =================================================================================
# CONFIGURATION
# =================================================================================

COMFYUI_URL = "http://127.0.0.1:8188"
INPUT_DIR = os.path.abspath("input_dataset")
OUTPUT_DIR = os.path.abspath("output_dataset")
WORKFLOW_FILE = "workflow_api.json"

# CRITICAL: UPDATE THESE IDS TO MATCH YOUR SPECIFIC WORKFLOW_API.JSON
# Open your workflow_api.json find the node class_types to identify the IDs.
NODE_ID_LOAD_IMAGE = "10"  # The LoadImage node
NODE_ID_PROMPT_TEXT = "6"  # The CLIPTextEncode node (Positive Prompt)
NODE_ID_KSAMPLER = "3"     # The KSampler node (Optional, if you want to set seed)

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
        return json.loads(urllib.request.urlopen(req).read())

    def get_history(self, prompt_id):
        with urllib.request.urlopen(f"{self.url}/history/{prompt_id}") as response:
            return json.loads(response.read())

    def get_image(self, filename, subfolder, folder_type):
        data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
        url_values = urllib.parse.urlencode(data)
        with urllib.request.urlopen(f"{self.url}/view?{url_values}") as response:
            return response.read()

    def wait_for_completion(self, prompt_id):
        while True:
            out = self.ws.recv()
            if isinstance(out, str):
                message = json.loads(out)
                if message['type'] == 'executing':
                    data = message['data']
                    if data['node'] is None and data['prompt_id'] == prompt_id:
                        return True # Execution done
            else:
                continue
        return False

# =================================================================================
# MAIN LOGIC
# =================================================================================

def process_dataset():
    # 1. Setup
    if not os.path.exists(INPUT_DIR):
        print(f"Error: {INPUT_DIR} does not exist.")
        return

    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    # Load Workflow Template
    try:
        with open(WORKFLOW_FILE, 'r') as f:
            workflow_template = json.load(f)
    except FileNotFoundError:
        print(f"Error: {WORKFLOW_FILE} not found.")
        return

    # Check for images
    images = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
    if not images:
        print("No images found in input_dataset.")
        return

    print(f"Found {len(images)} images to process.")
    
    # Initialize Client
    client = ComfyUIClient(COMFYUI_URL)
    client.connect()

    for idx, image_file in enumerate(images):
        print(f"\n[{idx+1}/{len(images)}] Processing: {image_file}")
        
        image_stem = os.path.splitext(image_file)[0]
        scene_output_dir = os.path.join(OUTPUT_DIR, image_stem)
        
        if not os.path.exists(scene_output_dir):
            os.makedirs(scene_output_dir)

        # Copy original as light0
        shutil.copy(os.path.join(INPUT_DIR, image_file), os.path.join(scene_output_dir, "light0.jpg"))
        print(f"  Saved original -> light0.jpg")

        # Iterate Lighting Prompts
        for i, prompt_text in enumerate(LIGHTING_PROMPTS):
            light_idx = i + 1
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
            
            if NODE_ID_LOAD_IMAGE in workflow:
                workflow[NODE_ID_LOAD_IMAGE]["inputs"]["image"] = os.path.join(INPUT_DIR, image_file)
            else:
                print(f"    Error: Node ID {NODE_ID_LOAD_IMAGE} not found!")
                continue

            # 2. Set Prompt
            if NODE_ID_PROMPT_TEXT in workflow:
                current_text = workflow[NODE_ID_PROMPT_TEXT]["inputs"]["text"]
                workflow[NODE_ID_PROMPT_TEXT]["inputs"]["text"] = f"{current_text}, {prompt_text}"
            
            # 3. Set Random Seed (to ensure new noise generation each time if desired, or keep fixed for consistency)
            if NODE_ID_KSAMPLER in workflow:
                 workflow[NODE_ID_KSAMPLER]["inputs"]["seed"] = int(time.time() * 1000) % 1000000000

            # Execute
            try:
                response = client.queue_prompt(workflow)
                prompt_id = response['prompt_id']
                
                # Wait for finish
                client.wait_for_completion(prompt_id)
                
                # Get Result
                # We need to find the output. Easier method: Read history to find output filename.
                history = client.get_history(prompt_id)[prompt_id]
                outputs = history['outputs']
                
                # Assume the first output node has our image
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
            except Exception as e:
                print(f"    Failed to generate variant {light_idx}: {e}")

    print("\nBatch processing complete.")

if __name__ == "__main__":
    process_dataset()
