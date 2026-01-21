#!/usr/bin/env python3
# -*- coding: utf-8 -*-

''' MMExport2HTML

Using the Mattermost API, connects to an instance and exports
all channel for a user on a team to HTML format.

Images and Videos are downloaded as well.

'''

#########################
## Python Imports
##

import argparse
import requests
import gzip
import simplejson as json
#import ujson as json
import datetime
import shutil
import sys
import os
import platform
import html
import base64
import re
from pathlib import Path
from urllib.parse import quote

import traceback

#########################
## Thirdparty Imports
##

# HTML export - no PDF dependencies needed 

__author__ = 'Alexander J. Lallier'
__version__ = '1.0'
__contact__ = ''



#########################
## Logger Function
##

def log_trace(message, exception=None):
    """Log trace level messages (for exception tracebacks). Only shown when debug is enabled."""
    global debug
    if debug:
        if exception:
            print(f'[TRACE] {message}')
            traceback.print_exception(type(exception), exception, exception.__traceback__)
        else:
            print(f'[TRACE] {message}')

def log_debug(message):
    """Log debug level messages. Only shown when debug is enabled."""
    global debug
    if debug:
        print(f'[DEBUG] {message}')

def log_info(message):
    """Log info level messages. Always shown."""
    print(f'[INFO] {message}')

def log_warning(message):
    """Log warning level messages. Always shown."""
    print(f'[WARNING] {message}')

def log_error(message, exception=None):
    """Log error level messages. Always shown. Can include exception traceback."""
    if exception:
        print(f'[ERROR] {message}')
        traceback.print_exception(type(exception), exception, exception.__traceback__)
    else:
        print(f'[ERROR] {message}')

#########################
## Globals Variables
##

imageExtenstions = [ 'gif', 'png', 'jpeg', 'jpg' ]
videoExtensions = [ 'mp4', 'mov', 'avi', 'webm', 'mkv', 'flv', 'wmv', 'm4v' ]

mattermostURL = ''
headers = {}
baseUserPath = ''
debug = False  # Debug logging flag

users = {}
channelCache = {}
emojiIdCache = {}  # Cache for emoji name -> emoji ID mapping


channelDisplayName = ''
messageHeader = None
tableOfContents = {}



#########################
## Exception Definitions
##

class OptionsException( Exception ):
    def __init__(self, message = None ):
        super(OptionsException,self).__init__(message)

class UserInfoException( Exception ):
    def __init__(self, message = None ):
        super(UserInfoException,self).__init__(message)

class UserIDException( Exception ):
    def __init__(self, message = None ):
        super(UserIDException,self).__init__(message)

class TeamIDException( Exception ):
    def __init__(self, message = None ):
        super(TeamIDException,self).__init__(message)

class UserChannelsException( Exception ):
    def __init__(self, message = None ):
        super(UserChannelsException,self).__init__(message)

class ImageException( Exception ):
    def __init__(self, message = None ):
        super(ImageException,self).__init__(message)

class FileException( Exception ):
    def __init__(self, message = None ):
        super(FileException,self).__init__(message)

class ChannelPostsException( Exception ):
    def __init__(self, message = None ):
        super(ChannelPostsException,self).__init__(message)

class ChannelMembersException( Exception ):
    def __init__(self, message = None ):
        super(ChannelMembersException,self).__init__(message)


#########################
## MMExport2PDF Options
##

def processOptions():
    '''
    Process command line arguments and set the internal options appropriately.

            @param argv List of command line arguments.
            @return The object containing the processed options.
    '''
    # process options

    options = None

    try:
        usage = f'%(prog)s [options]'
        description = '%(prog)s is used to export all a users channels and DMs from a team.'
        epilog = 'This can take a long time to run.'

        parser = argparse.ArgumentParser(usage=usage,
                                         description=description,
                                         epilog=epilog,
                                         formatter_class=argparse.ArgumentDefaultsHelpFormatter)

        usergroup = parser.add_argument_group(title='User Info')
        usergroup.add_argument("-a", "--auth", help="Auth Token", action="store", dest="auth", required=True)
        usergroup.add_argument("-u", "--user", help="Username for authentication and channel access (exports ALL messages from accessible channels, not just messages from this user)", action="store", dest="user", required=True)
        usergroup.add_argument("-t", "--team", help="Team to export from", action="store", dest="team", required=True)

        servergroup = parser.add_argument_group(title='Server Info')
        servergroup.add_argument("-s", "--server", help="Hostname or IP of the server", action="store", dest="server", default="mattermost.com")
        servergroup.add_argument("--protocol", help="Protocol to use (http or https)", action="store", dest="protocol", choices=['http', 'https'], default='https')
        servergroup.add_argument("--port", help="Port number (default: 443 for https, 80 for http)", action="store", dest="port", type=int, default=None)

        categorygroup = parser.add_argument_group(title='Channel Categories')
        categorygroup.add_argument("-p", "--public", help="Exclude public channels", action="store_true", dest="public")
        categorygroup.add_argument("-P", "--private", help="Exclude private channels", action="store_true", dest="private")
        categorygroup.add_argument("-g", "--groups", help="Exclude group messages", action="store_true", dest="group")
        categorygroup.add_argument("-d", "--DMs", help="Exclude direct messages", action="store_true", dest="dms")

        filtergroup = parser.add_argument_group(title='Message Filters')
        filtergroup.add_argument("-c", "--channel", help="Export only a single channel (by channel name or display name)", action="store", dest="channel", default=None)
        filtergroup.add_argument("-I", "--include", help="Only inlcude these channels in the export.", nargs='*', dest="include", default=[])
        filtergroup.add_argument("-E", "--exclude", help="Exclude these channels from the export", nargs='*', dest="exclude", default=[])
        filtergroup.add_argument("--start-date", help="Start date for message export (YYYY-MM-DD format). If not specified, exports from beginning.", action="store", dest="start_date", default=None)
        filtergroup.add_argument("--end-date", help="End date for message export (YYYY-MM-DD format). If not specified, exports to present.", action="store", dest="end_date", default=None)

        exportgroup = parser.add_argument_group(title='Export Options')
        exportgroup.add_argument("-j", "--json", help="Export JSON", action="store_true", dest="json")
        exportgroup.add_argument("-o", "--output", help="Base output directory", action="store", dest="output", default='./users')
        exportgroup.add_argument("-v", "--verbose", help="Enable debug logging", action="store_true", dest="verbose", default=False)
        exportgroup.add_argument("--reactions", help="Include reactions in export (default: exclude)", action="store_true", dest="include_reactions", default=False)
        exportgroup.add_argument("--dark-mode", help="Use dark mode for exports (dark blue background)", action="store_true", dest="dark_mode", default=False)

        options = parser.parse_args() # uses sys.argv[1:] by default

        # Set global debug flag
        global debug
        debug = options.verbose

        # Validate date formats if provided
        if options.start_date:
            try:
                datetime.datetime.strptime(options.start_date, '%Y-%m-%d')
            except ValueError:
                raise OptionsException('Start date must be in YYYY-MM-DD format')
        
        if options.end_date:
            try:
                datetime.datetime.strptime(options.end_date, '%Y-%m-%d')
            except ValueError:
                raise OptionsException('End date must be in YYYY-MM-DD format')
        
        # Validate that channel and include/exclude don't conflict
        if options.channel and (options.include or options.exclude):
            raise OptionsException('Cannot use --channel with --include or --exclude options')

    except Exception as e: #pylint: disable=broad-except
        raise OptionsException( e )

    return options


#########################
## Main
##

