import os
import shutil
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import requests
from googleapiclient.http import MediaFileUpload

# Config
SCOPES = ['https://www.googleapis.com/auth/drive.file']
OUTPUT_DIR = "output_dataset"
ZIP_NAME = "dataset_backup"
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'credentials.json'

def create_zip_archive():
    print("Compressing dataset...")
    # Creates dataset_backup.zip in current directory
    archive_path = shutil.make_archive(ZIP_NAME, 'zip', OUTPUT_DIR)
    print(f"Created {archive_path}")
    return archive_path

def authenticate_drive():
    creds = None
    # The file token.json stores the user's access and refresh tokens.
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(f"Missing {CREDENTIALS_FILE}. Please download it from Google Cloud Console.")
            
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save the credentials for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)

def upload_file(service, filename):
    print(f"Uploading {filename} to Google Drive...")
    file_metadata = {
        'name': f"Dataset_Backup_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.zip",
        'mimeType': 'application/zip'
    }
    media = MediaFileUpload(filename, mimetype='application/zip', resumable=True)
    
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"File ID: {file.get('id')} uploaded successfully.")
    return file.get('id')

def main():
    if not os.path.exists(OUTPUT_DIR) or not os.listdir(OUTPUT_DIR):
        print("No output dataset to backup.")
        return

    try:
        zip_file = create_zip_archive()
        service = authenticate_drive()
        upload_file(service, zip_file)
        
        # Cleanup
        if os.path.exists(zip_file):
            os.remove(zip_file)
            
    except Exception as e:
        print(f"Backup failed: {e}")


def download_file_from_google_drive(file_id, destination):
    URL = "https://docs.google.com/uc?export=download"
    session = requests.Session()

    print(f"Downloading file with ID: {file_id} to {destination}")
    response = session.get(URL, params={'id': file_id}, stream=True)
    token = get_confirm_token(response)

    if token:
        params = {'id': file_id, 'confirm': token}
        response = session.get(URL, params=params, stream=True)

    save_response_content(response, destination)
    return destination

def get_confirm_token(response):
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            return value
    return None

def save_response_content(response, destination):
    CHUNK_SIZE = 32768
    with open(destination, "wb") as f:
        for chunk in response.iter_content(CHUNK_SIZE):
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)

def unzip_dataset(zip_path):
    print(f"Unzipping {zip_path} to {OUTPUT_DIR}...")
    # Ensure output dir exists
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    shutil.unpack_archive(zip_path, OUTPUT_DIR)
    print("Unzip complete.")

def main():
    if not os.path.exists(OUTPUT_DIR) or not os.listdir(OUTPUT_DIR):
        print("No output dataset to backup.")
        return

    try:
        zip_file = create_zip_archive()
        service = authenticate_drive()
        upload_file(service, zip_file)
        
        # Cleanup
        if os.path.exists(zip_file):
            os.remove(zip_file)
            
    except Exception as e:
        print(f"Backup failed: {e}")

if __name__ == '__main__':
    main()

