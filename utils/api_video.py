import asyncio
import apivideo
from apivideo.apis import VideosApiAsync
import logging

# Replace with your actual API key
API_VIDEO_KEY = "__API_KEY__"

class ApiVideoClient:
    def __init__(self, api_key=API_VIDEO_KEY):
        self.api_key = api_key

    async def list_videos(self):
        """Fetch all videos from api.video."""
        async with apivideo.AuthenticatedApiClient(self.api_key) as client:
            videos_api = VideosApiAsync(client)

            try:
                response = await videos_api.list()
                return response.get("data", [])
            except Exception as e:
                logging.error(f"Error fetching videos: {e}")
                return []

    async def get_video_links(self):
        """Get streaming and download links for all videos."""
        videos = await self.list_videos()
        video_links = []

        for video in videos:
            video_id = video['videoId']
            title = video.get('title', 'No Title')

            # Permanent Streaming Link
            streaming_link = f"https://embed.api.video/vod/{video_id}"

            # Download Link (may expire)
            download_link = video.get('assets', {}).get('mp4')

            video_links.append({
                "title": title,
                "streaming_link": streaming_link,
                "download_link": download_link
            })

        return video_links

# For testing purposes
if __name__ == "__main__":
    async def main():
        api_client = ApiVideoClient()
        videos = await api_client.get_video_links()

        for video in videos:
            print(f"Title: {video['title']}")
            print(f"Streaming Link: {video['streaming_link']}")
            print(f"Download Link: {video['download_link'] if video['download_link'] else 'No Download Link'}")
            print("-" * 50)

    asyncio.run(main())