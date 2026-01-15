import os
import json
import threading
import time

# Simple in-memory queue for V2
# Structure: { scene_name: { status: 'queued'|'processing'|'done', progress: 0, total: 25 } }
OUTPUT_DATASET_DIR = "output_dataset"
QUEUE_LOCK = threading.Lock()

# Persistence file
JOBS_FILE = "jobs.json"

def load_jobs():
    if os.path.exists(JOBS_FILE):
        try:
            with open(JOBS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def clear_all_jobs():
    with QUEUE_LOCK:
        if os.path.exists(JOBS_FILE):
             try:
                 os.remove(JOBS_FILE)
             except:
                 pass
        save_jobs({})

def save_jobs(jobs):
    try:
        with open(JOBS_FILE, 'w') as f:
            json.dump(jobs, f, indent=2)
    except:
        pass

# Structure: { 
#   scene_name: { 
#       status: 'queued'|'processing'|'done', 
#       progress: 0, 
#       total: 25,
#       tasks: [ { prompt: "...", status: "pending" } ]
#   } 
# }

def update_job(scene_name, status, progress=None):
    with QUEUE_LOCK:
        jobs = load_jobs()
        if scene_name not in jobs:
            jobs[scene_name] = {'total': 25, 'tasks': []}
        
        jobs[scene_name]['status'] = status
        if progress is not None:
             jobs[scene_name]['progress'] = progress
        
        save_jobs(jobs)

def set_job_tasks(scene_name, task_list):
    with QUEUE_LOCK:
        jobs = load_jobs()
        if scene_name not in jobs:
            jobs[scene_name] = {'total': len(task_list), 'status': 'queued', 'progress': 0}
        
        # task_list is list of strings (prompts)
        jobs[scene_name]['tasks'] = [{'prompt': p, 'status': 'pending'} for p in task_list]
        jobs[scene_name]['total'] = len(task_list)
        save_jobs(jobs)

def update_task_status(scene_name, task_index, status):
    with QUEUE_LOCK:
        jobs = load_jobs()
        if scene_name in jobs and 'tasks' in jobs[scene_name]:
            tasks = jobs[scene_name]['tasks']
            if 0 <= task_index < len(tasks):
                tasks[task_index]['status'] = status
                save_jobs(jobs)

def get_job_status(scene_name):
    jobs = load_jobs()
    if scene_name in jobs:
        return jobs[scene_name]
    
    # Fallback to disk scan (no detailed tasks)
    scene_dir = os.path.join(OUTPUT_DATASET_DIR, scene_name)
    if os.path.exists(scene_dir):
        files = [f for f in os.listdir(scene_dir) if f.startswith('light') and f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        count = max(0, len(files) - 1)
        status = 'done' if count >= 25 else 'idle'
        return {'status': status, 'progress': count, 'total': 25, 'tasks': []}
        
    return {'status': 'unknown', 'progress': 0, 'total': 25, 'tasks': []}

def scan_all_jobs():
    """Refreshes status for all folders in output_dataset"""
    # Return all jobs in memory (for granular queue view) plus any on disk not in memory
    jobs = load_jobs()
    
    if not os.path.exists(OUTPUT_DATASET_DIR):
        return jobs
        
    # Merge disk info if needed (optional, mostly relevant for fresh start)
    for scene_name in os.listdir(OUTPUT_DATASET_DIR):
        path = os.path.join(OUTPUT_DATASET_DIR, scene_name)
        if os.path.isdir(path):
             # Force sync with disk
             job = jobs.get(scene_name, {'status': 'idle', 'progress': 0, 'total': 25, 'tasks': []})
             
             # Count actually finished files
             files = [f for f in os.listdir(path) if f.startswith('light') and f.lower().endswith(('.jpg', '.png', '.jpeg'))]
             real_progress = max(0, len(files) - 1) # Subtract light0
             
             # If disk shows more progress, update memory
             if real_progress > job.get('progress', 0):
                 job['progress'] = real_progress
                 # If finished, mark as done
                 if real_progress >= 25:
                     job['status'] = 'done'
                 jobs[scene_name] = job
             elif scene_name not in jobs:
                 # Initialize if new
                 job['progress'] = real_progress
                 jobs[scene_name] = job
                 
    return jobs

def get_queue_overview():
    jobs = scan_all_jobs()
    total_pending = 0
    processing_tasks = []
    
    # Calculate pending
    for name, job in jobs.items():
        if 'tasks' in job:
            for t in job['tasks']:
                if t['status'] == 'pending':
                    total_pending += 1
                elif t['status'] == 'processing':
                    processing_tasks.append(f"{name}: {t['prompt'][:30]}...")
                    
    return {
        'pending_count': total_pending,
        'processing_tasks': processing_tasks  # List of strings
    }
