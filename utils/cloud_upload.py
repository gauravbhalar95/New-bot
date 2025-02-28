from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.oauth2 import service_account
import os

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
SERVICE_ACCOUNT_FILE = "google_drive_credentials.json"

def upload_to_drive(file_path):
    """Uploads a file to Google Drive and returns the shared link."""
    try:
        credentials = service_account.Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=SCOPES
        )
        service = build("drive", "v3", credentials=credentials)

        file_metadata = {"name": os.path.basename(file_path), "parents": ["root"]}
        media = MediaFileUpload(file_path, resumable=True)

        uploaded_file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
        file_id = uploaded_file.get("id")

        # Make the file public
        service.permissions().create(fileId=file_id, body={"role": "reader", "type": "anyone"}).execute()

        link = f"https://drive.google.com/file/d/{file_id}/view"
        return link
    except Exception as e:
        print(f"Google Drive Upload Error: {e}")
        return None


from mega import Mega
import os

MEGA_EMAIL = "gauravbhalara@hotmail.com"
MEGA_PASSWORD = "Gaurav74$"

def upload_to_mega(file_path):
    """Uploads a file to Mega.nz and returns the public link."""
    try:
        mega = Mega()
        m = mega.login(MEGA_EMAIL, MEGA_PASSWORD)
        uploaded_file = m.upload(file_path)
        link = m.get_upload_link(uploaded_file)
        return link
    except Exception as e:
        print(f"Mega Upload Error: {e}")
        return None