def main():

    try:
        global baseUserPath
        global mattermostURL
        global headers

        options = processOptions()

        if (options.public and options.private and options.group and options.dms):
            raise OptionsException( 'At least one channel category must be exported' )

        # Setup URL with protocol and optional port
        port_suffix = ''
        if options.port:
            # User specified a port, always use it
            port_suffix = f':{options.port}'
        else:
            # No port specified, use defaults but don't include in URL for standard ports
            if options.protocol == 'http':
                # Default HTTP port 80, don't include in URL
                pass
            elif options.protocol == 'https':
                # Default HTTPS port 443, don't include in URL
                pass
        
        mattermostURL = f'{options.protocol}://{options.server}{port_suffix}/api/v4/'
        headers['Authorization'] = f'Bearer {options.auth}'

        userInfo = getUserFromName(options.user)
        teamInfo = getTeam(options.team)

        baseUserPath = os.path.join( options.output, options.user )
        baseUserFilePath = os.path.join( baseUserPath, 'files/' )
        baseUserAvatarsPath = os.path.join( baseUserPath, 'avatars/' )
        baseUserEmojisPath = os.path.join( baseUserPath, 'emojis/' )

        os.makedirs( baseUserPath, 0o755, True)
        os.makedirs( baseUserAvatarsPath, 0o755, True)
        os.makedirs( baseUserEmojisPath, 0o755, True)

        # Start Working
        allChannelsForUser = getChannelsForAUser(userInfo['id'], teamInfo['id'])
        allChannelsForUser.reverse()


        hitPublicChannel = False
        hitPrivateChannel = False
        hitDMChannel = False
        hitGroupMessages = False

        # Initialize HTML
        html_content = []
        html_content.append('<!DOCTYPE html>')
        html_content.append('<html><head>')
        html_content.append('<meta charset="UTF-8">')
        html_content.append('<title>Mattermost Export - ' + handleUnicode(options.user) + '</title>')
        html_content.append('<style>')
        # Dark mode support - darker blue colors
        bg_color = '#0d1b2a' if options.dark_mode else '#f5f5f5'
        text_color = '#ffffff' if options.dark_mode else '#000000'
        message_bg = '#1b263b' if options.dark_mode else '#ffffff'
        header_bg = '#415a77' if options.dark_mode else '#e0e0e0'
        border_color = '#778da9' if options.dark_mode else '#cccccc'
        pinned_color = '#3d2a64' if options.dark_mode else '#fff8e1'
        pinned_border_color = '#7d5fb8' if options.dark_mode else '#ffa500'
        pinned_header_bg = '#5A4A85' if options.dark_mode else '#D98D09'
        
        html_content.append(f'body {{ font-family: Arial, sans-serif; margin: 20px; background: {bg_color}; color: {text_color}; }}')
        html_content.append('.channel-group { margin-bottom: 30px; }')
        html_content.append(f'.channel-name {{ font-size: 24px; font-weight: bold; margin: 20px 0 10px 0; border-bottom: 2px solid {border_color}; padding-bottom: 5px; }}')
        html_content.append(f'.message {{ background: {message_bg}; margin: 10px 0; padding: 10px; border-left: 3px solid {border_color}; }}')
        html_content.append(f'.message.pinned {{ border-left-color: {pinned_border_color}; background: {pinned_color}; }}')
        html_content.append(f'.message-header.pinned {{ background: {pinned_header_bg}; }}')
        html_content.append(f'.message-header {{ background: {header_bg}; padding: 5px; margin-bottom: 5px; }}')
        html_content.append('.avatar { width: 32px; height: 32px; border-radius: 50%; vertical-align: middle; margin-right: 5px; }')
        html_content.append('.reply-context { font-size: 12px; color: #999; margin: 5px 0; padding-left: 10px; }')
        html_content.append('.message-text { margin: 5px 0; }')
        html_content.append('.file-attachment { margin: 5px 0; padding: 5px; }')
        html_content.append('.reaction { font-size: 12px; color: #666; margin: 3px 0; padding-left: 15px; }')
        html_content.append('.reaction img { width: 16px; height: 16px; vertical-align: middle; margin-right: 3px; }')
        html_content.append('a { color: #6BA3D8; text-decoration: underline; }')  # Lighter blue for links
        html_content.append('a:hover { color: #4A8BC2; }')  # Slightly darker on hover
        html_content.append('a:visited { color: #8BB5E8; }')  # Lighter for visited links
        # Inline code styling - grey-ish background
        if options.dark_mode:
            html_content.append('code { background: #2d3748; color: #e2e8f0; padding: 2px 4px; border-radius: 3px; font-family: "Courier New", Courier, monospace; }')
        else:
            html_content.append('code { background: #f4f4f4; color: #333; padding: 2px 4px; border-radius: 3px; font-family: "Courier New", Courier, monospace; }')
        # Code block styling - dark-green color block
        if options.dark_mode:
            html_content.append('pre { background: #1a4d3a; color: #e2e8f0; padding: 10px; border-radius: 5px; overflow-x: auto; margin: 10px 0; border-left: 4px solid #002935; }')
            html_content.append('pre code { background: transparent; color: inherit; padding: 0; border-radius: 0; }')
        else:
            html_content.append('pre { background: #1a4d3a; color: #e2e8f0; padding: 10px; border-radius: 5px; overflow-x: auto; margin: 10px 0; border-left: 4px solid #002935; }')
            html_content.append('pre code { background: transparent; color: inherit; padding: 0; border-radius: 0; }')
        html_content.append('</style>')
        html_content.append('</head><body>')

        publicChannels = []
        privateChannels = []
        groupChannels = []
        directMessageChannels = []

        channelGroupingsList = []
        
        # If single channel is specified, filter to only that channel
        if options.channel:
            channel_found = False
            for channel in allChannelsForUser:
                # Match by display_name or name
                if channel["display_name"] == options.channel or channel["name"] == options.channel:
                    # Determine channel type and add to appropriate list
                    if channel["type"] == 'O':
                        publicChannels.append(channel)
                    elif channel["type"] == 'P':
                        privateChannels.append(channel)
                    elif channel["type"] == 'D':
                        directMessageChannels.append(channel)
                    elif channel["type"] == 'G':
                        groupChannels.append(channel)
                    channel_found = True
                    break
            
            if not channel_found:
                raise OptionsException(f'Channel "{options.channel}" not found. Available channels can be listed by running without --channel option.')
        else:
            # Original logic for multiple channels
            for channel in allChannelsForUser:            
                if ( channel["display_name"] not in options.exclude):
                    if ( (not options.include) or (channel["display_name"] in options.include) ):
                        if ((not options.public) and channel["type"] == 'O'):
                            publicChannels.append(channel)

                        if ((not options.private) and channel["type"] == 'P'):
                            privateChannels.append(channel)

                        if ((not options.dms) and channel["type"] == 'D'):
                            directMessageChannels.append(channel)

                        if ((not options.group) and channel["type"] == 'G'):
                            groupChannels.append(channel)

        # Pre-process names in direct messages so we can sort by the other user's name
        for channel in directMessageChannels:
            channel['full_name'] = directMessageOtherUserName(channel, userInfo['id'])

        # Sort alphabetical

        publicChannels = sorted(publicChannels, key = lambda i: (i['name']))
        privateChannels = sorted(privateChannels, key = lambda i: (i['name']))
        groupChannels = sorted(groupChannels, key = lambda i: (i['name']))
        directMessageChannels = sorted(directMessageChannels, key = lambda i: (i['full_name']))

        channelGroupingsList = publicChannels + privateChannels + groupChannels + directMessageChannels
        
        if not channelGroupingsList:
            raise ChannelPostsException( "No posts matched the export criteria" )
        
        for channel in channelGroupingsList:

            messagesArray = []
            pinnedMessages = []

            # Setup Channel Name and Headers for printing
            setupChannelNameAndHeader(channel, userInfo['id'])

            if (channel["type"] == 'O' and hitPublicChannel == False):
                html_content.append('<div class="channel-group"><h1 class="channel-name">PUBLIC CHANNELS</h1>')
                hitPublicChannel = True

            if (channel["type"] == 'P' and hitPrivateChannel == False):
                html_content.append('<div class="channel-group"><h1 class="channel-name">PRIVATE CHANNELS</h1>')
                hitPrivateChannel = True

            if (channel["type"] == 'D' and hitDMChannel == False):
                html_content.append('<div class="channel-group"><h1 class="channel-name">DIRECT MESSAGE CHANNELS</h1>')
                hitDMChannel = True

            if (channel["type"] == 'G' and hitGroupMessages == False):
                html_content.append('<div class="channel-group"><h1 class="channel-name">GROUP MESSAGE CHANNELS</h1>')
                hitGroupMessages = True

            log_info(channelDisplayName)
            html_content.append(f'<h2 class="channel-name">{html.escape(channelDisplayName)}</h2>')
            # pdf.set_link(tableOfContents[channel["display_name"]])
            # pdf.multi_cell(0, 5, messageHeader, 0, 'L', True)
            # pdf.ln()

            channelId = channel["id"]
            
            # Create channel-specific folder for files and videos (for privacy/zipping)
            # Sanitize channel name for use as folder name
            safe_channel_name = re.sub(r'[<>:"/\\|?*]', '_', channelDisplayName)
            safe_channel_name = safe_channel_name.strip('. ')
            if not safe_channel_name:
                safe_channel_name = f"channel_{channelId[:8]}"
            channelFolderPath = os.path.join(baseUserPath, safe_channel_name)
            os.makedirs(channelFolderPath, 0o755, True)
            log_info(f'Created channel folder: {channelFolderPath}')

            morePages = True
            channelPostsCounter = 0
            allPosts = []
            allPostsFull = []
            # Get all pages and append messages to one array.
            # We reverse this array before processing so order is from older to newest when printing

            while (morePages):

                allPostsForChannel = getPostsForChannel(channelId, channelPostsCounter)

                postFiles = []

                if not allPostsForChannel["posts"]:
                    morePages = False

                channelPostsCounter += 1

                for key in allPostsForChannel["order"]:
                    allPosts.append(allPostsForChannel["posts"][key])

                allPostsFull.append(allPostsForChannel)

            # CACHE CHANNEL HERE
            channelCache[channelId] = {
                "channelName": channelDisplayName,
                "posts": allPostsFull
            }

            # Reverse so it prints oldest to newest
            allPosts.reverse()

            # Filter posts by date range if specified
            if options.start_date or options.end_date:
                filteredPosts = []
                start_timestamp = None
                end_timestamp = None
                
                if options.start_date:
                    # Parse date and interpret as UTC (Mattermost uses UTC)
                    start_dt = datetime.datetime.strptime(options.start_date, '%Y-%m-%d')
                    # Convert to UTC timestamp (treating input date as UTC)
                    # Use timezone.utc if available, otherwise calculate UTC offset
                    try:
                        start_dt = start_dt.replace(tzinfo=datetime.timezone.utc)
                        start_timestamp = int(start_dt.timestamp() * 1000)
                    except AttributeError:
                        # Fallback for older Python: use calendar module for UTC conversion
                        import calendar
                        start_timestamp = int(calendar.timegm(start_dt.timetuple()) * 1000)
                
                if options.end_date:
                    # Parse date and interpret as UTC (Mattermost uses UTC)
                    end_dt = datetime.datetime.strptime(options.end_date, '%Y-%m-%d')
                    # Add one day to include the entire end date
                    end_dt = end_dt + datetime.timedelta(days=1)
                    # Convert to UTC timestamp
                    try:
                        end_dt = end_dt.replace(tzinfo=datetime.timezone.utc)
                        end_timestamp = int(end_dt.timestamp() * 1000)
                    except AttributeError:
                        # Fallback for older Python: use calendar module for UTC conversion
                        import calendar
                        end_timestamp = int(calendar.timegm(end_dt.timetuple()) * 1000)
                
                for post in allPosts:
                    post_timestamp = post.get("create_at", 0)
                    include_post = True
                    
                    if start_timestamp and post_timestamp < start_timestamp:
                        include_post = False
                    
                    if end_timestamp and post_timestamp >= end_timestamp:
                        include_post = False
                    
                    if include_post:
                        filteredPosts.append(post)
                
                allPosts = filteredPosts
                log_info(f'Filtered to {len(allPosts)} messages in date range')

            # BEGIN POST PROCESSING
            # Loop over posts for channel
            for post in allPosts:
                pictures = []
                videos = []
                files = []

                message = post["message"]
                if (isinstance(message, str)):
                    postUserId = post["user_id"]

                    theUser = getUser(postUserId)

                    # Files
                    if "metadata" in post and "files" in post["metadata"]:
                        postFiles = post["metadata"]["files"]

                        if len(postFiles) > 0:
                            for file in postFiles:
                                # file["extension"] == "gif"
                                if file["extension"].lower() in imageExtenstions:
                                    pictures.append(file)
                                elif file["extension"].lower() in videoExtensions:
                                    videos.append(file)
                                else:
                                    files.append(file)
                    
                    # Reactions
                    reactions = []
                    if "metadata" in post and "reactions" in post["metadata"]:
                        reactions = post["metadata"]["reactions"]

                    # Check if this is a reply/thread
                    root_id = post.get("root_id", "")
                    parent_id = post.get("parent_id", "")
                    is_reply = bool(root_id) or bool(parent_id)
                    
                    # Get parent message info if this is a reply
                    parent_message_info = None
                    if is_reply:
                        # Try to get parent message from allPostsFull
                        parent_post_id = root_id if root_id else parent_id
                        for posts_batch in allPostsFull:
                            if "posts" in posts_batch and parent_post_id in posts_batch["posts"]:
                                parent_post = posts_batch["posts"][parent_post_id]
                                parent_user_id = parent_post.get("user_id", "")
                                parent_message_text = parent_post.get("message", "")
                                parent_time = parent_post.get("create_at", 0)
                                
                                if parent_user_id:
                                    try:
                                        parent_user = getUser(parent_user_id)
                                        parent_name = f"{parent_user.get('first_name', '')} {parent_user.get('last_name', '')}".strip()
                                        if not parent_name:
                                            parent_name = parent_user.get('username', parent_user_id)
                                        
                                        # Get preview of parent message (first 50 chars)
                                        parent_preview = parent_message_text[:50] + "..." if len(parent_message_text) > 50 else parent_message_text
                                        parent_date = datetime.datetime.fromtimestamp(parent_time / 1000).strftime("%d/%m/%Y, %H:%M:%S")
                                        
                                        parent_message_info = {
                                            "name": parent_name,
                                            "preview": parent_preview,
                                            "date": parent_date,
                                            "post_id": parent_post_id  # Add post ID for anchor link
                                        }
                                    except:
                                        pass
                                break
                    
                    # Get user name - fall back to username if first/last name is empty
                    user_name = f"{theUser.get('first_name', '')} {theUser.get('last_name', '')}".strip()
                    if not user_name:
                        user_name = theUser.get('username', postUserId)
                    
                    postWithUserName = {
                        "name": user_name,
                        "user_id": postUserId,
                        "message": message,
                        "time": str(datetime.datetime.fromtimestamp(post["create_at"] / 1000).strftime("%d/%m/%Y, %H:%M:%S")),
                        "pictures": pictures,
                        "videos": videos,
                        "files": files,
                        "reactions": reactions,
                        "post": post,
                        "post_id": post.get("id", ""),  # Add post ID for anchors
                        "root_id": root_id,
                        "parent_id": parent_id,
                        "is_reply": is_reply,
                        "parent_message_info": parent_message_info
                    }

                    if post["is_pinned"] == True:
                        pinnedMessages.append(postWithUserName)

                    messagesArray.append(postWithUserName)

            log_info(f'Total Messages: {len(messagesArray) + 1}')
            log_info('')

            # Collect all custom emoji names from messages and reactions
            allEmojiNames = set()
            # Pattern to match custom emoji text - exclude time patterns like :29:
            # Emoji names must start with letter or +, not just digits
            # Pattern to match emoji names:
            # - Starts with letter or underscore: [a-zA-Z_][a-zA-Z0-9_+-]*
            # - Starts with + followed by digits: \+[0-9]+
            # - Starts with 3 or more digits: [0-9]{3,}
            # This allows :100: but not :29: or :3:
            emoji_pattern = re.compile(r':([a-zA-Z_][a-zA-Z0-9_+-]*|\+[0-9]+|[0-9]{3,}):')
            
            for message in messagesArray + pinnedMessages:
                # Extract emojis from message text
                messageText = message.get("message", "")
                for match in emoji_pattern.finditer(messageText):
                    allEmojiNames.add(match.group(1))
                
                # Extract emojis from reactions
                reactions = message.get("reactions", [])
                for reaction in reactions:
                    emoji = reaction.get("emoji_name", "")
                    if emoji:
                        allEmojiNames.add(emoji)
            
            # Batch fetch all custom emoji IDs
            if allEmojiNames:
                log_debug(f'Collecting {len(allEmojiNames)} unique custom emoji names')
                batchFetchEmojiIds(list(allEmojiNames), baseUserEmojisPath)
            
            # Pre-download avatars for all unique users
            uniqueUserIDs = set()
            for message in messagesArray + pinnedMessages:
                userID = message.get("user_id", "")
                if userID:
                    uniqueUserIDs.add(userID)
            
            log_debug(f'Pre-downloading avatars for {len(uniqueUserIDs)} unique users')
            
            for userID in uniqueUserIDs:
                avatarFilePath = os.path.join(baseUserAvatarsPath, f'{userID}')
                getUserAvatar(userID, avatarFilePath)
            
            # Get global emojiIdCache for HTML export
            global emojiIdCache
            
            if len(pinnedMessages) > 0:
                html_content.append('<h3>Pinned Messages</h3>')

            # Loop through Pinned messages first, to put them all at the front
            # Download files/videos/images for pinned messages BEFORE rendering
            for message in pinnedMessages:
                # Download images for pinned messages
                try:
                    userPicturesFilePath = os.path.join( baseUserPath, "pics/" )
                    os.makedirs( userPicturesFilePath, 0o755, True)

                    for picture in message.get("pictures", []):
                        try:
                            imagePath = os.path.join( userPicturesFilePath,  f'{picture["id"]}_{picture["name"]}' )
                            myImage = Path(imagePath)

                            if not myImage.exists():
                                imageObj = getFile( picture["id"] )

                                with open(imagePath, 'wb') as f:
                                    imageObj.raw.decode_content = True
                                    shutil.copyfileobj(imageObj.raw, f)

                        except ImageException as ie:
                            log_error(f'Download Image error: {ie}', exception=ie)
                        except Exception as e:
                            log_error('Download Image error: Couldn\'t download picture', exception=e)

                except ImageException as ie:
                    log_error(str(ie), exception=ie)
                
                # Download videos for pinned messages
                videos_list = message.get("videos", [])
                if videos_list:
                    log_info(f'Found {len(videos_list)} video(s) in attachments')
                try:
                    userVideosFilePath = os.path.join( channelFolderPath, "videos" )
                    os.makedirs( userVideosFilePath, 0o755, True)

                    for video in videos_list:
                        try:
                            video_name = video.get("name", "unknown")
                            videoPath = os.path.join( userVideosFilePath,  f'{video["id"]}_{video_name}' )
                            myVideo = Path(videoPath)

                            if not myVideo.exists():
                                log_info(f'Downloading video: {video_name}')
                                videoObj = getFile( video["id"] )

                                with open(videoPath, 'wb') as f:
                                    videoObj.raw.decode_content = True
                                    shutil.copyfileobj(videoObj.raw, f)
                                log_info(f'Video downloaded successfully: {video_name}')
                            else:
                                log_info(f'Video found in cache: {video_name}')

                        except Exception as e:
                            log_error(f'Error downloading video {video.get("name", "unknown")}: {e}', exception=e)

                except Exception as e:
                    log_error(f'Error processing videos: {e}', exception=e)
                
                # Download files for pinned messages
                files_list = message.get("files", [])
                if files_list:
                    log_info(f'Found {len(files_list)} file(s) in attachments')
                try:
                    userFilesPath = os.path.join( channelFolderPath, "files" )
                    os.makedirs( userFilesPath, 0o755, True)

                    for file in files_list:
                        try:
                            file_name = file.get("name", "unknown")
                            filePath = os.path.join( userFilesPath,  f'{file["id"]}_{file_name}' )
                            myFile = Path(filePath)

                            if not myFile.exists():
                                log_info(f'Downloading file: {file_name}')
                                fileObj = getFile( file["id"] )

                                with open(filePath, 'wb') as f:
                                    fileObj.raw.decode_content = True
                                    shutil.copyfileobj(fileObj.raw, f)
                                log_info(f'File downloaded successfully: {file_name}')
                            else:
                                log_info(f'File found in cache: {file_name}')

                        except FileException as fe:
                            log_error(f'Error downloading file {file.get("name", "unknown")}: {fe}', exception=fe)
                        except Exception as e:
                            log_error(f'Error downloading file {file.get("name", "unknown")}: {e}', exception=e)

                except Exception as e:
                    log_error(f'Error processing files: {e}', exception=e)
                
                # NOW render the pinned message after all files/videos/images are downloaded
                isReply = message.get("is_reply", False)
                html_content.append(renderMessageHTML(message, baseUserAvatarsPath, baseUserEmojisPath, emojiIdCache, baseUserFilePath, baseUserPath=baseUserPath, channelFolderPath=channelFolderPath, isPinned=True, isReply=isReply, options=options))

            html_content.append('<h3>Regular Messages</h3>')

            for message in messagesArray:
                post = message["post"]
                isPinned = post.get("is_pinned", False)
                isReply = message.get("is_reply", False)
                
                # Download files and videos BEFORE rendering the message
                # Download images for HTML export
                try:
                    userPicturesFilePath = os.path.join( baseUserPath, "pics/" )
                    os.makedirs( userPicturesFilePath, 0o755, True)

                    for picture in message["pictures"]:
                        try:
                            # APPEND FILE ID TO PATH TO MAKE UNIQUE AND CACHE THIS
                            # Keep original filename with spaces for filesystem
                            imagePath = os.path.join( userPicturesFilePath,  f'{picture["id"]}_{picture["name"]}' )
                            myImage = Path(imagePath)

                            if not myImage.exists():
                                imageObj = getFile( picture["id"] )

                                with open(imagePath, 'wb') as f:
                                    imageObj.raw.decode_content = True
                                    shutil.copyfileobj(imageObj.raw, f)

                        except ImageException as ie:
                            log_error(f'Download Image error: {ie}', exception=ie)
                        except Exception as e:
                            log_error('Download Image error: Couldn\'t download picture', exception=e)

                except ImageException as ie:
                    log_error(str(ie), exception=ie)
                
                # Download videos for HTML export
                videos_list = message.get("videos", [])
                if videos_list:
                    log_info(f'Found {len(videos_list)} video(s) in attachments')
                try:
                    userVideosFilePath = os.path.join( channelFolderPath, "videos" )
                    os.makedirs( userVideosFilePath, 0o755, True)

                    for video in videos_list:
                        try:
                            video_name = video.get("name", "unknown")
                            # Keep original filename with spaces for filesystem
                            videoPath = os.path.join( userVideosFilePath,  f'{video["id"]}_{video_name}' )
                            myVideo = Path(videoPath)

                            if not myVideo.exists():
                                log_info(f'Downloading video: {video_name}')
                                videoObj = getFile( video["id"] )

                                with open(videoPath, 'wb') as f:
                                    videoObj.raw.decode_content = True
                                    shutil.copyfileobj(videoObj.raw, f)
                                log_info(f'Video downloaded successfully: {video_name}')
                            else:
                                log_info(f'Video found in cache: {video_name}')

                        except Exception as e:
                            log_error(f'Error downloading video {video.get("name", "unknown")}: {e}', exception=e)

                except Exception as e:
                    log_error(f'Error processing videos: {e}', exception=e)
                
                # Download files (non-image, non-video attachments) for HTML export
                files_list = message.get("files", [])
                if files_list:
                    log_info(f'Found {len(files_list)} file(s) in attachments')
                try:
                    userFilesPath = os.path.join( channelFolderPath, "files" )
                    os.makedirs( userFilesPath, 0o755, True)

                    for file in files_list:
                        try:
                            file_name = file.get("name", "unknown")
                            # Keep original filename with spaces for filesystem
                            filePath = os.path.join( userFilesPath,  f'{file["id"]}_{file_name}' )
                            myFile = Path(filePath)

                            if not myFile.exists():
                                log_info(f'Downloading file: {file_name}')
                                fileObj = getFile( file["id"] )

                                with open(filePath, 'wb') as f:
                                    fileObj.raw.decode_content = True
                                    shutil.copyfileobj(fileObj.raw, f)
                                log_info(f'File downloaded successfully: {file_name}')
                            else:
                                log_info(f'File found in cache: {file_name}')

                        except FileException as fe:
                            log_error(f'Error downloading file {file.get("name", "unknown")}: {fe}', exception=fe)
                        except Exception as e:
                            log_error(f'Error downloading file {file.get("name", "unknown")}: {e}', exception=e)

                except Exception as e:
                    log_error(f'Error processing files: {e}', exception=e)
                
                # NOW render the message after all files/videos/images are downloaded
                html_content.append(renderMessageHTML(message, baseUserAvatarsPath, baseUserEmojisPath, emojiIdCache, baseUserFilePath, baseUserPath=baseUserPath, channelFolderPath=channelFolderPath, isPinned=isPinned, isReply=isReply, options=options))

        # Determine output filename - use channel name if -c option is passed, otherwise use user name
        if options.channel and channelGroupingsList:
            # Get the channel name from the first (and only) channel when -c is used
            export_channel = channelGroupingsList[0]
            # Use the processed channelDisplayName if available (handles DMs and group messages),
            # otherwise use display_name or name
            if channelDisplayName:
                channel_name = channelDisplayName
            else:
                channel_name = export_channel.get("display_name") or export_channel.get("name", options.channel)
            # Sanitize channel name for use as filename (remove invalid characters)
            sanitized_name = re.sub(r'[<>:"/\\|?*]', '_', channel_name)
            output_basename = sanitized_name
        else:
            output_basename = options.user
        
        # Output HTML
        html_content.append('</body></html>')
        htmlOutput = os.path.join(baseUserPath, f'{output_basename}.html' )
        with open(htmlOutput, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html_content))
        log_info(htmlOutput)
        log_info('')

        if( options.json ):
            makeJsonFile(options.user)

    except Exception as e:
        log_error(str(e), exception=e)
        #traceback.print_exc()



