import os
import requests

# Option 1: Use image URLs directly (simplest)
# response = requests.post(
#     'https://api.bfl.ai/v1/flux-2-pro',
#     headers={
#         'accept': 'application/json',
#         'x-key': os.environ.get("BFL_API_KEY"),
#         'Content-Type': 'application/json',
#     },
#     json={
#         'prompt': '<What you want to edit on the image>',
#         'input_image': 'https://example.com/your-image.jpg',
#         # 'input_image_2': 'https://example.com/reference-2.jpg',  # Optional
#     },
# ).json()

# request_id = response["id"]
# polling_url = response["polling_url"]
# cost = response.get("cost")  # Cost in credits

# Option 2: Use base64 encoded images (for local files)
import base64
from PIL import Image
from io import BytesIO

image = Image.open("output_dataset/florist_01/light0.jpg")
buffered = BytesIO()
image.save(buffered, format="JPEG")
img_str = base64.b64encode(buffered.getvalue()).decode()

response = requests.post(
    'https://api.bfl.ai/v1/flux-2-pro',
    headers={
        'accept': 'application/json',
        'x-key': os.environ.get("BFL_API_KEY"),
        'Content-Type': 'application/json',
    },
    json={
        'prompt': 'High quality architectural photography, realistic textures, photorealistic, 8k, highly detailed, physically based rendering. (Masterpiece), accurate lighting physics, raytracing. \nUse the reference image only as the scene structure and material guide. Reproduce the same indoor environment with identical layout, geometry, objects, and textures. \nRelight the scene with: harsh frontal flash lighting intense direct point source casting sharp hard shadows dark background falloff',
        'input_image': img_str,
    },
).json()

print(response)
request_id = response["id"]
polling_url = response["polling_url"]
cost = response.get("cost")  # Cost in credits



import time
import os
import requests

while True:
  time.sleep(0.5)
  result = requests.get(
      polling_url,
      headers={
          'accept': 'application/json',
          'x-key': os.environ.get("BFL_API_KEY"),
      },
      params={'id': request_id}
  ).json()
  
  if result['status'] == 'Ready':
      print(f"Image ready: {result['result']['sample']}")
      break
  elif result['status'] in ['Error', 'Failed']:
      print(f"Generation failed: {result}")
      break