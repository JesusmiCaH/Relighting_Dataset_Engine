import os
import requests
import time
import argparse

# Configuration
BUFFER_DIR = "buffer"
IMAGE_COUNT = 10
# Using loremflickr as a reliable source for random indoor images without API keys
# In a production environment, you would use Unsplash API or similar.
SOURCE_URL = "https://loremflickr.com/1024/1024/interior,room"

def download_images(count):
    if not os.path.exists(BUFFER_DIR):
        os.makedirs(BUFFER_DIR)
        print(f"Created {BUFFER_DIR}/")

    print(f"Starting download of {count} images to {BUFFER_DIR}...")
    
    for i in range(count):
        try:
            # Generate a unique timestamp for the filename
            timestamp = int(time.time() * 1000)
            filename = f"interior_{timestamp}_{i}.jpg"
            filepath = os.path.join(BUFFER_DIR, filename)
            
            # Fetch image
            # We add a random parameter to bypass caching if the service caches by URL
            response = requests.get(SOURCE_URL + f"?random={timestamp}", timeout=10)
            
            if response.status_code == 200:
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                print(f"[{i+1}/{count}] Downloaded {filename}")
            else:
                print(f"[{i+1}/{count}] Failed to fetch image (Status {response.status_code})")
            
            # Be nice to the server
            time.sleep(1)
            
        except Exception as e:
            print(f"Error downloading image {i}: {e}")

    print("Download complete.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indoor Scene Scraper")
    parser.add_argument("--count", type=int, default=5, help="Number of images to download")
    args = parser.parse_args()
    
    download_images(args.count)