#########################
## Helper Functions
##

def getUser(userID):
    '''
    getUser

    Returns the user info for the given ID.

        @param userID The user ID to look up

    :raises:
        UserInfoException
    '''
    if userID not in users:
        getUserResponse = requests.get(f'{mattermostURL}/users/{userID}',
                                       headers=headers)

        if (getUserResponse.status_code != 200):
            raise UserInfoException(f'Failed to get user info for: {userID}')

        users[userID] = getUserResponse.json()

    return users[userID]


def getUserFromName(username):
    '''
    getUserFromName

    Retrieves the user info for the username.

        @param username the username to look up.

    :raises:
        UserIDException
    '''
    getUserIDResponse = requests.get(f'{mattermostURL}/users/username/{username}',
                                     headers=headers)

    if (getUserIDResponse.status_code != 200):
      raise UserIDException(f'Failed to get user ID for: {username}')

    return getUserIDResponse.json()


def getAllTeamsForUser(userID):
    '''
    getAllTeamsForUser

    Returns all teams that the user is a member of.

        @param userID The user ID to look up teams for.

    :returns:
        List of teams
    '''
    allTeams = []
    page = 0
    perPage = 200
    
    while True:
        getTeamsResponse = requests.get(f'{mattermostURL}/users/{userID}/teams',
                                       headers=headers,
                                       params={'page': page, 'per_page': perPage})
        
        if getTeamsResponse.status_code != 200:
            break
        
        teams = getTeamsResponse.json()
        if not teams:
            break
        
        allTeams.extend(teams)
        
        # If we got fewer teams than requested, we've reached the end
        if len(teams) < perPage:
            break
        
        page += 1
    
    return allTeams


