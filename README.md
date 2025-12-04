# Tumblr Backup Tool

Automatically back up your Tumblr posts to markdown files using the Tumblr API v2.

## Features

- Fetches all posts from your Tumblr blog
- Converts posts to markdown format
- Each post saved to its own file under `output_dir/YYYY/MM/DD/HH-MM-title.md` (default output_dir is `backup`)
- **Incremental backups**: Skips already-backed-up posts
- **Downloads attachments locally**: Images, videos, and audio files saved in per-day `Attachments/` folders
- Supports all post types (text, photo, quote, link, video, audio)
- Smart attachments handling: Skips external embeds (YouTube, Vimeo, Spotify, etc.) and oversized files, keeping them as URL links
- Respects API rate limits
- Preserves metadata (dates and tags in front matter)

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

## Usage

Run the backup script:

```bash
python tumblr_backup.py
```

The script will:
1. Fetch all posts from your blog
2. Check for existing post files and skip them
3. Create `output_dir/YYYY/MM/DD/` folders with filenames prefixed by the post time
4. Download attachments into that day's `Attachments/` folder (if enabled)
5. Save each post as an individual markdown file

### Incremental Backups

The script automatically skips posts that have already been backed up by checking if the file exists. When you run the script again:
- Only new posts are created
- Already downloaded attachments files in the day's `Attachments/` folder are skipped
- No duplicate posts will be created

This makes it efficient to run regularly (e.g., daily or weekly) to keep your backup up-to-date.

### Attachments Download Behavior

- **Images**: All images are downloaded to the day's `Attachments/` folder
- **Videos**:
  - Tumblr-hosted videos are downloaded (max 100MB)
  - External embeds (YouTube, Vimeo, Instagram) remain as links
  - Files larger than 100MB remain as links
- **Audio**:
  - Tumblr-hosted audio is downloaded (max 100MB)
  - External embeds (Spotify, SoundCloud, Bandcamp) remain as links
  - Files larger than 100MB remain as links

## Output Format

### File Structure

```
backup/
└── 2025/
    └── 12/
        └── 04/
            ├── 17-15-my-first-post.md
            ├── 18-05-weekend-thoughts.md
            └── Attachments/
                ├── photo1.jpg
                ├── photo2.png
                ├── video.mp4
                └── audio.mp3
```

Each post gets:
- A markdown file at `output_dir/YYYY/MM/DD/HH-MM-<sanitized-title>.md`
- Attachments saved to `output_dir/YYYY/MM/DD/Attachments/` if downloading is enabled

Folders are organized by `year/month/day`. Filenames are prefixed with the post time (`HH-MM`) followed by a sanitized title. All attachments for posts on that date are stored in the shared `Attachments/` folder and linked from each markdown file (links reference that folder as `Attachments/...`).

### Post Format

Each markdown file includes:

- **Front matter** with `date` and `tags`
- **Content** formatted according to post type
- **Relative attachments paths** pointing to the `Attachments/` folder

Example file content (`18-05-travel-update.md`):

```markdown
---
date: 2025-12-04 18:05:00
tags:
  - photo
  - travel
---

Check out this amazing photo from my trip!

![Photo](Attachments/sunset.jpg)
```

## Rate Limits

The script respects Tumblr's API rate limits:
- 300 API calls per minute per IP
- 1,000 API calls per hour per consumer key

A small delay is added between requests to stay within limits.

## Automated Backups with GitHub Actions

The repository includes a GitHub Actions workflow that automatically backs up your posts every 4 hours and uploads them to Dropbox.

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

- The workflow runs automatically every 4 hours
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

## API Documentation

For more details about the Tumblr API: [https://www.tumblr.com/docs/en/api/v2](https://www.tumblr.com/docs/en/api/v2)
