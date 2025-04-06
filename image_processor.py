async def process_image_download(message, url):
    """Handles image download and sends it to Telegram or Dropbox."""
    try:
        await send_message(message.chat.id, "🖼️ Processing Instagram image...")
        logger.info(f"Processing Instagram image URL: {url}")
        # Process the Instagram image
        try:
            result = await process_instagram_image(url)

            # Handle different return formats
            if isinstance(result, list):
                file_paths = result
            elif isinstance(result, tuple) and len(result) >= 2:
                file_paths = result[0] if isinstance(result[0], list) else [result[0]]
            else:
                file_paths = [result] if result else []

            if not file_paths or all(not path for path in file_paths):
                logger.warning("No valid image paths returned from Instagram handler")
                await send_message(message.chat.id, "❌ **Download failed. No images found.**")
                return

            # Process each image
            for file_path in file_paths:
                if not file_path or not os.path.exists(file_path):
                    logger.warning(f"Image path does not exist: {file_path}")
                    continue

                # Get file size
                file_size = os.path.getsize(file_path)

                # Handle case where file is too large for Telegram
                if file_size > TELEGRAM_FILE_LIMIT:
                    filename = f"{message.chat.id}_{os.path.basename(file_path)}"
                    logger.info(f"Image too large for Telegram: {file_size} bytes. Using Dropbox.")

                    # Upload to Dropbox
                    dropbox_link = await upload_to_dropbox(file_path, filename)

                    if dropbox_link:
                        logger.info(f"Successfully uploaded image to Dropbox: {dropbox_link}")
                        await send_message(
                            message.chat.id,
                            f"⚠️ **Image too large for Telegram.**\n📥 [Download from Dropbox]({dropbox_link})",
                            parse_mode="Markdown"
                        )
                    else:
                        logger.warning("Dropbox upload failed")
                        await send_message(message.chat.id, "❌ **Image download failed.**")
                else:
                    # Send image to Telegram
                    try:
                        async with aiofiles.open(file_path, "rb") as file:
                            file_content = await file.read()
                            await bot.send_photo(message.chat.id, file_content, timeout=60)
                            logger.info(f"Successfully sent image to Telegram")
                    except Exception as send_error:
                        logger.error(f"Error sending image to Telegram: {send_error}")
                        await send_message(message.chat.id, f"❌ **Error sending image: {str(send_error)}**")

                # Cleanup the file
                try:
                    if os.path.exists(file_path):
                        os.remove(file_path)
                        logger.info(f"Cleaned up image file: {file_path}")
                except Exception as cleanup_error:
                    logger.error(f"Failed to clean up image file {file_path}: {cleanup_error}")

            # Send success message
            await send_message(message.chat.id, "✅ **Instagram image(s) downloaded successfully!**")

        except Exception as e:
            logger.error(f"Error processing Instagram image: {e}", exc_info=True)
            await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`", parse_mode="Markdown")

    except Exception as e:
        logger.error(f"Comprehensive error in process_image_download: {e}", exc_info=True)
        await send_message(message.chat.id, f"❌ **An error occurred:** `{e}`")