def getTeam(team):
    '''
    getTeadID

    Returns the ID for the team.

        @param team the team name to look up.

    :raises:
        TeamIDException
    '''

    getTeamIDResponse = requests.get(f'{mattermostURL}/teams/name/{team}',
                                     headers=headers)

    if (getTeamIDResponse.status_code != 200):
        # Try to get available teams to show in error message
        error_message = f'Failed to get team ID for: "{team}"\n'
        try:
            # Get current user info from the auth token to list their teams
            getMeResponse = requests.get(f'{mattermostURL}/users/me', headers=headers)
            if getMeResponse.status_code == 200:
                currentUser = getMeResponse.json()
                availableTeams = getAllTeamsForUser(currentUser['id'])
                if availableTeams:
                    error_message += '\nAvailable teams for this user:\n'
                    for t in availableTeams:
                        # Show both display_name and name (which is used in the API)
                        team_display = t.get("display_name", t.get("name", "Unknown"))
                        team_name = t.get("name", "unknown")
                        error_message += f'  - "{team_display}" (use --team "{team_name}")\n'
                    error_message += '\nNote: Use the team "name" (not display_name) with the --team parameter.\n'
                else:
                    error_message += '\nNo teams found for this user.\n'
            else:
                error_message += '\nCould not retrieve available teams. Please check your authentication.\n'
        except Exception as e:
            error_message += f'\nCould not retrieve available teams: {str(e)}\n'
        
        raise TeamIDException(error_message)

    return getTeamIDResponse.json()


def getFile(fileID):
    '''
    getFile

    Retrieves an attachement file from the server.

        @param fileID the attachment ID/

    :raises:
        FileException
    '''

    getFileResponse = requests.get(f'{mattermostURL}/files/{fileID}',
                                   headers=headers,
                                   stream=True)

    if (getFileResponse.status_code != 200):
      raise FileException(f'Failed to get file[{fileID}], status code: {getFileResponse.status_code}')

    return getFileResponse


def batchFetchEmojiIds(emojiNames, baseUserEmojisPath):
    '''
    batchFetchEmojiIds
    
    Batch fetches emoji IDs for all custom emojis and downloads their images.
    
        @param emojiNames List of emoji names to fetch
        @param baseUserEmojisPath Path to emojis directory
    '''
    global debug, emojiIdCache
    
    if not emojiNames:
        return
    
    try:
        import json
        
        # Filter out emojis that are already cached
        emojisToFetch = [name for name in emojiNames if name not in emojiIdCache]
        
        if not emojisToFetch:
            log_debug(f'All {len(emojiNames)} emojis already cached')
            return
        
        log_debug(f'Batch fetching IDs for {len(emojisToFetch)} custom emojis')
        
        # POST to /api/v4/emoji/names to get all emoji IDs at once
        emojiDataResponse = requests.post(
            f'{mattermostURL}emoji/names',
            headers={**headers, 'Content-Type': 'application/json'},
            data=json.dumps(emojisToFetch)
        )
        
        if emojiDataResponse.status_code == 200:
            emojiDataList = emojiDataResponse.json()
            
            # Build emoji name -> ID mapping
            for emojiData in emojiDataList:
                emojiName = emojiData.get('name', '')
                emojiId = emojiData.get('id', '')
                if emojiName and emojiId:
                    emojiIdCache[emojiName] = emojiId
                    log_debug(f'Cached emoji ID: {emojiName} -> {emojiId}')
            
            # Download all emoji images
            for emojiName, emojiId in emojiIdCache.items():
                if emojiName in emojisToFetch:  # Only download newly fetched emojis
                    emojiFilePath = os.path.join(baseUserEmojisPath, f'{emojiName}')
                    
                    # Check if already exists
                    exists = False
                    for ext in ['png', 'gif', 'jpg', 'jpeg']:
                        if os.path.exists(f'{emojiFilePath}.{ext}'):
                            exists = True
                            break
                    
                    if not exists:
                        # Download the emoji image
                        emojiURL = f'{mattermostURL}emoji/{emojiId}/image'
                        emojiResponse = requests.get(emojiURL, headers=headers, stream=True)
                        
                        if emojiResponse.status_code == 200:
                            content_type = emojiResponse.headers.get('content-type', 'image/png')
                            ext = 'png'
                            if 'gif' in content_type:
                                ext = 'gif'
                            elif 'jpeg' in content_type or 'jpg' in content_type:
                                ext = 'jpg'
                            
                            emojiPathWithExt = f'{emojiFilePath}.{ext}'
                            os.makedirs(os.path.dirname(emojiPathWithExt), 0o755, True)
                            
                            with open(emojiPathWithExt, 'wb') as f:
                                emojiResponse.raw.decode_content = True
                                shutil.copyfileobj(emojiResponse.raw, f)
                            
                            log_debug(f'Downloaded emoji: {emojiName} to {emojiPathWithExt}')
        else:
            log_debug(f'Failed to batch fetch emoji IDs: HTTP {emojiDataResponse.status_code}')
    except Exception as e:
        log_trace(f'Exception in batchFetchEmojiIds: {e}', exception=e)


