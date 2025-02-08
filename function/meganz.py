from mega import Mega
import os

# ✅ Initialize MEGA session
mega = Mega()
mega_session = None  # Will store login session

def mega_login(email, password):
    """Logs in to MEGA with given credentials."""
    global mega_session
    try:
        mega_session = mega.login(email, password)
        return "✅ MEGA Login Successful!"
    except Exception as e:
        return f"❌ MEGA Login Failed: {str(e)}"

def upload_to_mega(file_path):
    """Uploads a file to MEGA and returns the download link."""
    if mega_session is None:
        return "❌ Please log in to MEGA first using /meganz <email> <password>."

    try:
        if not os.path.exists(file_path):
            return "❌ File not found."

        uploaded_file = mega_session.upload(file_path)
        file_url = mega_session.get_upload_link(uploaded_file)
        return f"✅ File Uploaded Successfully!\n🔗 MEGA Link: {file_url}"
    except Exception as e:
        return f"❌ Upload Failed: {str(e)}"

def download_from_mega(url, dest_folder="./downloads"):
    """Downloads a file from MEGA and saves it to the given folder."""
    if mega_session is None:
        return "❌ Please log in to MEGA first using /meganz <email> <password>."

    try:
        if not os.path.exists(dest_folder):
            os.makedirs(dest_folder)

        mega_session.download_url(url, dest_folder)
        return f"✅ File Downloaded Successfully! Saved to: {dest_folder}"
    except Exception as e:
        return f"❌ MEGA Download Failed: {str(e)}"