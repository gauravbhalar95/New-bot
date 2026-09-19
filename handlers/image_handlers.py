import os
import tempfile
import asyncio
import aiofiles
import aiohttp
import shutil
import traceback
import random

import instaloader
from asyncio import Lock
from instaloader.exceptions import ConnectionException

from utils.logger import logger
from utils.sanitize import sanitize_filename
from config import (
    session_id,
    crf_tk,
    ds_user,
    ig_dd,
    DOWNLOAD_DIR,
)


# ============================================================
# SETTINGS
# ============================================================

MIN_REQUEST_DELAY = 8
MAX_REQUEST_DELAY = 12

# Only one Instaloader request at a time.
SESSION_LOCK = Lock()

# Prevent hammering Instagram after a temporary block.
INSTAGRAM_COOLDOWN_UNTIL = 0


# ============================================================
# INSTALOADER
# ============================================================

INSTALOADER_INSTANCE = instaloader.Instaloader(
    download_videos=False,
    download_video_thumbnails=False,
    download_geotags=False,
    save_metadata=False,
    download_comments=False,
    post_metadata_txt_pattern="",
    quiet=True,
)


# ============================================================
# SESSION INITIALIZATION
# ============================================================

def initialize_instagram_session():
    """
    Load the existing Instagram cookies into Instaloader.

    IMPORTANT:
    We intentionally DO NOT call test_login() here.

    Instagram currently returns 401 for the GraphQL login-check
    endpoint used by Instaloader. Calling test_login() during
    startup therefore causes unnecessary 401 errors.
    """

    try:
        context = INSTALOADER_INSTANCE.context

        # Clear old cookies first.
        context._session.cookies.clear()

        cookies = {
            "sessionid": session_id,
            "csrftoken": crf_tk,
            "ds_user_id": ds_user,
            "ig_did": ig_dd,
        }

        for name, value in cookies.items():

            if value:
                context._session.cookies.set(
                    name,
                    value,
                    domain=".instagram.com",
                    path="/",
                )

        logger.info(
            "✅ Instagram session cookies loaded."
        )

        logger.info(
            "ℹ️ Instagram login verification skipped "
            "to avoid unnecessary GraphQL 401 requests."
        )

        return True

    except Exception as e:

        logger.error(
            f"❌ Failed to load Instagram session: {e}",
            exc_info=True,
        )

        return False


# ============================================================
# INSTAGRAM ERROR HANDLING
# ============================================================

def is_instagram_block_error(error):
    """
    Detect temporary Instagram blocking/rate limiting.
    """

    message = str(error).lower()

    indicators = (
        "please wait a few minutes",
        "401 unauthorized",
        "429",
        "rate limit",
        "too many requests",
        "challenge_required",
        "checkpoint_required",
    )

    return any(
        indicator in message
        for indicator in indicators
    )


def set_instagram_cooldown(seconds=300):

    global INSTAGRAM_COOLDOWN_UNTIL

    INSTAGRAM_COOLDOWN_UNTIL = (
        asyncio.get_running_loop().time()
        + seconds
    )

    logger.warning(
        f"⏳ Instagram cooldown enabled for {seconds} seconds."
    )


def instagram_is_on_cooldown():

    if INSTAGRAM_COOLDOWN_UNTIL <= 0:
        return False

    return (
        asyncio.get_running_loop().time()
        < INSTAGRAM_COOLDOWN_UNTIL
    )


# ============================================================
# FETCH POST
# ============================================================

async def get_post(shortcode: str):
    """
    Fetch an Instagram post safely.

    No recursive retry is performed while holding SESSION_LOCK.
    """

    if instagram_is_on_cooldown():

        logger.warning(
            "⏳ Instagram is currently on cooldown. "
            "Skipping request."
        )

        raise RuntimeError(
            "Instagram is temporarily unavailable. "
            "Please try again later."
        )

    # Random delay before contacting Instagram.
    await asyncio.sleep(
        random.uniform(
            MIN_REQUEST_DELAY,
            MAX_REQUEST_DELAY,
        )
    )

    async with SESSION_LOCK:

        try:

            logger.info(
                f"📡 Fetching Instagram post: {shortcode}"
            )

            post = await asyncio.to_thread(
                instaloader.Post.from_shortcode,
                INSTALOADER_INSTANCE.context,
                shortcode,
            )

            logger.info(
                f"✅ Instagram post fetched: {shortcode}"
            )

            return post

        except ConnectionException as e:

            error_message = str(e)

            if is_instagram_block_error(e):

                set_instagram_cooldown(300)

                logger.warning(
                    "⚠️ Instagram rejected the request. "
                    f"Post={shortcode} Error={error_message}"
                )

                raise RuntimeError(
                    "Instagram temporarily rejected this request. "
                    "Please try again later."
                ) from e

            logger.error(
                f"❌ Instagram connection error: "
                f"{error_message}"
            )

            raise

        except Exception as e:

            if is_instagram_block_error(e):

                set_instagram_cooldown(300)

                logger.warning(
                    "⚠️ Instagram temporarily rejected "
                    "the request."
                )

                raise RuntimeError(
                    "Instagram temporarily rejected this request. "
                    "Please try again later."
                ) from e

            logger.error(
                f"❌ Error fetching Instagram post "
                f"{shortcode}: {e}\n"
                f"{traceback.format_exc()}"
            )

            raise