def processMarkdownForHTML(text):
    """
    Process markdown formatting in text for HTML rendering.
    Handles: ```code blocks```, `inline code`, _italic_, **bold**, [title](url), URLs
    Returns HTML string with markdown processed.
    """
    # Process code blocks first (```...```) - these take precedence
    code_block_pattern = re.compile(r'```([^`]+)```', re.DOTALL)
    
    # Find all code blocks and replace them with placeholders first
    code_blocks = []
    placeholder_map = {}
    placeholder_counter = 0
    
    def replace_code_block_with_placeholder(match):
        nonlocal placeholder_counter
        code_content = match.group(1)
        # Escape HTML and preserve line breaks
        escaped_code = html.escape(code_content)
        placeholder = f'__CODE_BLOCK_{placeholder_counter}__'
        placeholder_map[placeholder] = f'<pre><code>{escaped_code}</code></pre>'
        placeholder_counter += 1
        return placeholder
    
    # Replace code blocks with placeholders
    processed_text = code_block_pattern.sub(replace_code_block_with_placeholder, text)
    
    # Now process inline markdown (only outside code blocks - placeholders won't match)
    # Pattern to match inline code `code` (not inside code blocks)
    inline_code_pattern = re.compile(r'`([^`]+)`')
    # Pattern to match italic _text_ (but not __bold__ or at start/end of word)
    italic_pattern = re.compile(r'(?<![_a-zA-Z0-9])_([^_]+)_(?![_a-zA-Z0-9])')
    # Pattern to match bold **text**
    bold_pattern = re.compile(r'\*\*([^*]+)\*\*')
    
    # Replace inline code
    def replace_inline_code(match):
        code_content = match.group(1)
        escaped_code = html.escape(code_content)
        return f'<code>{escaped_code}</code>'
    
    processed_text = inline_code_pattern.sub(replace_inline_code, processed_text)
    
    # Replace italic
    def replace_italic(match):
        italic_content = match.group(1)
        escaped_italic = html.escape(italic_content)
        return f'<em>{escaped_italic}</em>'
    
    processed_text = italic_pattern.sub(replace_italic, processed_text)
    
    # Replace bold
    def replace_bold(match):
        bold_content = match.group(1)
        escaped_bold = html.escape(bold_content)
        return f'<strong>{escaped_bold}</strong>'
    
    processed_text = bold_pattern.sub(replace_bold, processed_text)
    
    # Process markdown links [title](url) - must be done before URL processing
    # Important: Skip if the URL part already contains HTML tags (means URLs were processed first somehow)
    # Need to handle titles with nested brackets like [[BR-02.246] ...]
    # Use non-greedy match that stops at ]( to handle nested brackets correctly
    def replace_markdown_link_http(match):
        title = match.group(1)
        url = match.group(2)
        # Skip if URL already contains HTML tags (means it was already processed as a URL)
        if '<' in url or '>' in url:
            return match.group(0)  # Return original, don't process
        # Remove angle brackets if present
        url = url.strip('<>')
        # Unescape brackets in title (convert \] to ] and \[ to [)
        title = title.replace('\\]', ']').replace('\\[', '[')
        return f'<a href="{html.escape(url)}" target="_blank">{html.escape(title)}</a>'
    
    # Pattern: [title](url) where title can contain nested brackets like [[BR-02.246] ...]
    # Use non-greedy match (.*?) that stops at ]( - this handles nested brackets correctly
    # The key is matching until we find ]( which indicates end of title and start of URL
    markdown_link_pattern = re.compile(r'\[(.*?)\]\((https?://[^<>)]+)\)', re.IGNORECASE)
    processed_text = markdown_link_pattern.sub(replace_markdown_link_http, processed_text)
    
    # Then match non-URL markdown links (relative paths, etc.) - but skip if already HTML
    def replace_markdown_link_non_url(match):
        title = match.group(1)
        url = match.group(2)
        # Skip if URL already contains HTML tags (already processed)
        if '<' in url or '>' in url:
            return match.group(0)  # Return original, don't process
        url = url.strip('<>')
        # Unescape brackets in title
        title = title.replace('\\]', ']').replace('\\[', '[')
        return f'<a href="{html.escape(url)}" target="_blank">{html.escape(title)}</a>'
    
    # Pattern for non-URL markdown links (but only if not already processed)
    # Match [text](url) where url doesn't start with http and doesn't contain HTML
    # Title can contain nested brackets - use non-greedy match
    non_url_link_pattern = re.compile(r'\[(.*?)\]\(([^<>\s)]+)\)')
    processed_text = non_url_link_pattern.sub(replace_markdown_link_non_url, processed_text)
    
    # Process URLs to make them clickable
    # But skip URLs that are already inside <a> tags from markdown links
    # Also skip URLs that are inside markdown link syntax [text](url)
    def replace_url_if_not_in_link(match):
        url = match.group(1)
        start = match.start()
        end = match.end()
        before = processed_text[:start]
        after = processed_text[end:]
        
        # Check if this URL is already inside an <a> tag
        open_tags = before.count('<a')
        close_tags = before.count('</a>')
        if open_tags > close_tags:
            return url  # Don't wrap, already in a link
        
        # Check if this URL is inside markdown link syntax [text](url)
        # Look backwards for the pattern ]( - this indicates a markdown link
        # Search backwards from the URL start (look back up to 500 chars)
        search_start = max(0, start - 500)
        text_before = processed_text[search_start:start]
        # Find the last occurrence of ]( or ] ( with optional whitespace before this URL
        # This indicates the URL is part of a markdown link
        if re.search(r'\]\s*\([^)]*$', text_before):
            # Found ]( or ] ( - this URL is inside a markdown link, skip it
            return url
        
        return f'<a href="{html.escape(url)}" target="_blank">{html.escape(url)}</a>'
    
    # Pattern to match URLs
    # Use negative lookbehind to skip URLs that come immediately after ](
    url_pattern = re.compile(r'(?<!\]\()(https?://[^\s<>"{}|\\^`\[\]]+)', re.IGNORECASE)
    processed_text = url_pattern.sub(replace_url_if_not_in_link, processed_text)
    
    # Replace placeholders back with actual code blocks
    for placeholder, code_block_html in placeholder_map.items():
        processed_text = processed_text.replace(placeholder, code_block_html)
    
    # The processed_text already contains properly formatted HTML tags
    # We just need to escape any remaining text that's not inside HTML tags
    # and convert newlines to <br> tags (except inside <pre> blocks)
    
    # Split into parts: text and HTML tags
    parts = []
    last_end = 0
    
    # Find all HTML tags - use a more comprehensive pattern
    # Match code blocks first (they can contain newlines)
    tag_pattern = re.compile(
        r'(<pre><code>.*?</code></pre>|'  # Code blocks (multiline)
        r'<a\s+href="[^"]+"\s+target="_blank">[^<]*</a>|'  # Links
        r'<code>[^<]*</code>|'  # Inline code
        r'<strong>[^<]*</strong>|'  # Bold
        r'<em>[^<]*</em>)',  # Italic
        re.DOTALL
    )
    
    for match in tag_pattern.finditer(processed_text):
        # Add text before tag
        if match.start() > last_end:
            text_part = processed_text[last_end:match.start()]
            if text_part:
                parts.append(('text', text_part))
        # Add tag (unescaped)
        parts.append(('tag', match.group(0)))
        last_end = match.end()
    
    # Add remaining text
    if last_end < len(processed_text):
        remaining = processed_text[last_end:]
        if remaining:
            parts.append(('text', remaining))
    
    # If no tags found, just escape the whole text and convert newlines
    if not parts:
        escaped = html.escape(processed_text).replace('\n', '<br>')
        return escaped
    
    # Build final HTML
    result = []
    in_pre_block = False
    
    for part_type, part_content in parts:
        if part_type == 'tag':
            # Check if this is a <pre><code> block
            if '<pre><code>' in part_content:
                in_pre_block = True
            elif '</code></pre>' in part_content:
                in_pre_block = False
            # Keep HTML tags as-is (they're already properly formatted)
            result.append(part_content)
        else:
            # Escape text and convert newlines to <br> (except inside <pre> blocks)
            escaped = html.escape(part_content)
            if not in_pre_block:
                escaped = escaped.replace('\n', '<br>')
            result.append(escaped)
    
    return ''.join(result)


def image_to_data_uri(image_path):
    """
    Convert an image file to a data URI for embedding in HTML.
    
    @param image_path Path to the image file
    @return Data URI string or None if file doesn't exist
    """
    if not image_path or not os.path.exists(image_path):
        return None
    
    try:
        # Determine MIME type from file extension
        ext = os.path.splitext(image_path)[1].lower()
        mime_types = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.webp': 'image/webp'
        }
        mime_type = mime_types.get(ext, 'image/png')
        
        # Read image file and encode as base64
        with open(image_path, 'rb') as f:
            image_data = f.read()
            base64_data = base64.b64encode(image_data).decode('utf-8')
            return f'data:{mime_type};base64,{base64_data}'
    except Exception as e:
        log_error(f'Error converting image to data URI: {e}', exception=e)
        return None


def getUserAvatar(userID, avatarPath):
    '''
    getUserAvatar

    Downloads and caches a user's avatar image.

        @param userID The user ID
        @param avatarPath The path where the avatar should be saved (without extension)
        @return Path to the avatar file, or None if not available
    '''
    global debug
    
    log_debug(f'Getting avatar for userID: {userID}, path: {avatarPath}')
    
    # Check if avatar already exists (try common extensions)
    for ext in ['png', 'jpg', 'jpeg', 'gif']:
        existingPath = f'{avatarPath}.{ext}'
        if os.path.exists(existingPath):
            log_debug(f'Avatar found in cache: {existingPath}')
            return existingPath
    
    log_debug(f'Avatar not in cache, downloading from API...')
    
    try:
        # Download avatar from Mattermost API
        avatarURL = f'{mattermostURL}/users/{userID}/image'
        log_debug(f'Downloading avatar from: {avatarURL}')
        avatarResponse = requests.get(avatarURL, headers=headers, stream=True)
        
        log_debug(f'Avatar API response status: {avatarResponse.status_code}')
        
        if avatarResponse.status_code == 200:
            # Determine file extension from content type or default to png
            content_type = avatarResponse.headers.get('content-type', 'image/png')
            ext = 'png'
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = 'jpg'
            elif 'gif' in content_type:
                ext = 'gif'
            
            log_debug(f'Avatar content-type: {content_type}, using extension: {ext}')
            
            avatarPathWithExt = f'{avatarPath}.{ext}'
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(avatarPathWithExt), 0o755, True)
            
            with open(avatarPathWithExt, 'wb') as f:
                avatarResponse.raw.decode_content = True
                shutil.copyfileobj(avatarResponse.raw, f)
            
            log_debug(f'Avatar downloaded successfully to: {avatarPathWithExt}')
            
            return avatarPathWithExt
        elif avatarResponse.status_code == 404:
            # User has no custom avatar (uses default)
            log_debug(f'Avatar not found (404) for userID: {userID}')
            return None
        else:
            log_debug(f'Avatar download failed with status {avatarResponse.status_code} for userID: {userID}')
            return None
    except Exception as e:
        log_trace(f'Exception while downloading avatar for userID {userID}: {e}', exception=e)
        # Silently fail - avatars are optional
        pass
    
    log_debug(f'Avatar download failed for userID: {userID}')
    return None


def getChannelsForAUser(userID, teamID):
    '''
    getChannelsForAUser

    Get all Channels for a User

        @param userID
        @param teamID

    :raises:
        UserChannelsException
    '''
    allChannelsForUserResponse = requests.get(f'{mattermostURL}/users/{userID}/teams/{teamID}/channels?include_deleted=false&last_delete_at=0',
                                              headers=headers)

    if (allChannelsForUserResponse.status_code != 200):
        raise UserChannelsException('Failed to get channels for user')

    return allChannelsForUserResponse.json()


def getPostsForChannel(channelID, channelPostsCounter):
    '''
    getPostsForChannel

    Get all Posts for a Channels

        @param channelID
        @param channelPostsCounter

    :raises:
        ChannelPostsException
    '''
    getPostsForChannelResponse = requests.get(f'{mattermostURL}channels/{channelID}/posts?page={channelPostsCounter}', headers=headers)

    if (getPostsForChannelResponse.status_code != 200):
        raise ChannelPostsException('Failed to get posts for channels')

    return getPostsForChannelResponse.json()


def setupChannelNameAndHeader(channel, userID):
    global messageHeader
    global channelDisplayName

    channelDisplayName = channel["display_name"]
    # Direct messsages
    # if len(channel["display_name"]) == 0:
    if channel["type"] == 'D':
        nameSplit = channel["name"].split("__")
        firstPerson = getUser(nameSplit[0])
        firstPersonFirstName = firstPerson["first_name"]
        firstPersonLastName = firstPerson["last_name"]
        firstPersonUserId = nameSplit[0]

        secondPerson = getUser(nameSplit[1])
        secondPersonFirstName = secondPerson["first_name"]
        secondPersonLastName = secondPerson["last_name"]
        secondPersonUserId = nameSplit[1]

        if firstPersonUserId == userID:
            otherPersonFirstName = secondPersonFirstName
            otherPersonLastName = secondPersonLastName
        else:
            otherPersonFirstName = firstPersonFirstName
            otherPersonLastName = firstPersonLastName

        messageHeader = 'DM with ' + otherPersonFirstName + ' ' + otherPersonLastName
        channelDisplayName = messageHeader
    else:
        # If MM Group message
        if channel["type"] == 'G':
            # Get Channel Members:
            names = getChannelMembersFn(channel)

            messageHeader = "Group Message between: " + names
            channelDisplayName = messageHeader
        # Public/Private Channels
        else:
            messageHeader = channelDisplayName


def directMessageOtherUserName(channel, userID):
    nameSplit = channel["name"].split("__")
    firstPerson = getUser(nameSplit[0])
    firstPersonFirstName = firstPerson["first_name"]
    firstPersonLastName = firstPerson["last_name"]
    firstPersonUserId = nameSplit[0]

    secondPerson = getUser(nameSplit[1])
    secondPersonFirstName = secondPerson["first_name"]
    secondPersonLastName = secondPerson["last_name"]
    secondPersonUserId = nameSplit[1]

    if firstPersonUserId == userID:
        return secondPersonFirstName + secondPersonLastName
    else:
        return firstPersonFirstName + firstPersonLastName


