# Mattermost-Export

A simple Python script that exports Mattermost chat data to various formats via the Mattermost API

## Installation

### Python Dependencies

Install the required dependencies:

```bash
pip install -r requirements.txt
```

### Fonts (Optional but Recommended)

The script uses **NotoSans** fonts for better Unicode support (emojis, international characters, etc.). If NotoSans is not installed, the script will fall back to system default fonts (Helvetica on macOS, DejaVu Sans on Linux).

**macOS:**
```bash
# Using Homebrew (recommended)
brew install font-noto-sans

# For emoji support, install Noto Color Emoji:
# Option 1: Try Homebrew (may fail due to Google storage issues)
brew install font-noto-color-emoji

# Option 2: Manual installation (if Homebrew fails)
# 1. Download from: https://fonts.google.com/noto/specimen/Noto+Color+Emoji
# 2. Or direct download: https://github.com/googlefonts/noto-emoji/releases
# 3. Extract and copy NotoColorEmoji.ttf to ~/Library/Fonts/

# Or download NotoSans manually from:
# https://fonts.google.com/noto/specimen/Noto+Sans
# Then copy the .ttf files to ~/Library/Fonts/
```

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install fonts-noto fonts-noto-color-emoji

# Fedora/RHEL
sudo dnf install google-noto-sans-fonts google-noto-emoji-fonts

# Or download manually and place in:
# ~/.local/share/fonts/ or /usr/local/share/fonts/
```

**Windows:**
Download NotoSans fonts from [Google Fonts](https://fonts.google.com/noto/specimen/Noto+Sans) and install them through the Font Settings.

For emoji support, download Noto Color Emoji from [Google Fonts](https://fonts.google.com/noto/specimen/Noto+Color+Emoji) and install it.

**Note:** The script will work without NotoSans, but Unicode characters (emojis, non-Latin scripts) may not render correctly. For best results, install both NotoSans and Noto Color Emoji fonts.

## Authentication

To use this script, you need to obtain a Mattermost Personal Access Token (PAT). Here's how:

### Method 1: Using Mattermost Web Interface

1. Log in to your Mattermost instance
2. Click on your profile picture (top right)
3. Go to **Account Settings** → **Security** → **Personal Access Tokens**
4. Click **Create Token**
5. Give it a description (e.g., "Export Script")
6. Copy the token immediately (you won't be able to see it again)

### Method 2: Using Mattermost API (for server administrators)

If you have API access, you can create a token programmatically:

```bash
curl -X POST 'https://your-mattermost-server.com/api/v4/users/login' \
  -H 'Content-Type: application/json' \
  -d '{"login_id":"your-username","password":"your-password"}'

# Then use the token from the response to create a PAT
```

**Note:** The token needs appropriate permissions to read channels and messages. Make sure your user has access to the channels you want to export.

## Usage

MMExport2PDF.py [options]

MMExport2PDF.py is used to export channels and DMs from a Mattermost team.

### Basic Options

```
options:
  -h, --help            show this help message and exit

User Info:
  -a AUTH, --auth AUTH  Auth Token (required)
  -u USER, --user USER  Username for authentication and channel access. The script exports ALL messages from channels this user can access, not just messages from this user. (required)
  -t TEAM, --team TEAM  Team to export from (required)

Server Info:
  -s SERVER, --server SERVER
                        Hostname or IP of the server (default: mattermost.com)
  --protocol {http,https}
                        Protocol to use (default: https)
  --port PORT           Port number (default: 443 for https, 80 for http)

Channel Categories:
  -p, --public          Exclude public channels
  -P, --private         Exclude private channels
  -g, --groups          Exclude group messages
  -d, --DMs             Exclude direct messages

Message Filters:
  -c CHANNEL, --channel CHANNEL
                        Export only a single channel (by channel name or display name)
  -I [INCLUDE ...], --include [INCLUDE ...]
                        Only include these channels in the export (default: [])
  -E [EXCLUDE ...], --exclude [EXCLUDE ...]
                        Exclude these channels from the export (default: [])
  --start-date START_DATE
                        Start date for message export (YYYY-MM-DD format)
  --end-date END_DATE   End date for message export (YYYY-MM-DD format)

Export Options:
  -i, --images          Embed images in PDF (default: False)
  -f, --files           Embed files in PDF (default: False)
  -j, --json            Export JSON (default: False)
  -o OUTPUT, --output OUTPUT
                        Base output directory (default: ./users)
```

## Examples

### Export all channels for a user (remote server)

```bash
python3 MMExport2PDF.py \
  --auth "your-auth-token" \
  --user "username" \
  --team "team-name" \
  --server "mattermost.example.com"
```

### Export from local Mattermost server

```bash
python3 MMExport2PDF.py \
  --auth "your-auth-token" \
  --user "username" \
  --team "team-name" \
  --server "localhost" \
  --protocol http \
  --port 8065
```

### Export a single channel

```bash
python3 MMExport2PDF.py \
  --auth "your-auth-token" \
  --user "username" \
  --team "team-name" \
  --server "mattermost.example.com" \
  --channel "general"
```

### Export messages from a specific date range

```bash
python3 MMExport2PDF.py \
  --auth "your-auth-token" \
  --user "username" \
  --team "team-name" \
  --server "mattermost.example.com" \
  --start-date "2024-01-01" \
  --end-date "2024-12-31"
```

### Export single channel with date range and include images

```bash
python3 MMExport2PDF.py \
  --auth "your-auth-token" \
  --user "username" \
  --team "team-name" \
  --server "mattermost.example.com" \
  --channel "general" \
  --start-date "2024-01-01" \
  --end-date "2024-12-31" \
  --images
```

### Export only public channels, excluding specific ones

```bash
python3 MMExport2PDF.py \
  --auth "your-auth-token" \
  --user "username" \
  --team "team-name" \
  --server "mattermost.example.com" \
  --private \
  --groups \
  --DMs \
  --exclude "off-topic" "random"
```

## Notes

- **Important:** The `--user` parameter is used for authentication and to determine which channels you have access to. The script exports **ALL messages** from accessible channels, regardless of who wrote them. It does NOT filter messages by author.
- This can take a long time to run, especially for channels with many messages
- When using `--channel`, you cannot use `--include` or `--exclude` options
- Date filtering uses UTC timezone. Make sure to account for timezone differences
- The script creates a directory structure: `{output}/{username}/files/` for downloaded files
- PDF output is saved as `{output}/{username}/{username}.pdf`
- JSON export (if enabled) is saved as `{output}/{username}/{username}.gz`
