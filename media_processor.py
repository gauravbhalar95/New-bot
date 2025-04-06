async def process_download(message, url, is_audio=False, is_video_trim=False, is_audio_trim=False, start_time=None, end_time=None):
    """Handles video/audio download and sends it to Telegram or Dropbox."""
    try:
        request_type = "Video Download"
        if is_audio:
            request_type = "Audio Download"
        elif is_video_trim:
            request_type = "Video Trimming"
        elif is_audio_trim:
            request_type = "Audio Trimming"

        await send_message(message.chat.id, f"📥 **Processing your {request_type.lower()}...**")
        logger.info(f"Processing URL: {url}, Type: {request_type}")

        # Detect platform
        platform = detect_platform(url)
        if not platform:
            await send_message(message.chat.id, "⚠️ **Unsupported URL.**")
            return

        # Handle request based on type
        if is_video_trim:
            logger.info(f"Processing video trim request: Start={start_time}, End={end_time}")
            file_path, file_size = await process_video_trim(url, start_time, end_time)
            download_url = None
            file_paths = [file_path] if file_path else []

        elif is_audio_trim:
            logger.info(f"Processing audio trim request: Start={start_time}, End={end_time}")
            file_path, file_size = await process_audio_trim(url, start_time, end_time)
            download_url = None
            file_paths = [file_path] if file_path else []

        elif is_audio:
            result = await extract_audio_ffmpeg(url)
            if isinstance(result, tuple):
                file_path, file_size = result if len(result) == 2 else (result[0], None)
                download_url = None
                file_paths = [file_path] if file_path else []
            else:
                file_path, file_size, download_url = result, None, None
                file_paths = [file_path] if file_path else []

        else:
            if platform == "Instagram":
                if "/reel/" in url or "/tv/" in url:
                    result = await process_instagram(url)  # Handles Reels and IGTV videos
                else:
                    result = await process_instagram_image(url)  # Handles posts and stories
            else:
                result = await PLATFORM_HANDLERS[platform](url)

            # Handle different return formats from platform handlers
            if isinstance(result, tuple) and len(result) >= 3:
                file_paths, file_size, download_url = result
                if not isinstance(file_paths, list):
                    file_paths = [file_paths] if file_paths else []
            elif isinstance(result, tuple) and len(result) == 2:
                file_paths, file_size = result
                download_url = None
                if not isinstance(file_paths, list):
                    file_paths = [file_paths] if file_paths else []
            else:
                file_paths = result if isinstance(result, list) else [result] if result else []
                file_size = None
                download_url = None

        logger.info(f"Platform handler returned: file_paths={file_paths}, file_size={file_size}, download_url={download_url}")

        if not file_paths or all(not path for path in file_paths):
            logger.warning("No valid file paths returned from platform handler")
            await send_message(message.chat.id, "❌ **Download failed. No media found.**")
            return

        for file_path in file_paths:
            if not file_path or not os.path.exists(file_path):
                logger.warning(f"File path does not exist: {file_path}")
                continue

            if file_size is None:
                file_size = os.path.getsize(file_path)

            if file_size > TELEGRAM_FILE_LIMIT or file_size > 49 * 1024 * 1024:
                filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                logger.info(f"File too large for Telegram: {file_size} bytes. Using Dropbox.")
                dropbox_link = await upload_to_dropbox(file_path, filename)

                if dropbox_link:
                    logger.info(f"Successfully uploaded to Dropbox: {dropbox_link}")
                    await send_message(
                        message.chat.id,
                        f"⚠️ **File too large for Telegram.**\n📥 [Download from Dropbox]({dropbox_link})"
                    )
                else:
                    logger.warning("Dropbox upload failed")
                    if download_url:
                        await send_message(
                            message.chat.id,
                            f"⚠️ **File too large for Telegram.**\n📥 [Download here]({download_url})"
                        )
                    else:
                        await send_message(message.chat.id, "❌ **Download failed.**")
            else:
                try:
                    async with aiofiles.open(file_path, "rb") as file:
                        file_content = await file.read()
                        file_size_actual = len(file_content)

                        if file_size_actual > TELEGRAM_FILE_LIMIT:
                            logger.warning(f"Actual size exceeds limit: {file_size_actual}")
                            filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                            dropbox_link = await upload_to_dropbox(file_path, filename)

                            if dropbox_link:
                                await send_message(
                                    message.chat.id,
                                    f"⚠️ **File too large for Telegram.**\n📥 [Download from Dropbox]({dropbox_link})"
                                )
                            else:
                                await send_message(message.chat.id, "❌ **File too large. Upload failed.**")
                        else:
                            if is_audio or is_audio_trim:
                                await bot.send_audio(message.chat.id, file_content, timeout=600)
                            else:
                                await bot.send_video(message.chat.id, file_content, supports_streaming=True, timeout=600)

                except Exception as send_error:
                    logger.error(f"Error sending file to Telegram: {send_error}")
                    if "413" in str(send_error):
                        logger.info("Got 413 error, attempting Dropbox upload as fallback")
                        filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                        dropbox_link = await upload_to_dropbox(file_path, filename)

                        if dropbox_link:
                            await send_message(
                                message.chat.id,
                                f"⚠️ **File too large for Telegram.**\n📥 [Download from Dropbox]({dropbox_link})"
                            )
                        else:
                            await send_message(message.chat.id, "❌ **File too large and Dropbox upload failed.**")
                    else:
                        await send_message(message.chat.id, f"❌ **Error sending file: {str(send_error)}**")

            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Cleaned up file: {file_path}")
            except Exception as cleanup_error:
                logger.error(f"Failed to clean up file {file_path}: {cleanup_error}")

        gc.collect()

    except Exception as e:
        logger.error(f"Comprehensive error in process_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")