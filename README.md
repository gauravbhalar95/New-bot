# New-bot

Telegram media downloader bot supporting Instagram and other supported media platforms.

## Docker image

Docker Hub image: [`gauravabhalara/newbot`](https://hub.docker.com/r/gauravabhalara/newbot)

Pull the `latest` tag (if that tag has been published):

```bash
docker pull gauravabhalara/newbot:latest
```

If Docker Hub shows a different tag as the published version, replace `latest` in the commands below with that tag.

## Configure environment

Create a local file named `.env` in your deployment directory. Do not commit it or share it publicly.

```dotenv
BOT_TOKEN=your_telegram_bot_token
WEBHOOK_URL=https://your-public-domain.example
WEBHOOK_SECRET=replace_with_a_long_random_secret
PORT=8080
```

Required variables:
- `BOT_TOKEN`: token from Telegram's BotFather.
- `WEBHOOK_URL`: the public HTTPS base URL for this deployment.
- `WEBHOOK_SECRET`: a private secret used to protect the Telegram webhook.

Optional Instagram and YouTube settings can be supplied as environment variables when needed, including `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET`, `INSTAGRAM_REDIRECT_URI`, `INSTAGRAM_SESSIONID`, and `YOUTUBE_COOKIES_B64`. Keep all credentials and cookies private.

## Run the container

Make sure your `.env` file is in the current directory, then run:

```bash
docker run -d \
  --name newbot \
  --restart unless-stopped \
  --env-file .env \
  -p 8080:8080 \
  -v newbot-downloads:/app/downloads \
  gauravabhalara/newbot:latest
```

Check that the container is running:

```bash
docker ps
docker logs -f newbot
```

The container exposes port `8080`. Configure your hosting provider or reverse proxy to route HTTPS traffic to that port. The application includes a health endpoint at `/health`.

Stop the container:

```bash
docker stop newbot
```

Remove it:

```bash
docker rm newbot
```

## Security notes

- Never commit `.env`, Telegram bot tokens, Instagram credentials, session IDs, or cookie files.
- Use HTTPS for the public webhook URL.
- The Docker pull command assumes the `latest` tag exists on Docker Hub; use a published tag if it does not.
