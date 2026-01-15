import uuid
import os
import random
from icrawler.builtin import BingImageCrawler


# List of "Lucky" indoor scene keywords
LUCKY_KEYWORDS = [
    "modern minimalist living room",
    "abandoned warehouse interior",
    "baroque style library",
    "cozy wooden cabin interior",
    "futuristic sci-fi corridor",
    "industrial loft apartment",
    "luxury hotel lobby",
    "messy artist studio",
    "japanese zen bedroom",
    "gothic cathedral interior"
]

def get_lucky_prompt():
    return random.choice(LUCKY_KEYWORDS)

def google_crawl(keyword, max_num=10, buffer_dir="buffer_temp"):
    """
    Crawls Google Images for the keyword.
    Downloads them to a temporary buffer directory.
    Returns a list of downloaded filenames.
    """
    if not os.path.exists(buffer_dir):
        os.makedirs(buffer_dir)
        
    # Use a subdirectory for the keyword to keep things organized or flatten?
    # For "Virtual Buffer", we might want to just dump them in a temp folder 
    # and return the paths so the UI can verify them.
    
    # Clean previous temp buffer if needed? 
    # For now, let's append.
    
    # Clear buffer first if desired? Or just overwrite.
    # We rely on UUID filenames so likely no overwrite unless same.
    
    # Use Bing instead of Google as it's often more stable
    # google_crawler = GoogleImageCrawler(storage={'root_dir': buffer_dir})
    # google_crawler.crawl(keyword=keyword, max_num=max_num)
    
    bing_crawler = BingImageCrawler(storage={'root_dir': buffer_dir})
    bing_crawler.crawl(keyword=keyword, max_num=max_num)
    
    # Rename files to include keyword
    # Pattern: keyword_idx.ext (e.g., apple_1.jpg)
    downloaded_files = []
    
    # Keyword safe format
    safe_keyword = keyword.replace(' ', '_')
    prefix = safe_keyword + "_"

    # Determined start index for this keyword
    start_idx = 1
    if os.path.exists(buffer_dir):
        # Scan existing files to find max index for this keyword
        for f in os.listdir(buffer_dir):
            if f.startswith(prefix):
                try:
                    # Parse index from "keyword_idx.ext"
                    # strictly check if remainder is int to avoid collisions
                    # e.g. "living_room_1" (keyword "living") -> remainder "room_1" -> fail
                    # e.g. "living_room_1" (keyword "living_room") -> remainder "1" -> pass
                    
                    stem = os.path.splitext(f)[0]
                    remainder = stem[len(prefix):]
                    
                    # Ensure remainder is just digits
                    if remainder.isdigit():
                        idx = int(remainder)
                        if idx >= start_idx:
                            start_idx = idx + 1
                except:
                    pass

        # Rename new files
        for f in os.listdir(buffer_dir):
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
                # Check if it looks like we already renamed it in this batch or previous
                # We need to be careful not to rename "apple_1.jpg" to "apple_1_1.jpg"
                # Check if it matches our pattern for this logical keyword
                already_named = False
                if f.startswith(prefix):
                     stem = os.path.splitext(f)[0]
                     if stem[len(prefix):].isdigit():
                         already_named = True
                
                if not already_named:
                    ext = os.path.splitext(f)[1]
                    new_name = f"{safe_keyword}_{start_idx}{ext}"
                    try:
                        os.rename(os.path.join(buffer_dir, f), os.path.join(buffer_dir, new_name))
                        downloaded_files.append(new_name)
                        start_idx += 1
                    except Exception as e:
                        print(f"Error renaming {f}: {e}")
                else:
                    downloaded_files.append(f)
                    
    return downloaded_files