# ============================================================
# IMAGE DOWNLOAD
# ============================================================

async def download_image(
    session,
    url,
    temp_path,
    final_path,
):

    try:

        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(
                total=60
            ),
        ) as response:

            response.raise_for_status()

            async with aiofiles.open(
                temp_path,
                "wb",
            ) as file:

                await file.write(
                    await response.read()
                )

        await asyncio.to_thread(
            shutil.move,
            temp_path,
            final_path,
        )

        logger.info(
            f"✅ Saved image: {final_path}"
        )

        return final_path

    except Exception as e:

        logger.error(
            f"❌ Failed downloading image: {e}"
        )

        return None


# ============================================================
# CLEANUP
# ============================================================

async def cleanup_temp_dir(temp_dir):

    try:

        await asyncio.to_thread(
            shutil.rmtree,
            temp_dir,
            ignore_errors=True,
        )

    except Exception as e:

        logger.warning(
            f"⚠️ Temp cleanup failed: "
            f"{temp_dir} - {e}"
        )


# ============================================================
# INSTAGRAM IMAGE PROCESSOR
# ============================================================

async def process_instagram_image(url: str):
    """
    Download all images from an Instagram post.
    """

    if "/p/" not in url:

        logger.warning(
            "⚠️ Invalid Instagram post URL."
        )

        return [], None

    shortcode = (
        url.split("/p/")[1]
        .split("/")[0]
        .split("?")[0]
    )

    if not shortcode:

        logger.warning(
            "⚠️ Instagram shortcode is empty."
        )

        return [], None

    os.makedirs(
        DOWNLOAD_DIR,
        exist_ok=True,
    )

    temp_dir = tempfile.mkdtemp()

    image_paths = []
    uploader = None

    try:

        # ----------------------------------------------------
        # GET POST
        # ----------------------------------------------------

        post = await get_post(
            shortcode
        )

        uploader = post.owner_username

        # ----------------------------------------------------
        # GET MEDIA NODES
        # ----------------------------------------------------

        if post.typename == "GraphSidecar":

            nodes = list(
                post.get_sidecar_nodes()
            )

        else:

            nodes = [post]

        logger.info(
            f"📸 Found {len(nodes)} Instagram media item(s)."
        )

        # ----------------------------------------------------
        # DOWNLOAD
        # ----------------------------------------------------

        async with aiohttp.ClientSession() as session:

            for idx, node in enumerate(nodes):

                if node.is_video:

                    logger.info(
                        f"⏭️ Skipping video item {idx}."
                    )

                    continue

                filename = sanitize_filename(
                    f"{uploader}_{shortcode}_{idx}.jpg"
                )

                final_path = os.path.join(
                    DOWNLOAD_DIR,
                    filename,
                )

                temp_path = os.path.join(
                    temp_dir,
                    filename,
                )

                # Avoid duplicate download.
                if os.path.exists(final_path):

                    logger.info(
                        f"♻️ File already exists: "
                        f"{final_path}"
                    )

                    image_paths.append(
                        final_path
                    )

                    continue

                result = await download_image(
                    session,
                    node.display_url,
                    temp_path,
                    final_path,
                )

                if result:

                    image_paths.append(
                        result
                    )

                # Small delay between CDN requests.
                await asyncio.sleep(
                    random.uniform(1, 2)
                )

        logger.info(
            f"✅ Instagram image processing completed. "
            f"Downloaded={len(image_paths)}"
        )

        return image_paths, uploader

    except Exception as e:

        logger.error(
            "❌ Instagram image processing failed: "
            f"{e}\n{traceback.format_exc()}"
        )

        return [], None

    finally:

        await cleanup_temp_dir(
            temp_dir
        )


# ============================================================
# BULK INSTAGRAM IMAGES
# ============================================================

async def process_bulk_instagram_images(
    urls: list[str],
):

    all_images = []

    for index, url in enumerate(urls):

        logger.info(
            f"📦 Processing Instagram item "
            f"{index + 1}/{len(urls)}"
        )

        images, _ = await process_instagram_image(
            url
        )

        all_images.extend(
            images
        )

        if index < len(urls) - 1:

            await asyncio.sleep(
                random.uniform(8, 12)
            )

    return all_images


# ============================================================
# LOAD SESSION
# ============================================================

# IMPORTANT:
# This only loads cookies.
# It DOES NOT call Instagram test_login().
initialize_instagram_session()