def getChannelMembersFn(channel):
    channelMembersCounter = 0
    morePages = True
    names = ''
    while(morePages):
        getChannelMembers = f'/channels/{channel["id"]}/members?page={channelMembersCounter}'
        getChannelMembersResponse = requests.get(mattermostURL + getChannelMembers, headers=headers)

        if (getChannelMembersResponse.status_code != 200):
            raise ChannelPostsException("ERROR: Getting all posts for channel")

        channelMembers = getChannelMembersResponse.json()

        channelMembersCounter += 1

        channelMembersLoopCounter = 0
        for member in channelMembers:
            user = getUser(member["user_id"])

            if channelMembersLoopCounter == len(channelMembers) - 1:
                names += 'and ' + user["first_name"] + ' ' + user["last_name"]
            else:
                names += user["first_name"] + ' ' + user["last_name"] + ', '

            channelMembersLoopCounter += 1

        if len(channelMembers) == 0:
            morePages = False
            break
    return names


def process_urls_for_html(text):
    """
    Process text to detect URLs and make them clickable in HTML.
    Returns HTML with URLs wrapped in <a> tags.
    Uses placeholders to avoid escaping issues.
    """
    # Pattern to match URLs (more comprehensive)
    url_pattern = re.compile(r'(https?://[^\s<>"{}|\\^`\[\]]+)', re.IGNORECASE)
    
    # Use unique placeholders that won't conflict with text
    placeholder_map = {}
    placeholder_counter = 0
    
    def replace_url(match):
        nonlocal placeholder_counter
        url = match.group(1)
        placeholder = f'__URL_PLACEHOLDER_{placeholder_counter}__'
        placeholder_map[placeholder] = url
        placeholder_counter += 1
        return placeholder
    
    result = url_pattern.sub(replace_url, text)
    
    # Store placeholder map in a way we can access it later
    # For now, we'll process it immediately
    for placeholder, url in placeholder_map.items():
        # Create the <a> tag with the URL
        link_tag = f'<a href="{html.escape(url)}" target="_blank">{html.escape(url)}</a>'
        result = result.replace(placeholder, link_tag)
    
    return result


def handleUnicode(text):
    '''
    handleUnicode
    
    Returns text as-is since we're using Unicode fonts.
    The old latin-1 encoding was breaking Polish and other Unicode characters.
    
        @param text The text to handle
        @return The text unchanged (Unicode-safe)
    '''
    # With Unicode fonts (NotoSans, DejaVu, etc.), we can handle Unicode directly
    # Just ensure it's a string and return it
    if text is None:
        return ""
    return str(text)


def formatEmojiForDisplay(emojiName):
    '''
    formatEmojiForDisplay
    
    Formats emoji names for display. Custom Mattermost emojis are in format :name:,
    Unicode emojis should already be in the text.
    
        @param emojiName The emoji name or Unicode emoji
        @return Formatted emoji string
    '''
    if not emojiName:
        return ""
    
    # If it's already a Unicode emoji, return as-is
    # Custom Mattermost emojis are in format :name:
    if emojiName.startswith(':') and emojiName.endswith(':'):
        return emojiName  # Keep custom emoji format
    else:
        # Try to format as custom emoji if it's just a name
        return f":{emojiName}:"


def containsEmoji(text):
    '''
    containsEmoji
    
    Checks if text contains Unicode emoji characters.
    
        @param text The text to check
        @return True if text contains emojis
    '''
    if not text:
        return False
    
    # Unicode emoji ranges
    emoji_ranges = [
        (0x1F600, 0x1F64F),  # Emoticons
        (0x1F300, 0x1F5FF),  # Misc Symbols and Pictographs
        (0x1F680, 0x1F6FF),  # Transport and Map
        (0x1F1E0, 0x1F1FF),  # Regional indicators
        (0x2600, 0x26FF),    # Misc symbols
        (0x2700, 0x27BF),   # Dingbats
        (0xFE00, 0xFE0F),   # Variation selectors
        (0x1F900, 0x1F9FF), # Supplemental Symbols and Pictographs
        (0x1FA00, 0x1FA6F), # Chess Symbols
        (0x1FA70, 0x1FAFF), # Symbols and Pictographs Extended-A
    ]
    
    for char in text:
        code_point = ord(char)
        for start, end in emoji_ranges:
            if start <= code_point <= end:
                return True
    
    return False


def emoji_name_to_unicode(name):
    """Convert emoji name to Unicode character"""
    # Standard emoji name to Unicode mapping
    emoji_name_map = {
        'slightly_smiling_face': '🙂',
        'muscle': '💪',
        'heart': '❤',
        'blue_heart': '💙',
        'green_heart': '💚',  # U+1F49A
        'tada': '🎉',
        'pray': '🙏',
        'point_right': '👉',
        'arrow_right': '➡️',
        'christmas_tree': '🎄',
        'sparkles': '✨',
        'gift': '🎁',
        'star2': '🌟',
        'champagne': '🍾',
        'wave': '👋',
        'white_check_mark': '✅',
        'calendar': '📅',
        'raised_hands': '🙌',
        'coffee': '☕',
        'information_source': 'ℹ️',
        'eyes': '👀',
        'snowflake': '❄️',
        'paperclip': '📎',
        'clinking_glasses': '🥂',
        'sports_medal': '🏅',
        'fireworks': '🎆',
        'the_horns': '🤘',
        'ok_hand': '👌',
        'male_genie': '🧞‍♂️',
        'cry': '😢',
        'disappointed_relieved': '😌',
        'skull_and_crossbones': '☠️',
        'eggplant': '🍆',
        'scales': '⚖️',
        'see_no_evil': '🙈',
        'broken_heart': '💔',
        'pleading_face': '🥺',
        'foot_light_skin_tone': '🦶🏻',
        'runner': '🏃',
        'snowman': '⛄️',
        'rocket': '🚀',
        '+1': '👍',
        'thumbsup': '👍',
        'thumbs_up': '👍',
        '100': '💯',
        'joy': '😂',
        'woman-gesturing-ok': '🙆‍♀️',
        'sunglasses': '😎',
        '+1_light_skin_tone': '👍🏻',
    }
    return emoji_name_map.get(name, None)


def unicode_emoji_to_text(char):
    """Convert Unicode emoji to text representation"""
    # Common emoji to text mapping
    emoji_map = {
        '🙂': ':slightly_smiling_face:',
        '💪': ':muscle:',
        '❤': ':heart:',
        '💙': ':blue_heart:',
        '💚': ':green_heart:',
        '🎉': ':tada:',
        '🙏': ':pray:',
        '👉': ':point_right:',
        '🎄': ':christmas_tree:',
        '✨': ':sparkles:',
        '🎁': ':gift:',
        '🌟': ':star2:',
        '🍾': ':champagne:',
        '👋': ':wave:',
        '☑️': ':white_check_mark:',
    }
    
    if char in emoji_map:
        return emoji_map[char]
    
    # For unknown emojis, return a generic representation
    try:
        code_point = ord(char)
        return f'[U+{code_point:04X}]'
    except:
        return '[emoji]'


def is_unicode_emoji_char(char):
    """Check if a character is a Unicode emoji"""
    try:
        code_point = ord(char)
        # Check common emoji ranges
        if (0x1F300 <= code_point <= 0x1F9FF or  # Miscellaneous Symbols and Pictographs
            0x1F600 <= code_point <= 0x1F64F or  # Emoticons
            0x1F900 <= code_point <= 0x1F9FF or  # Supplemental Symbols and Pictographs
            0x2600 <= code_point <= 0x26FF or    # Miscellaneous Symbols
            0x2700 <= code_point <= 0x27BF or    # Dingbats
            0xFE00 <= code_point <= 0xFE0F):      # Variation selectors
            return True
    except:
        pass
    return False


