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
    
    # Return list of downloaded files
    downloaded_files = []
    if os.path.exists(buffer_dir):
        downloaded_files = [os.path.join(buffer_dir, f) for f in os.listdir(buffer_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    return downloaded_files
