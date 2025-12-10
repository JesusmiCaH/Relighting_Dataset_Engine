import os
import shutil
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Config
SCOPES = ['https://www.googleapis.com/auth/drive.file']
OUTPUT_DIR = "output_dataset"
ZIP_NAME = "dataset_backup"
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'credentials.json'

def create_zip_archive():
    print("Compressing dataset...")
    shutil.make_archive(ZIP_NAME, 'zip', OUTPUT_DIR)
    print(f"Created {ZIP_NAME}.zip")
    return f"{ZIP_NAME}.zip"

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

if __name__ == '__main__':
    main()