def renderMessageHTML(message, baseUserAvatarsPath, baseUserEmojisPath, emojiIdCache, baseUserFilePath, baseUserPath=None, channelFolderPath=None, isPinned=False, isReply=False, options=None):
    """
    Render a message as HTML.
    Returns HTML string for the message.
    """
    global debug
    
    userName = message.get("name", "")
    userID = message.get("user_id", "")
    singleMessage = message.get("message", "")
    time = message.get("time", "")
    reactions = message.get("reactions", [])
    pictures = message.get("pictures", [])
    videos = message.get("videos", [])
    parent_message_info = message.get("parent_message_info", None)
    
    # Calculate baseUserPath if not provided (baseUserFilePath is typically baseUserPath/files/)
    if baseUserPath is None:
        # baseUserFilePath is typically baseUserPath/files/, so go up one level
        if baseUserFilePath.endswith('files/') or baseUserFilePath.endswith('files'):
            baseUserPath = os.path.dirname(baseUserFilePath)
        else:
            baseUserPath = os.path.dirname(baseUserFilePath)
    
    # Use channelFolderPath for files and videos if provided, otherwise fall back to baseUserFilePath
    if channelFolderPath is None:
        channelFolderPath = baseUserFilePath
    
    log_debug(f'renderMessageHTML: channelFolderPath={channelFolderPath}, baseUserPath={baseUserPath}')
    
    html_parts = []
    
    # Get post ID for anchor
    post_id = message.get("post_id", "")
    anchor_id = f'message-{post_id}' if post_id else ''
    
    # Message container with anchor
    pinned_class = " pinned" if isPinned else ""
    if anchor_id:
        html_parts.append(f'<div id="{anchor_id}" class="message{pinned_class}">')
    else:
        html_parts.append(f'<div class="message{pinned_class}">')
    
    # Message header - always include avatar in header
    pinned_header_class = " pinned" if isPinned else ""
    html_parts.append(f'<div class="message-header{pinned_header_class}">')
    
    # Avatar - always attempt to get and display avatar in message header
    avatarPath = None
    avatarAdded = False
    
    if userID:
        avatarFilePath = os.path.join(baseUserAvatarsPath, f'{userID}')
        log_debug(f'renderMessageHTML: Getting avatar for userID: {userID}, userName: {userName}, avatarFilePath: {avatarFilePath}, baseUserAvatarsPath: {baseUserAvatarsPath}')
        # Download avatar if it doesn't exist
        avatarPath = getUserAvatar(userID, avatarFilePath)
        log_debug(f'renderMessageHTML: Avatar path result: {avatarPath}')
        if avatarPath:
            log_debug(f'renderMessageHTML: Avatar file exists check: {os.path.exists(avatarPath)}')
    else:
        log_debug(f'renderMessageHTML: No userID for message from userName: {userName}, message keys: {list(message.keys())}')
    
    # Always add avatar to message header if available
    if avatarPath and os.path.exists(avatarPath):
        log_debug(f'renderMessageHTML: Avatar file exists, converting to data URI: {avatarPath}')
        # Convert to data URI for single-file HTML
        data_uri = image_to_data_uri(avatarPath)
        if data_uri:
            log_debug(f'renderMessageHTML: Avatar data URI created successfully (length: {len(data_uri)})')
            avatar_html = f'<img src="{data_uri}" class="avatar" alt="{html.escape(userName)}">'
            log_debug(f'renderMessageHTML: Appending avatar HTML: {avatar_html[:100]}...')
            html_parts.append(avatar_html)
            avatarAdded = True
            log_debug(f'renderMessageHTML: Avatar HTML appended, avatarAdded={avatarAdded}, html_parts length={len(html_parts)}')
        else:
            log_debug(f'renderMessageHTML: Avatar data URI conversion failed, using relative path')
            # Fallback to relative path if data URI conversion fails
            # Calculate relative path from baseUserPath (where HTML file is located)
            try:
                rel_avatar_path = os.path.relpath(avatarPath, baseUserPath)
                # URL encode the path to handle spaces
                rel_avatar_path_encoded = quote(rel_avatar_path.replace('\\', '/'))
                log_debug(f'renderMessageHTML: Using relative avatar path: {rel_avatar_path_encoded}')
                html_parts.append(f'<img src="{rel_avatar_path_encoded}" class="avatar" alt="{html.escape(userName)}">')
                avatarAdded = True
            except Exception as e:
                log_error(f'renderMessageHTML: Error calculating relative avatar path: {e}', exception=e)
                # Last resort: use filename only
                avatar_filename = os.path.basename(avatarPath)
                html_parts.append(f'<img src="avatars/{avatar_filename}" class="avatar" alt="{html.escape(userName)}">')
                avatarAdded = True
    else:
        if avatarPath:
            log_debug(f'renderMessageHTML: Avatar path returned but file does not exist: {avatarPath}')
        else:
            log_warning(f'renderMessageHTML: No avatar path returned for userID: {userID}, userName: {userName}')
    
    # Always add avatar or placeholder to message header
    if not avatarAdded:
        log_warning(f'renderMessageHTML: Avatar NOT added to HTML. userName: {userName}, userID: {userID}, avatarPath: {avatarPath}')
        # Always add a placeholder to maintain layout consistency
        html_parts.append(f'<span class="avatar-placeholder" style="display: inline-block; width: 32px; height: 32px; border-radius: 50%; background: #ccc; margin-right: 5px; vertical-align: middle;"></span>')
    
    # Username and time - wrap in span for proper inline display with avatar
    header_text = f'{html.escape(userName)} {html.escape(time)}'
    if isPinned:
        header_text += ' Pinned'
    html_parts.append(f'<span>{header_text}</span>')
    html_parts.append('</div>')
    
    # Reply context - hyperlink to the parent message
    if isReply and parent_message_info:
        parent_post_id = parent_message_info.get('post_id', '')
        parent_anchor = f'#message-{parent_post_id}' if parent_post_id else '#'
        reply_text = f"Commented on {html.escape(parent_message_info['name'])}'s message: {html.escape(parent_message_info['preview'])} ({html.escape(parent_message_info['date'])})"
        html_parts.append(f'<div class="reply-context"><a href="{parent_anchor}">{reply_text}</a></div>')
    
    # Message text - process emojis similar to PDF rendering
    html_parts.append('<div class="message-text">')
    message_html = renderTextWithEmojisHTML(singleMessage, baseUserEmojisPath, emojiIdCache)
    html_parts.append(message_html)
    html_parts.append('</div>')
    
    # Images
    if pictures:
        userPicturesFilePath = os.path.join(baseUserPath, "pics/")
        for picture in pictures:
            imagePath = os.path.join(userPicturesFilePath, f'{picture["id"]}_{picture["name"]}')
            if os.path.exists(imagePath):
                # Convert to data URI for single-file HTML
                data_uri = image_to_data_uri(imagePath)
                if data_uri:
                    html_parts.append(f'<img src="{data_uri}" style="max-width: 75%; margin: 5px 0;">')
                else:
                    # Fallback to relative path if data URI conversion fails
                    # Calculate path relative to the HTML file location (baseUserPath)
                    # URL-encode the path to handle spaces in filenames
                    rel_image_path = os.path.relpath(imagePath, baseUserPath)
                    # Split path into components and quote each part to handle spaces
                    path_parts = rel_image_path.split(os.sep)
                    quoted_parts = [quote(part, safe='') for part in path_parts]
                    quoted_path = '/'.join(quoted_parts)
                    html_parts.append(f'<img src="{quoted_path}" style="max-width: 75%; margin: 5px 0;">')
            else:
                # Image file doesn't exist - log for debugging
                log_debug(f'Image file not found: {imagePath}')
    
    # Videos
    if videos:
        userVideosFilePath = os.path.join(channelFolderPath, "videos")
        # Normalize paths to absolute for comparison
        userVideosFilePath = os.path.abspath(userVideosFilePath)
        log_debug(f'Looking for videos in: {userVideosFilePath} (channelFolderPath={channelFolderPath})')
        # List actual files in the directory for debugging
        if os.path.exists(userVideosFilePath):
            try:
                actual_files = os.listdir(userVideosFilePath)
                log_debug(f'Actual files in videos directory ({len(actual_files)}): {actual_files[:10]}...')  # Show first 10
            except Exception as e:
                log_debug(f'Could not list files in videos directory: {e}')
        else:
            log_debug(f'Videos directory does not exist: {userVideosFilePath}')
        
        for video in videos:
            video_name = video.get("name", "video")
            video_id = video.get("id", "")
            videoPath = os.path.join(userVideosFilePath, f'{video_id}_{video_name}')
            videoPath = os.path.abspath(videoPath)  # Normalize to absolute path
            
            # Try to find the video file - check if it exists
            # Also try without the ID prefix in case the file was saved differently
            video_found = os.path.exists(videoPath)
            log_debug(f'Checking video path: {videoPath}, exists: {video_found}, video_id={video_id}, video_name={video_name}')
            if not video_found:
                # Try alternative path (just the filename)
                alt_videoPath = os.path.join(userVideosFilePath, video_name)
                alt_videoPath = os.path.abspath(alt_videoPath)
                video_found = os.path.exists(alt_videoPath)
                log_debug(f'Checking alternative video path: {alt_videoPath}, exists: {video_found}')
                if video_found:
                    videoPath = alt_videoPath
            
            if not video_found:
                # Last resort: try to find video by name only (in case ID prefix doesn't match)
                try:
                    if os.path.exists(userVideosFilePath):
                        for existing_file in os.listdir(userVideosFilePath):
                            # Check if the existing file ends with the expected filename
                            if existing_file.endswith(video_name) or existing_file == video_name:
                                found_path = os.path.join(userVideosFilePath, existing_file)
                                found_path = os.path.abspath(found_path)
                                if os.path.exists(found_path):
                                    videoPath = found_path
                                    video_found = True
                                    log_debug(f'Found video by name match: {found_path}')
                                    break
                except Exception as e:
                    log_debug(f'Error searching for video by name: {e}')
            
            if video_found:
                # Use relative path for videos (not data URI due to size)
                # Calculate path relative to the HTML file location (baseUserPath)
                # URL-encode the path to handle spaces in filenames
                rel_video_path = os.path.relpath(videoPath, baseUserPath)
                # Split path into components and quote each part to handle spaces
                path_parts = rel_video_path.split(os.sep)
                quoted_parts = [quote(part, safe='') for part in path_parts]
                quoted_path = '/'.join(quoted_parts)
                video_name_escaped = html.escape(video_name)
                video_ext = video.get("extension", "mp4")
                html_parts.append(f'<video controls style="max-width: 75%; margin: 5px 0;">')
                html_parts.append(f'<source src="{quoted_path}" type="video/{video_ext}">')
                html_parts.append(f'Your browser does not support the video tag. <a href="{quoted_path}">Download {video_name_escaped}</a>')
                html_parts.append(f'</video>')
            else:
                # Video not found - show message with debug log
                video_name_escaped = html.escape(video_name)
                log_debug(f'Video file not found after all attempts: {videoPath} (searched in: {userVideosFilePath})')
                html_parts.append(f'<div class="file-attachment">🎥 {video_name_escaped} (not downloaded)</div>')
    
    # Files (non-image, non-video attachments)
    files = message.get("files", [])
    if files:
        userFilesPath = os.path.join(channelFolderPath, "files")
        # Normalize paths to absolute for comparison
        userFilesPath = os.path.abspath(userFilesPath)
        log_debug(f'Looking for files in: {userFilesPath} (channelFolderPath={channelFolderPath})')
        # List actual files in the directory for debugging
        if os.path.exists(userFilesPath):
            try:
                actual_files = os.listdir(userFilesPath)
                log_debug(f'Actual files in files directory ({len(actual_files)}): {actual_files[:10]}...')  # Show first 10
            except Exception as e:
                log_debug(f'Could not list files in files directory: {e}')
        else:
            log_debug(f'Files directory does not exist: {userFilesPath}')
        
        for file in files:
            file_name = file.get("name", "file")
            file_id = file.get("id", "")
            filePath = os.path.join(userFilesPath, f'{file_id}_{file_name}')
            filePath = os.path.abspath(filePath)  # Normalize to absolute path
            
            # Try to find the file - check if it exists
            # Also try without the ID prefix in case the file was saved differently
            file_found = os.path.exists(filePath)
            log_debug(f'Checking file path: {filePath}, exists: {file_found}, file_id={file_id}, file_name={file_name}')
            if not file_found:
                # Try alternative path (just the filename)
                alt_filePath = os.path.join(userFilesPath, file_name)
                alt_filePath = os.path.abspath(alt_filePath)
                file_found = os.path.exists(alt_filePath)
                log_debug(f'Checking alternative file path: {alt_filePath}, exists: {file_found}')
                if file_found:
                    filePath = alt_filePath
            
            if not file_found:
                # Last resort: try to find file by name only (in case ID prefix doesn't match)
                try:
                    if os.path.exists(userFilesPath):
                        for existing_file in os.listdir(userFilesPath):
                            # Check if the existing file ends with the expected filename
                            if existing_file.endswith(file_name) or existing_file == file_name:
                                found_path = os.path.join(userFilesPath, existing_file)
                                found_path = os.path.abspath(found_path)
                                if os.path.exists(found_path):
                                    filePath = found_path
                                    file_found = True
                                    log_debug(f'Found file by name match: {found_path}')
                                    break
                except Exception as e:
                    log_debug(f'Error searching for file by name: {e}')
            
            if file_found:
                # Use relative path for files
                rel_file_path = os.path.relpath(filePath, baseUserPath)
                # Split path into components and quote each part to handle spaces
                path_parts = rel_file_path.split(os.sep)
                quoted_parts = [quote(part, safe='') for part in path_parts]
                quoted_path = '/'.join(quoted_parts)
                file_name_escaped = html.escape(file_name)
                html_parts.append(f'<div class="file-attachment"><a href="{quoted_path}">📎 {file_name_escaped}</a></div>')
            else:
                # File not found - show message with debug log
                file_name_escaped = html.escape(file_name)
                log_debug(f'File not found after all attempts: {filePath} (searched in: {userFilesPath})')
                html_parts.append(f'<div class="file-attachment">📎 {file_name_escaped} (not downloaded)</div>')
    
    # Reactions - only include if options.include_reactions is True
    if reactions and options and options.include_reactions:
        for reaction in reactions:
            emoji = reaction.get("emoji_name", "")
            userId = reaction.get("user_id", "")
            
            if not emoji:
                continue
            
            html_parts.append('<div class="reaction">')
            
            # Try to find emoji image - check if it's a standard emoji first
            emojiImagePath = None
            unicode_char = emoji_name_to_unicode(emoji)
            
            if unicode_char:
                # Standard emoji - try to get Unicode emoji image
                emoji_base = unicode_char[0] if unicode_char else ''
                if emoji_base:
                    emojiFilePath = os.path.join(baseUserEmojisPath, f'unicode_{ord(emoji_base):X}')
                    for ext in ['png', 'gif', 'jpg', 'jpeg']:
                        potential_path = f'{emojiFilePath}.{ext}'
                        if os.path.exists(potential_path):
                            emojiImagePath = potential_path
                            break
                
                # If image not found, use Unicode character directly
                if not emojiImagePath:
                    html_parts.append(f'<span style="font-size: 16px;">{html.escape(unicode_char)}</span>')
                else:
                    # Convert to data URI for single-file HTML
                    data_uri = image_to_data_uri(emojiImagePath)
                    if data_uri:
                        html_parts.append(f'<img src="{data_uri}" alt=":{emoji}:" style="width: 16px; height: 16px; vertical-align: middle;">')
                    else:
                        # Fallback to relative path if data URI conversion fails
                        rel_emoji_path = os.path.relpath(emojiImagePath, os.path.dirname(baseUserEmojisPath))
                        html_parts.append(f'<img src="emojis/{rel_emoji_path}" alt=":{emoji}:" style="width: 16px; height: 16px; vertical-align: middle;">')
            elif emoji in emojiIdCache:
                # Custom emoji - try to find emoji image file
                emojiFilePath = os.path.join(baseUserEmojisPath, f'{emoji}')
                for ext in ['png', 'gif', 'jpg', 'jpeg']:
                    potential_path = f'{emojiFilePath}.{ext}'
                    if os.path.exists(potential_path):
                        emojiImagePath = potential_path
                        break
                
                if emojiImagePath:
                    # Convert to data URI for single-file HTML
                    data_uri = image_to_data_uri(emojiImagePath)
                    if data_uri:
                        html_parts.append(f'<img src="{data_uri}" alt=":{emoji}:" style="width: 16px; height: 16px; vertical-align: middle;">')
                    else:
                        # Fallback to relative path if data URI conversion fails
                        rel_emoji_path = os.path.relpath(emojiImagePath, os.path.dirname(baseUserEmojisPath))
                        html_parts.append(f'<img src="emojis/{rel_emoji_path}" alt=":{emoji}:" style="width: 16px; height: 16px; vertical-align: middle;">')
                else:
                    # Custom emoji image not found - show as text
                    html_parts.append(f':{html.escape(emoji)}:')
            else:
                # Not a recognized emoji - show as text
                html_parts.append(f':{html.escape(emoji)}:')
            
            # Username
            if userId:
                try:
                    user = getUser(userId)
                    userName = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                    if not userName:
                        userName = user.get('username', userId)
                    html_parts.append(f' {html.escape(userName)}')
                except:
                    html_parts.append(f' {html.escape(str(userId))}')
            
            html_parts.append('</div>')
    
    html_parts.append('</div>')
    
    # Debug: Check if avatar HTML is in the output
    html_output = '\n'.join(html_parts)
    if 'class="avatar"' in html_output:
        log_debug(f'renderMessageHTML: Avatar HTML found in output for userName: {userName}')
    else:
        log_debug(f'renderMessageHTML: Avatar HTML NOT found in output for userName: {userName}')
        log_debug(f'renderMessageHTML: First 500 chars of output: {html_output[:500]}')
    
    return html_output


