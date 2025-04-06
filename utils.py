async def send_message(chat_id, text):
    """Sends a message asynchronously."""
    try:
        await bot.send_message(chat_id, text)
    except Exception as e:
        logger.error(f"Error sending message: {e}")


def detect_platform(url):
    """Detects the platform based on URL patterns."""
    for platform, pattern in PLATFORM_PATTERNS.items():
        if pattern.search(url):
            return platform
    return None


async def upload_to_dropbox(file_path, filename):
    """
    Uploads a file to Dropbox and returns a shareable link.

    Args:
        file_path (str): Path to the file to upload
        filename (str): Name to use for the file in Dropbox

    Returns:
        str: Shareable link to the uploaded file
    """
    try:
        # Validate access token
        try:
            dbx.users_get_current_account()
        except Exception as auth_error:
            logger.error(f"Dropbox authentication failed: {auth_error}")
            return None

        dropbox_path = f"/telegram_uploads/{filename}"
        file_size = os.path.getsize(file_path)

        with open(file_path, "rb") as f:
            if file_size > 140 * 1024 * 1024:  # 140 MB threshold
                logger.info("Large file detected, using upload session")
                upload_session = dbx.files_upload_session_start(f.read(4 * 1024 * 1024))
                cursor = dropbox.files.UploadSessionCursor(
                    session_id=upload_session.session_id,
                    offset=f.tell()
                )

                while f.tell() < file_size:
                    chunk_size = 4 * 1024 * 1024
                    if (file_size - f.tell()) <= chunk_size:
                        dbx.files_upload_session_finish(
                            f.read(chunk_size),
                            cursor,
                            dropbox.files.CommitInfo(path=dropbox_path)
                        )
                        break
                    else:
                        dbx.files_upload_session_append_v2(
                            f.read(chunk_size),
                            cursor
                        )
                        cursor.offset = f.tell()
            else:
                dbx.files_upload(f.read(), dropbox_path, mode=dropbox.files.WriteMode.overwrite)

        shared_link = dbx.sharing_create_shared_link_with_settings(
            dropbox_path,
            dropbox.sharing.SharedLinkSettings(
                requested_visibility=dropbox.sharing.RequestedVisibility.public
            )
        )
        return shared_link.url.replace('dl=0', 'dl=1')

    except AuthError as auth_error:
        logger.error(f"Dropbox authentication error: {auth_error}")
        return None
    except ApiError as api_error:
        logger.error(f"Dropbox API error: {api_error}")
        return None
    except Exception as e:
        logger.error(f"Unexpected Dropbox upload error: {e}")
        return None