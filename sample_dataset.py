import os
import shutil
import random
import argparse
from PIL import Image

def sample_images(source_dir, buffer_dir, n, min_size):
    if not os.path.exists(source_dir):
        print(f"Error: Source directory '{source_dir}' does not exist.")
        return

    if not os.path.exists(buffer_dir):
        os.makedirs(buffer_dir)
        print(f"Created buffer directory: {buffer_dir}")

    # Iterate over classes (subdirectories in source_dir)
    classes = [d for d in os.listdir(source_dir) if os.path.isdir(os.path.join(source_dir, d))]
    classes.sort()

    print(f"Found {len(classes)} classes in {source_dir}")

    total_sampled = 0

    for class_name in classes:
        class_path = os.path.join(source_dir, class_name)
        images = [f for f in os.listdir(class_path) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
        
        # Shuffle to random sample
        random.shuffle(images)
        
        sampled_count = 0
        
        for img_name in images:
            if sampled_count >= n:
                break
                
            img_path = os.path.join(class_path, img_name)
            
            try:
                with Image.open(img_path) as img:
                    width, height = img.size
                    
                if width < min_size or height < min_size:
                    # Skip if too small
                    continue
                    
                # Valid image, process it
                ext = os.path.splitext(img_name)[1]
                # Naming convention: {class name}_{idx}
                # idx is 1-based index (1 to N)
                new_name = f"{class_name}_{sampled_count + 1}{ext}"
                dest_path = os.path.join(buffer_dir, new_name)
                
                shutil.copy2(img_path, dest_path)
                print(f"Sampled: {new_name} (from {img_name})")
                
                sampled_count += 1
                total_sampled += 1
                
            except Exception as e:
                print(f"Error processing {img_path}: {e}")
                
    print(f"\nDone! Total images sampled: {total_sampled}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sample images from dataset to buffer.")
    parser.add_argument("--source", type=str, default="/root/workspace/indoorCVPR_09/Images", help="Path to source dataset.")
    parser.add_argument("--buffer", type=str, default="buffer", help="Path to buffer directory.")
    parser.add_argument("--n", type=int, default=1, help="Number of images to sample per class.")
    parser.add_argument("--min_size", type=int, default=300, help="Minimum width/height for images.")
    
    args = parser.parse_args()
    
    # Resolve absolute paths
    source = os.path.abspath(args.source)
    buffer = os.path.abspath(args.buffer)
    
    print(f"Source: {source}")
    print(f"Buffer: {buffer}")
    print(f"N per class: {args.n}")
    print(f"Min Size: {args.min_size}")
    
    sample_images(source, buffer, args.n, args.min_size)
