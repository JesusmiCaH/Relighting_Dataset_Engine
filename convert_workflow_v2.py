import json

INPUT_FILE = "Flux2_relight.json"
OUTPUT_FILE = "workflow_api.json"

def convert():
    try:
        with open(INPUT_FILE, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: {INPUT_FILE} not found.")
        return

    api_workflow = {}
    
    # ComfyUI API format: { "node_id": { "inputs": {...}, "class_type": "..." } }
    # Source format is UI: { "nodes": [ ... ], "links": [ ... ] }
    
    # We iterate over nodes and extract inputs.
    # Links need to be resolved: input value becomes [node_id, slot_index]
    
    # 1. Map Link ID -> Source Node
    link_map = {} # link_id -> [source_node_id, source_slot_index]
    if "links" in data:
        for link in data["links"]:
            # Link format: [id, source_node_id, source_slot_index, target_node_id, target_slot_index, type]
            link_id = link[0]
            source_node_id = str(link[1])
            source_slot_index = link[2]
            link_map[link_id] = [source_node_id, source_slot_index]
            
    # 2. Process Nodes
    for node in data["nodes"]:
        node_id = str(node["id"])
        
        # Skip UI-only nodes
        if node["type"] in ["Note", "MarkdownNote", "PrimitiveNode", "Reroute"]:
            continue
            
        api_node = {
            "inputs": {},
            "class_type": node["type"],
            "_meta": {
                "title": node.get("title", node["type"])
            }
        }
        
        # Process Widget Values (convert to inputs)
        # ComfyUI nodes have 'widgets_values' list which maps to widget inputs in order.
        # This is tricky because the API expects named keys, but UI stores them as a list.
        # However, usually the 'inputs' dictionary in the UI node object contains the links.
        # But for scalar values (int, string), they are often in 'widgets_values'.
        
        # Heuristic for this specific workflow:
        # We can try to rely on `processor.py` to override what matters, 
        # but to have a valid base workflow, we need the values.
        # LUCKILY: The UI node inputs list usually contains the name.
        # BUT: In recent ComfyUI, `widgets_values` are separate.
        
        # Let's simple-copy the logic from my previous manual conversion experience or use the "save_api" export.
        # Since I cannot use "Save (API)" button, I have to approximate.
        # CRITICAL: For known nodes, I can map manually. For unknown, I might guess.
        
        # Better approach:
        # Use the fact that `inputs` in UI node has `widget` field if it's connected to a widget.
        # `widgets_values` are in order of widgets.
        
        # Let's map widget definition to value
        widget_iter = iter(node.get("widgets_values", []))
        
        # Inputs from Links
        if "inputs" in node:
            for inp in node["inputs"]:
                name = inp["name"]
                link_id = inp["link"]
                
                if link_id is not None:
                     # It's a link
                     if link_id in link_map:
                         api_node["inputs"][name] = link_map[link_id]
                else:
                    # It might be a widget value?
                    # If 'widget' key exists, it consumes a value from widgets_values
                    if "widget" in inp:
                        try:
                            val = next(widget_iter)
                            api_node["inputs"][name] = val
                        except StopIteration:
                            pass
        
        # Some widgets are not in 'inputs' list (like Free-standing widgets e.g. Seed on RandomNoise?)
        # Actually in Flux2_relight info:
        # RandomNoise inputs: [ {name: noise_seed, widget: {name: noise_seed}} ] -> Link null.
        # So it consumes a widget value.
        
        # Check specific nodes to ensure correctness
        # Node 48 Flux2Scheduler: widgets_values [18, 1248, 832]. inputs: steps, width, height. Matches.
        # Node 6 CLIPTextEncode: widgets_values ["High quality..."]. inputs: text. Matches.
        
        # Add leftover widgets? Some nodes like 'LoadImage' have 'image' and 'upload' widgets.
        # LoadImage (46): inputs [image, upload]. widgets_values ["b914...", "image"].
        # So inputs['image'] = "b914...", inputs['upload'] = "image".
        
        # One tricky case: UNETLoader. inputs: unet_name, weight_dtype. widgets_values ["flux2...", "default"].
        # Matches.
        
        api_workflow[node_id] = api_node
        
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(api_workflow, f, indent=2)
    print(f"Converted {len(api_workflow)} nodes to {OUTPUT_FILE}")

if __name__ == "__main__":
    convert()