def renderTextWithEmojisHTML(text, baseUserEmojisPath, emojiIdCache):
    """
    Render text with emoji images for HTML export.
    Returns HTML string with emojis as <img> tags.
    """
    # Pattern to match custom emoji text like :arrow_right: or :+1: or :100:
    # Updated regex to allow emojis with 3+ digits when the name starts with a digit (e.g., :100: is emoji, but :29: or :3: is not)
    emoji_pattern = re.compile(r':([a-zA-Z_][a-zA-Z0-9_+-]*|\+[0-9]+|[0-9]{3,}):')
    
    # Split text into segments: text, custom emojis (:name:), and Unicode emojis
    parts = []
    last_end = 0
    
    # First, find custom emoji patterns
    for match in emoji_pattern.finditer(text):
        # Add text before emoji
        if match.start() > last_end:
            text_part = text[last_end:match.start()]
            if text_part:
                parts.append(('text', text_part))
        
        # Add custom emoji
        emoji_name = match.group(1)
        parts.append(('custom_emoji', emoji_name))
        last_end = match.end()
    
    # Add remaining text
    if last_end < len(text):
        text_part = text[last_end:]
        if text_part:
            parts.append(('text', text_part))
    
    # If no custom emojis, just split by text
    if not parts:
        parts = [('text', text)]
    
    # Now process parts and convert to HTML
    html_parts = []
    for part_type, part_content in parts:
        if part_type == 'text':
            # Process text for Unicode emojis and escape HTML
            current_text = ""
            i = 0
            while i < len(part_content):
                char = part_content[i]
                if is_unicode_emoji_char(char):
                    # Save any text before emoji
                    if current_text:
                        escaped_text = html.escape(current_text).replace('\n', '<br>')
                        html_parts.append(escaped_text)
                        current_text = ""
                    # Add emoji
                    emoji_chars = char
                    # Check for variation selectors
                    if i + 1 < len(part_content):
                        next_char = part_content[i+1]
                        next_code = ord(next_char)
                        if next_code in [0xFE0F, 0xFE00]:
                            emoji_chars += next_char
                            i += 1
                    
                    # Try to get emoji image
                    emoji_base = emoji_chars[0] if emoji_chars else ''
                    if emoji_base:
                        emojiFilePath = os.path.join(baseUserEmojisPath, f'unicode_{ord(emoji_base):X}')
                        emojiImagePath = None
                        for ext in ['png', 'gif', 'jpg', 'jpeg']:
                            potential_path = f'{emojiFilePath}.{ext}'
                            if os.path.exists(potential_path):
                                emojiImagePath = potential_path
                                break
                        
                        if emojiImagePath:
                            # Convert to data URI for single-file HTML
                            data_uri = image_to_data_uri(emojiImagePath)
                            if data_uri:
                                html_parts.append(f'<img src="{data_uri}" alt="{html.escape(emoji_chars)}" style="width: 16px; height: 16px; vertical-align: middle;">')
                            else:
                                # Fallback to relative path if data URI conversion fails
                                rel_path = os.path.relpath(emojiImagePath, os.path.dirname(baseUserEmojisPath))
                                html_parts.append(f'<img src="emojis/{rel_path}" alt="{html.escape(emoji_chars)}" style="width: 16px; height: 16px; vertical-align: middle;">')
                        else:
                            # Fallback to Unicode character
                            html_parts.append(html.escape(emoji_chars))
                else:
                    current_text += char
                i += 1
            if current_text:
                # Process markdown formatting: code blocks, inline code, italic, bold, markdown links [title](url), and URLs
                # processMarkdownForHTML already handles all markdown including links and URLs, and returns properly formatted HTML
                processed_html = processMarkdownForHTML(current_text)
                html_parts.append(processed_html)
        elif part_type == 'custom_emoji':
            # Check if it's a standard emoji name that we can convert to Unicode
            unicode_char = emoji_name_to_unicode(part_content)
            
            if unicode_char:
                # Standard emoji - render as Unicode emoji image
                emoji_base = unicode_char[0] if unicode_char else ''
                if emoji_base:
                    emojiFilePath = os.path.join(baseUserEmojisPath, f'unicode_{ord(emoji_base):X}')
                    emojiImagePath = None
                    for ext in ['png', 'gif', 'jpg', 'jpeg']:
                        potential_path = f'{emojiFilePath}.{ext}'
                        if os.path.exists(potential_path):
                            emojiImagePath = potential_path
                            break
                    
                    if emojiImagePath:
                        # Convert to data URI for single-file HTML
                        data_uri = image_to_data_uri(emojiImagePath)
                        if data_uri:
                            html_parts.append(f'<img src="{data_uri}" alt=":{part_content}:" style="width: 16px; height: 16px; vertical-align: middle;">')
                        else:
                            # Fallback to relative path if data URI conversion fails
                            rel_path = os.path.relpath(emojiImagePath, os.path.dirname(baseUserEmojisPath))
                            html_parts.append(f'<img src="emojis/{rel_path}" alt=":{part_content}:" style="width: 16px; height: 16px; vertical-align: middle;">')
                    else:
                        html_parts.append(html.escape(unicode_char))
                else:
                    html_parts.append(f':{html.escape(part_content)}:')
            elif part_content in emojiIdCache:
                # Custom emoji - try to find emoji image file
                emojiFilePath = os.path.join(baseUserEmojisPath, f'{part_content}')
                emojiImagePath = None
                for ext in ['png', 'gif', 'jpg', 'jpeg']:
                    potential_path = f'{emojiFilePath}.{ext}'
                    if os.path.exists(potential_path):
                        emojiImagePath = potential_path
                        break
                
                if emojiImagePath:
                    # Convert to data URI for single-file HTML
                    data_uri = image_to_data_uri(emojiImagePath)
                    if data_uri:
                        html_parts.append(f'<img src="{data_uri}" alt=":{part_content}:" style="width: 16px; height: 16px; vertical-align: middle;">')
                    else:
                        # Fallback to relative path if data URI conversion fails
                        rel_path = os.path.relpath(emojiImagePath, os.path.dirname(baseUserEmojisPath))
                        html_parts.append(f'<img src="emojis/{rel_path}" alt=":{part_content}:" style="width: 16px; height: 16px; vertical-align: middle;">')
                else:
                    html_parts.append(f':{html.escape(part_content)}:')
            else:
                # Unknown emoji, render as text
                html_parts.append(f':{html.escape(part_content)}:')
    
    return ''.join(html_parts)


def makeJsonFile(username):
    '''
    makeJsonFile

    Export the messages as JSON

        @param username

    '''
    ## PRINT STATEMENT FOR JSON FILE NEEDED
    jsonPath = os.path.join( baseUserPath, f'{username}.gz' )
    log_info("Writing JSON to file")
    log_info(jsonPath)
    with gzip.open(jsonPath, 'wt', encoding="ascii") as zipfile:
        json.dump(channelCache, zipfile)


if __name__ == '__main__':
  main()
