# Tumblr Backup Tool

Automatically back up your Tumblr posts to markdown files using the Tumblr API v2.

## Features

- Fetches all posts from your Tumblr blog
- Converts posts to markdown format
- Each post saved to its own file with a clean folder structure
- **Incremental backups**: Skips already-backed-up posts
- **Downloads attachments locally**: Images, videos, and audio files saved in post-specific attachments folders
- Supports all post types (text, photo, quote, link, video, audio)
- Smart attachments handling: Skips external embeds (YouTube, Vimeo, Spotify, etc.) and oversized files, keeping them as URL links
- Respects API rate limits
- Preserves metadata (tags, dates, URLs, post IDs)

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
3. Create a folder structure organized by date
4. Download attachments to post-specific folders (if enabled)
5. Save each post as an individual markdown file

### Incremental Backups

The script automatically skips posts that have already been backed up by checking if the file exists. When you run the script again:
- Only new posts are created
- Already downloaded attachments files are skipped
- No duplicate posts will be created

This makes it efficient to run regularly (e.g., daily or weekly) to keep your backup up-to-date.

### Attachments Download Behavior

- **Images**: All images are downloaded to the post's attachments folder
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
├── 2024/
│   ├── 2024-01/
│   │   ├── 2024-01-15/
│   │   │   ├── my-first-post.md
│   │   │   ├── another-post.md
│   │   │   └── Attachments/
│   │   │       ├── photo1.jpg
│   │   │       └── photo2.png
│   │   └── 2024-01-20/
│   │       ├── weekend-thoughts.md
│   │       └── Attachments/
│   │           └── sunset.jpg
│   └── 2024-03/
│       └── 2024-03-05/
│           ├── travel-update.md
│           └── Attachments/
│               ├── video.mp4
│               └── audio.mp3
```

Each post gets:
- Its own markdown file named after the post title (sanitized)
- A `Attachments/` subfolder containing all images, videos, and audio for that specific post

### Post Format

Each markdown file includes:

- **Front matter** with metadata (post_id, title, date, type, URL, tags)
- **Content** formatted according to post type
- **Relative attachments paths** pointing to the `Attachments/` folder

Example file content (`my-first-post.md`):

```markdown
---
post_id: 123456789
title: My First Post
date: 2024-03-15 10:30:00
type: text
url: https://yourblog.tumblr.com/post/123456789
tags:
  - example
  - tumblr
---

## My First Post

This is the content of my first post...
```

Example photo post (`travel-update.md`):

```markdown
---
post_id: 123456790
title: Travel Update
date: 2024-03-15 14:45:00
type: photo
url: https://yourblog.tumblr.com/post/123456790
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

1. **Get a Dropbox Access Token**:
   - Create a free [Dropbox](https://dub.sh/drop-box) account
   - Go to [Dropbox App Console](https://www.dropbox.com/developers/apps)
   - Click "Create app"
   - Choose "Scoped access"
   - Name your app (e.g., your blog name)
   - Once created, go to the "Permissions" tab and enable `files.content.write` and `files.content.read`
   - Go to the "Settings" tab and generate an access token

2. **Fork or push this repository to GitHub**

3. **Configure GitHub Secrets and Variables**:
   - Go to your repository on GitHub
   - Navigate to **Settings** → **Secrets and variables** → **Actions**

   **Add these Repository secrets** (Secrets tab):

   For Public Blogs:
   - `BLOG_IDENTIFIER`: Your Tumblr username
   - `API_KEY`: Your Tumblr API Consumer Key
   - `DROPBOX_ACCESS_TOKEN`: Your Dropbox access token from step 1

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

## API Documentation

For more details about the Tumblr API: [https://www.tumblr.com/docs/en/api/v2](https://www.tumblr.com/docs/en/api/v2)
