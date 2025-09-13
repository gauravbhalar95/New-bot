import os
import json
from cryptography.fernet import Fernet

CREDENTIALS_FILE = "mega_credentials.json"

# 🔑 Generate or load encryption key
def get_encryption_key():
    key_file = "mega_secret.key"
    if not os.path.exists(key_file):
        key = Fernet.generate_key()
        with open(key_file, "wb") as f:
            f.write(key)
    else:
        with open(key_file, "rb") as f:
            key = f.read()
    return key

fernet = Fernet(get_encryption_key())

# 📦 Save credentials (encrypted)
def store_encrypted_credentials(chat_id, username, password):
    creds = {}
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE, "r") as f:
            creds = json.load(f)

    creds[str(chat_id)] = {
        "username": fernet.encrypt(username.encode()).decode(),
        "password": fernet.encrypt(password.encode()).decode()
    }

    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(creds, f, indent=2)

# 📦 Get credentials
def get_mega_credentials(chat_id):
    if not os.path.exists(CREDENTIALS_FILE):
        return None
    with open(CREDENTIALS_FILE, "r") as f:
        creds = json.load(f)
    if str(chat_id) not in creds:
        return None
    data = creds[str(chat_id)]
    return {
        "username": fernet.decrypt(data["username"].encode()).decode(),
        "password": fernet.decrypt(data["password"].encode()).decode()
    }

# 📦 Delete credentials
def delete_mega_credentials(chat_id):
    if not os.path.exists(CREDENTIALS_FILE):
        return False
    with open(CREDENTIALS_FILE, "r") as f:
        creds = json.load(f)
    if str(chat_id) in creds:
        del creds[str(chat_id)]
        with open(CREDENTIALS_FILE, "w") as f:
            json.dump(creds, f, indent=2)
        return True
    return False