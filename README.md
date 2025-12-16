# Tumblr Backup Tool

Automatically back up your Tumblr posts to markdown files using the Tumblr API v2.

## Features

- Fetches all posts from your Tumblr blog (or just recent posts with incremental mode)
- Converts posts to markdown format with full reblog trail support
- All posts from a day saved to a single file: `output_dir/YYYY/MM/DD.md` (default output_dir is `backup`)
- **Incremental backups**: Skips already-backed-up days
- **Time-based incremental mode**: Only fetch posts from the last N hours (perfect for scheduled backups)
- **Downloads attachments locally**: Images, videos, and audio files saved in per-day `Attachments/` folders
- **Reblog trail formatting**: Displays full reblog chains with proper markdown quoting
- Supports all post types (text, photo, quote, link, video, audio)
- Smart attachments handling: Skips external embeds (YouTube, Vimeo, Spotify, etc.)
- Respects API rate limits
- Preserves metadata (timestamps as H2 headings, tags inline)

## Setup

### 1. Get Your Tumblr API Credentials

#### For Public Blogs:
1. Go to [https://www.tumblr.com/oauth/apps](https://www.tumblr.com/oauth/apps)
2. Click "Register application"
3. Fill in the required fields (you can use dummy URLs for callback)
4. Copy your **OAuth Consumer Key** (this is your API key)

#### For Private Blogs:
Private blogs require full OAuth authentication. You'll need to get OAuth tokens:

1. Follow steps 1-3 above to register your app
2. Copy both the **OAuth Consumer Key** AND **Consumer Secret**
3. Use a tool like [Tumblr OAuth Tool](https://api.tumblr.com/console/calls/user/info) or follow [Tumblr's OAuth flow](https://www.tumblr.com/docs/en/api/v2#auth) to obtain:
   - **OAuth Token**
   - **OAuth Token Secret**

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Your Credentials

Create a `config.json` file based on the example:

```bash
cp config.example.json config.json
```

Edit `config.json` with your details:

**For Public Blogs:**
```json
{
  "blog_identifier": "yourblog",
  "api_key": "your_consumer_key_here",
  "output_dir": "backup",
  "download_images": true,
  "download_videos": true,
  "download_audio": true
}
```

**For Private Blogs:**
```json
{
  "blog_identifier": "yourblog",
  "api_key": "your_consumer_key_here",
  "consumer_secret": "your_consumer_secret_here",
  "oauth_token": "your_oauth_token_here",
  "oauth_token_secret": "your_oauth_token_secret_here",
  "output_dir": "backup",
  "download_images": true,
  "download_videos": true,
  "download_audio": true
}
```

**Configuration Options:**
- **blog_identifier**: Your Tumblr username
- **api_key**: Your OAuth Consumer Key from step 1
- **consumer_secret**: (Private blogs only) Your OAuth Consumer Secret
- **oauth_token**: (Private blogs only) Your OAuth Token
- **oauth_token_secret**: (Private blogs only) Your OAuth Token Secret
- **output_dir**: Directory where backups will be saved (default: "backup")
- **download_images**: Whether to download images locally (default: true)
- **download_videos**: Whether to download videos locally (default: true)
- **download_audio**: Whether to download audio files locally (default: true)
- **incremental_hours**: (Optional) Only fetch posts from the last N hours. Set to `null` for full backup (default: 5)
- **delete_after_backup**: (Optional) Delete posts from Tumblr after successful backup. Requires OAuth credentials (default: true)
- **add_to_youtube_playlist**: (Optional) Automatically add YouTube videos from posts to a playlist (default: false)
- **youtube_playlist_id**: (Required if add_to_youtube_playlist is true) Your YouTube playlist ID (starts with "PL")
- **youtube_client_id**: (Required if add_to_youtube_playlist is true) Google OAuth2 client ID
- **youtube_client_secret**: (Required if add_to_youtube_playlist is true) Google OAuth2 client secret
- **youtube_refresh_token**: (Required if add_to_youtube_playlist is true) YouTube refresh token for headless authentication

## Usage

Run the backup script:

```bash
python tumblr_backup.py
```

The script will:
1. Fetch all posts from your blog
2. Group posts by day
3. Create `output_dir/YYYY/MM/DD.md` files for each day
4. Download attachments into that day's `Attachments/` folder (if enabled)
5. Save all posts from each day in a single markdown file with timestamps as H2 headings

### Incremental Backups

The script automatically skips days that have already been backed up by checking if the daily file exists. When you run the script again:
- Only new days are created
- Already downloaded attachments files in the day's `Attachments/` folder are skipped
- Existing daily files are not overwritten

This makes it efficient to run regularly (e.g., daily or weekly) to keep your backup up-to-date.

### Time-Based Incremental Mode

For scheduled backups that run frequently, you can use time-based incremental mode to only fetch recent posts:

```json
{
  "blog_identifier": "yourblog",
  "api_key": "your_consumer_key_here",
  "incremental_hours": 5
}
```

With `incremental_hours` set to 5:
- Only posts from the last 5 hours are fetched from the API
- Dramatically reduces API calls and processing time
- Perfect for automated backups that run every 4 hours (with a 1-hour buffer)
- Already-backed-up posts are still skipped via file checking

**When to use:**
- **Full backup** (`"incremental_hours": null`): First run, or occasional full sync
- **Incremental mode** (default, `incremental_hours: 5`): Scheduled backups running every few hours

### Attachments Download Behavior

- **Images**: All images are downloaded to the day's `Attachments/` folder
- **Videos**:
  - Tumblr-hosted videos are downloaded
  - External embeds (YouTube, Vimeo, Instagram) remain as links
- **Audio**:
  - Tumblr-hosted audio is downloaded
  - External embeds (Spotify, SoundCloud, Bandcamp) remain as links

## Output Format

### File Structure

```
backup/
└── 2025/
    └── 12/
        ├── 04.md
        ├── 05.md
        └── 04/
            └── Attachments/
                ├── photo1.jpg
                ├── photo2.png
                ├── video.mp4
                └── audio.mp3
```

Each day gets:
- A single markdown file at `output_dir/YYYY/MM/DD.md` containing all posts from that day
- Attachments saved to `output_dir/YYYY/MM/DD/Attachments/` if downloading is enabled

Files are organized by `year/month/day.md`. All posts from a day are in one file with timestamps as H2 headings. All attachments for that date are stored in the `DD/Attachments/` folder and linked from the markdown file (links reference that folder as `04/Attachments/...`).

### Post Format

Each daily markdown file includes:

- **H1 heading** with the date (YYYY-MM-DD)
- **H2 headings** for each post's timestamp (HH:MM)
- **Tags** shown inline after each timestamp
- **Reblog trail** (if the post is a reblog) with proper quote formatting
- **Content** formatted according to post type
- **Relative attachments paths** pointing to the `Attachments/` folder
- **Horizontal rules** (`---`) separating posts

Example daily file (`04.md`):

```markdown
# 2025-12-04

## 18:05

Tags: `photo`, `travel`

Check out this amazing photo from my trip!

![Photo](04/Attachments/sunset.jpg)

---

## 19:30

Tags: `reblog`

user1:
>Original post content here
>![Image](04/Attachments/photo.jpg)

user2:
>Added some thoughts about this

My additional commentary goes here

---

## 22:15

Just a quick text post before bed!
```

The daily file contains all posts chronologically with timestamps as H2 headings. The reblog trail shows the full chain of reblogs with each person's contribution quoted, followed by your own commentary.

## Rate Limits

The script respects Tumblr's API rate limits:
- 300 API calls per minute per IP
- 1,000 API calls per hour per consumer key

A small delay is added between requests to stay within limits.

## Automated Backups with GitHub Actions

The repository includes a GitHub Actions workflow that automatically backs up your posts daily and uploads them to Dropbox.

### Setup GitHub Actions with Dropbox

1. **Get Dropbox Credentials**:
   - Create a free [Dropbox](https://dub.sh/drop-box) account
   - Go to [Dropbox App Console](https://www.dropbox.com/developers/apps)
   - Click "Create app"
   - Choose "Scoped access"
   - Choose "Full Dropbox" or "App folder" access
   - Name your app (e.g., your blog name)
   - Once created, go to the "Permissions" tab and enable `files.content.write` and `files.content.read`
   - Go to the "Settings" tab and note your **App key** and **App secret**

2. **Generate a Refresh Token** (recommended):

   Run the included helper script to get a long-lived refresh token:
   ```bash
   python get_dropbox_refresh_token.py
   ```

   Follow the prompts:
   - Enter your App Key and App Secret
   - Visit the authorization URL in your browser
   - Copy the authorization code and paste it back
   - The script will output your `DROPBOX_REFRESH_TOKEN`

3. **Fork or push this repository to GitHub**

4. **Configure GitHub Secrets and Variables**:
   - Go to your repository on GitHub
   - Navigate to **Settings** → **Secrets and variables** → **Actions**

   **Add these Repository secrets** (Secrets tab):

   For Public Blogs:
   - `BLOG_IDENTIFIER`: Your Tumblr username
   - `API_KEY`: Your Tumblr API Consumer Key
   - `DROPBOX_APP_KEY`: Your Dropbox App Key
   - `DROPBOX_APP_SECRET`: Your Dropbox App Secret
   - `DROPBOX_REFRESH_TOKEN`: Your Dropbox refresh token from step 2

   For Private Blogs (add all of the above plus):
   - `CONSUMER_SECRET`: Your Tumblr OAuth Consumer Secret
   - `OAUTH_TOKEN`: Your Tumblr OAuth Token
   - `OAUTH_TOKEN_SECRET`: Your Tumblr OAuth Token Secret

   **Optional: Adjust attachments download flags in the workflow file**:
   - Open `.github/workflows/backup.yml`
   - In the `env` block, set `DOWNLOAD_IMAGES`, `DOWNLOAD_VIDEOS`, and `DOWNLOAD_AUDIO` to `false` if you want to skip downloading that attachments type (all default to `true`)

4. **Enable GitHub Actions**:
   - Go to the **Actions** tab in your repository
   - If prompted, enable workflows

### How It Works

- The workflow runs automatically daily at 12:00 AM Sydney time
- You can also trigger it manually from the Actions tab
- New posts and attachments are uploaded to Dropbox
- Existing posts are skipped (incremental backup)
- Files are synced to your Dropbox account automatically

### Manual Trigger

To run a backup manually:
1. Go to the **Actions** tab
2. Select **Tumblr Backup** workflow
3. Click **Run workflow**

## Local Dropbox Upload

You can also manually upload your backups to Dropbox from your local machine.

### Setup

1. **Get your Dropbox refresh token** (if you haven't already):
   ```bash
   python get_dropbox_refresh_token.py
   ```

2. **Set environment variables**:
   ```bash
   export DROPBOX_APP_KEY="your_app_key"
   export DROPBOX_APP_SECRET="your_app_secret"
   export DROPBOX_REFRESH_TOKEN="your_refresh_token"
   export LOCAL_FOLDER="backup"  # optional, defaults to "backup"
   export DROPBOX_PATH="/Tumblr"  # optional, defaults to root
   ```

3. **Upload to Dropbox**:
   ```bash
   python upload_to_dropbox.py
   ```

The script will upload all files from your backup folder to Dropbox. The refresh token never expires, so you can use the same credentials indefinitely.

## YouTube Playlist Integration

Automatically collect YouTube video links from your Tumblr posts and add them to a YouTube playlist.

### Features

- Extracts YouTube URLs from video blocks in posts (NPF format)
- Automatically adds videos to your specified playlist
- Skips duplicates (won't add videos already in the playlist)
- Works with GitHub Actions using refresh tokens (no browser required)

### Setup

1. **Create a Google Cloud Project**:
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project
   - Enable the "YouTube Data API v3"

2. **Get OAuth2 Credentials**:
   - In the Cloud Console, go to "Credentials"
   - Create "OAuth 2.0 Client ID" (choose "Desktop app")
   - Copy the Client ID and Client Secret

3. **Create a YouTube Playlist**:
   - Go to YouTube and create a new playlist
   - Get the playlist ID from the URL: `youtube.com/playlist?list=PLxxxxxxxxxx`

4. **Generate a Refresh Token**:
   ```bash
   python get_youtube_refresh_token.py
   ```
   - Enter your Client ID and Client Secret
   - Authorize in the browser
   - Copy the refresh token

5. **Update config.json**:
   ```json
   {
     "add_to_youtube_playlist": true,
     "youtube_playlist_id": "PLxxxxxxxxxx",
     "youtube_client_id": "your_client_id.apps.googleusercontent.com",
     "youtube_client_secret": "your_client_secret",
     "youtube_refresh_token": "your_refresh_token"
   }
   ```

### How It Works

- During backup, the script collects YouTube URLs from video blocks
- After backup completes, videos are automatically added to your playlist
- Only YouTube links from explicit video blocks are collected (not from text or comments)
- The refresh token allows it to work in GitHub Actions without browser interaction

### GitHub Actions Setup

Add these secrets to your GitHub repository (Settings → Secrets and variables → Actions):

- `YOUTUBE_PLAYLIST_ID`
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`

Set `ADD_TO_YOUTUBE_PLAYLIST: true` in the workflow environment variables.

## API Documentation

For more details about the Tumblr API: [https://www.tumblr.com/docs/en/api/v2](https://www.tumblr.com/docs/en/api/v2)
