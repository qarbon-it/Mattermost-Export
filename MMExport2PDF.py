#!/usr/bin/env python3
# -*- coding: utf-8 -*-

''' MMExport2PDF

Using the Mattermost API, connects to an instance and exports
all channel for a user on a team.

Images and Files are downloaded as well.

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
from pathlib import Path

#import traceback

#########################
## Thirdparty Imports
##

# fpdf is acutally PyFPDF2
from fpdf import FPDF, TitleStyle, Align
from fpdf.enums import FileAttachmentAnnotationName 

__author__ = 'Alexander J. Lallier'
__version__ = '1.0'
__contact__ = ''



#########################
## Globals Variables
##

imageExtenstions = [ 'gif', 'png', 'jpeg', 'jpg' ]

mattermostURL = ''
headers = {}
baseUserPath = ''

users = {}
channelCache = {}


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
        filtergroup.add_argument("-I", "--include", help="Only include these channels in the export.", nargs='*', dest="include", default=[])
        filtergroup.add_argument("-E", "--exclude", help="Exclude these channels from the export", nargs='*', dest="exclude", default=[])
        filtergroup.add_argument("--start-date", help="Start date for message export (YYYY-MM-DD format). If not specified, exports from beginning.", action="store", dest="start_date", default=None)
        filtergroup.add_argument("--end-date", help="End date for message export (YYYY-MM-DD format). If not specified, exports to present.", action="store", dest="end_date", default=None)

        exportgroup = parser.add_argument_group(title='Export Options')
        exportgroup.add_argument("-i", "--images", help="Embed images in PDF", action="store_true", dest="images")
        exportgroup.add_argument("-f", "--files", help="Embed files in PDF", action="store_true", dest="files")
        exportgroup.add_argument("-j", "--json", help="Export JSON", action="store_true", dest="json")
        exportgroup.add_argument("-o", "--output", help="Base output directory", action="store", dest="output", default='./users')

        options = parser.parse_args() # uses sys.argv[1:] by default

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

        os.makedirs( baseUserPath, 0o755, True)
        os.makedirs( baseUserAvatarsPath, 0o755, True)

        # Start Working
        allChannelsForUser = getChannelsForAUser(userInfo['id'], teamInfo['id'])
        allChannelsForUser.reverse()


        hitPublicChannel = False
        hitPrivateChannel = False
        hitDMChannel = False
        hitGroupMessages = False

        # Initialize PDF
        pdf = PDF()
        pdf.add_page()
        pdf.set_auto_page_break(True, 15.0)

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
                pdf.set_fill_color(255, 165, 0)
                pdf.start_section("PUBLIC CHANNELS")
                hitPublicChannel = True

            if (channel["type"] == 'P' and hitPrivateChannel == False):
                pdf.set_fill_color(255, 165, 0)
                pdf.start_section("PRIVATE CHANNELS")
                hitPrivateChannel = True

            if (channel["type"] == 'D' and hitDMChannel == False):
                pdf.set_fill_color(255, 165, 0)
                pdf.start_section("DIRECT MESSAGE CHANNELS")
                hitDMChannel = True

            if (channel["type"] == 'G' and hitGroupMessages == False):
                pdf.set_fill_color(255, 165, 0)
                pdf.start_section("GROUP MESSAGE CHANNELS")
                hitGroupMessages = True

            print(channelDisplayName)
            # File_object.write("## " + channelDisplayName + '\n\n')
            pdf.set_fill_color(255, 0, 0)
            pdf.start_section(channelDisplayName, level=1)
            # pdf.set_link(tableOfContents[channel["display_name"]])
            # pdf.multi_cell(0, 5, messageHeader, 0, 'L', True)
            # pdf.ln()

            channelId = channel["id"]

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
                print(f'Filtered to {len(allPosts)} messages in date range')

            # BEGIN POST PROCESSING
            # Loop over posts for channel
            for post in allPosts:
                pictures = []
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
                                else:
                                    files.append(file)
                    
                    # Reactions
                    reactions = []
                    if "metadata" in post and "reactions" in post["metadata"]:
                        reactions = post["metadata"]["reactions"]

                    postWithUserName = {
                        "name": theUser["first_name"] + " " + theUser["last_name"],
                        "user_id": postUserId,
                        "message": message,
                        "time": str(datetime.datetime.fromtimestamp(post["create_at"] / 1000).strftime("%m/%d/%Y, %I:%M:%S %p")),
                        "pictures": pictures,
                        "files": files,
                        "reactions": reactions,
                        "post": post
                    }

                    if post["is_pinned"] == True:
                        pinnedMessages.append(postWithUserName)

                    messagesArray.append(postWithUserName)

            print('Total Messages: ', len(messagesArray) + 1)
            print('\n')

            if len(pinnedMessages) > 0:
                pdf.start_section("Pinned Messages", level=2)

            # Loop through Pinned messages first, to put them all at the front
            for message in pinnedMessages:
                renderMessageWithAvatar(pdf, message, baseUserAvatarsPath, isPinned=True)

            pdf.set_draw_color(0, 0, 0)
            pdf.set_fill_color(220, 220, 220)
            pdf.start_section("Regular Messages", level=2)

            pdf.set_fill_color(255, 255, 255)
            for message in messagesArray:
                post = message["post"]
                isPinned = post.get("is_pinned", False)
                renderMessageWithAvatar(pdf, message, baseUserAvatarsPath, isPinned=isPinned)


                if( options.images ):
                    try:
                        userPicturesFilePath = os.path.join( baseUserFilePath, "pics/" )
                        os.makedirs( userPicturesFilePath, 0o755, True)

                        for picture in message["pictures"]:
                            try:
                                # APPEND FILE ID TO PATH TO MAKE UNIQUE AND CACHE THIS
                                imagePath = os.path.join( userPicturesFilePath,  f'{picture["id"]}_{picture["name"]}' )
                                myImage = Path(imagePath)

                                if not myImage.exists():
                                    imageObj = getFile( picture["id"] )

                                    with open(imagePath, 'wb') as f:
                                        imageObj.raw.decode_content = True
                                        shutil.copyfileobj(imageObj.raw, f)

                                pdf.image(imagePath, w=(pdf.epw * .75), x=Align.C)

                            except ImageException as ie:
                                print( f'Embed Image error: {ie}' )
                                #traceback.print_exc()
                            except Exception as e:
                                print('Embed Image error: Couldn\'t add picture to PDF')
                                print( e )
                                #traceback.print_exc()

                    except ImageException as ie:
                        print( ie )

                if( options.files ):
                    try:
                        userAttachmentsFilePath = os.path.join( baseUserFilePath, "files/" )
                        os.makedirs( userAttachmentsFilePath, 0o755, True)

                        for aFile in message["files"]:
                            try:
                                filePath = os.path.join( userAttachmentsFilePath, f'{aFile["id"]}_{aFile["name"]}' )
                                myFile = Path(filePath)

                                if not myFile.exists():
                                    fileObj = getFile( aFile["id"] )

                                    with open(filePath, 'wb') as f:
                                        fileObj.raw.decode_content = True
                                        shutil.copyfileobj(fileObj.raw, f)
                                                                
                                if myFile.is_file():                                    
                                    pdf.embed_file( myFile, desc=aFile["name"], compress=True)
                                    pdf.cell(30, 5, 'Attached file: ', 0, align='L', fill=True)
                                    pdf.set_text_color(0, 0, 255)
                                    pdf.cell(0, 5, f'{aFile["id"]}_{aFile["name"]}', 0, align='L', fill=True)
                                    
                            except FileException as fe:
                                print( f'Embed File error: {fe}' )
                                #traceback.print_exc()
                            except Exception as e:
                                print('Embed File error: Couldn\'t add file to PDF')
                                print( e )
                                #traceback.print_exc()
                            finally:
                                pdf.set_text_color(0, 0, 0)
                                pdf.ln()
                                
                    except ImageException as ie:
                        print( ie )

        pdfOutput = os.path.join(baseUserPath, f'{options.user}.pdf' )

        print( pdfOutput )
        print()
        pdf.add_page()
        pdf.output( pdfOutput )

        if( options.json ):
            makeJsonFile(options.user)

    except Exception as e:
        print( e )
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


def getUserAvatar(userID, avatarPath):
    '''
    getUserAvatar

    Downloads and caches a user's avatar image.

        @param userID The user ID
        @param avatarPath The path where the avatar should be saved (without extension)
        @return Path to the avatar file, or None if not available
    '''
    # Check if avatar already exists (try common extensions)
    for ext in ['png', 'jpg', 'jpeg', 'gif']:
        existingPath = f'{avatarPath}.{ext}'
        if os.path.exists(existingPath):
            return existingPath
    
    try:
        # Download avatar from Mattermost API
        avatarURL = f'{mattermostURL}/users/{userID}/image'
        avatarResponse = requests.get(avatarURL, headers=headers, stream=True)
        
        if avatarResponse.status_code == 200:
            # Determine file extension from content type or default to png
            content_type = avatarResponse.headers.get('content-type', 'image/png')
            ext = 'png'
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = 'jpg'
            elif 'gif' in content_type:
                ext = 'gif'
            
            avatarPathWithExt = f'{avatarPath}.{ext}'
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(avatarPathWithExt), 0o755, True)
            
            with open(avatarPathWithExt, 'wb') as f:
                avatarResponse.raw.decode_content = True
                shutil.copyfileobj(avatarResponse.raw, f)
            
            return avatarPathWithExt
        elif avatarResponse.status_code == 404:
            # User has no custom avatar (uses default)
            return None
    except Exception as e:
        # Silently fail - avatars are optional
        pass
    
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


def renderMessageWithAvatar(pdf, message, baseUserAvatarsPath, isPinned=False):
    '''
    renderMessageWithAvatar
    
    Renders a message with avatar, username, time, message text, and reactions.
    
        @param pdf The PDF object
        @param message The message dictionary
        @param baseUserAvatarsPath Path to avatars directory
        @param isPinned Whether this is a pinned message
    '''
    userName = message["name"]
    userID = message.get("user_id", "")
    singleMessage = message["message"]
    time = message["time"]
    reactions = message.get("reactions", [])
    
    # Avatar size
    avatarSize = 8
    
    # Get avatar
    avatarPath = None
    if userID:
        avatarFilePath = os.path.join(baseUserAvatarsPath, f'{userID}')
        avatarPath = getUserAvatar(userID, avatarFilePath)
    
    # Start message row
    if isPinned:
        pdf.set_fill_color(255, 165, 0)
        pdf.set_draw_color(255, 165, 0)
    else:
        pdf.set_fill_color(220, 220, 220)
    
    # Draw avatar if available
    x_start = pdf.get_x()
    y_start = pdf.get_y()
    
    if avatarPath and os.path.exists(avatarPath):
        try:
            pdf.image(avatarPath, x=x_start, y=y_start, w=avatarSize, h=avatarSize)
            pdf.set_x(x_start + avatarSize + 2)
        except Exception as e:
            print(f'Warning: Could not render avatar: {e}')
            pdf.set_x(x_start)
    
    # Username and time
    headerText = f'{handleUnicode(userName)} {time}'
    if isPinned:
        headerText += ' Pinned'
    
    pdf.cell(0, avatarSize if avatarPath else 5, headerText, 0, align='L', fill=True)
    pdf.set_fill_color(255, 255, 255)
    pdf.ln()
    
    # Message text (indent if avatar was shown)
    if avatarPath:
        pdf.set_x(x_start + avatarSize + 2)
    
    # Render message text
    pdf.multi_cell(0, 5, handleUnicode(singleMessage), 1 if isPinned else 0, align='L', fill=True, markdown=True)
    pdf.ln()
    
    # Reactions
    if reactions:
        pdf.set_x(x_start + (avatarSize + 2 if avatarPath else 0))
        pdf.set_font(pdf.fontFamily, '', 8)
        pdf.set_text_color(100, 100, 100)
        
        for reaction in reactions:
            emoji = reaction.get("emoji_name", "")
            userId = reaction.get("user_id", "")
            
            if not emoji:
                continue
            
            # Format emoji for display
            emojiDisplay = formatEmojiForDisplay(emoji)
            
            # Get username who reacted
            userName = ""
            if userId:
                try:
                    user = getUser(userId)
                    userName = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
                    if not userName:
                        userName = user.get('username', userId)
                except:
                    userName = str(userId)
            
            # Build reaction text
            if userName:
                reactionText = f"{emojiDisplay} {userName}"
            else:
                reactionText = f"{emojiDisplay}"
            
            pdf.cell(0, 4, handleUnicode(reactionText), 0, align='L')
            pdf.ln()
        
        pdf.set_text_color(0, 0, 0)
        pdf.set_font(pdf.fontFamily, '', 10)
    
    if isPinned:
        pdf.set_draw_color(0, 0, 0)


def findEmojiFontPath():
    '''
    findEmojiFontPath

    Finds Noto Emoji or Noto Color Emoji font on the system (cross-platform).
    Prefers Noto Color Emoji as it has better emoji coverage.
    
        @return Path to emoji font file or None if not found
    '''
    system = platform.system()
    fontPaths = []
    
    if system == "Darwin":  # macOS
        # Prefer Noto Color Emoji (better coverage)
        fontPaths = [
            "/Library/Fonts/NotoColorEmoji.ttf",
            "/System/Library/Fonts/Supplemental/NotoColorEmoji.ttf",
            os.path.expanduser("~/Library/Fonts/NotoColorEmoji.ttf"),
            "/opt/homebrew/share/fonts/noto/NotoColorEmoji.ttf",
            "/usr/local/share/fonts/noto/NotoColorEmoji.ttf",
            # Fallback to Noto Emoji
            "/Library/Fonts/NotoEmoji-Regular.ttf",
            "/System/Library/Fonts/Supplemental/NotoEmoji-Regular.ttf",
            os.path.expanduser("~/Library/Fonts/NotoEmoji-Regular.ttf"),
            "/opt/homebrew/share/fonts/noto/NotoEmoji-Regular.ttf",
            "/usr/local/share/fonts/noto/NotoEmoji-Regular.ttf",
        ]
    elif system == "Linux":
        # Prefer Noto Color Emoji
        fontPaths = [
            "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
            "/usr/share/fonts/noto/NotoColorEmoji.ttf",
            "/usr/local/share/fonts/noto/NotoColorEmoji.ttf",
            os.path.expanduser("~/.fonts/NotoColorEmoji.ttf"),
            os.path.expanduser("~/.local/share/fonts/NotoColorEmoji.ttf"),
            # Fallback to Noto Emoji
            "/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf",
            "/usr/share/fonts/noto/NotoEmoji-Regular.ttf",
            "/usr/local/share/fonts/noto/NotoEmoji-Regular.ttf",
            os.path.expanduser("~/.fonts/NotoEmoji-Regular.ttf"),
            os.path.expanduser("~/.local/share/fonts/NotoEmoji-Regular.ttf"),
        ]
    elif system == "Windows":
        fontPaths = [
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "NotoColorEmoji.ttf"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts", "NotoColorEmoji.ttf"),
            os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "NotoEmoji-Regular.ttf"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts", "NotoEmoji-Regular.ttf"),
        ]
    
    for fontPath in fontPaths:
        if os.path.exists(fontPath):
            return fontPath
    
    return None


def findFontPath(fontName, style=""):
    '''
    findFontPath

    Finds a font file on the system (cross-platform).
    Searches for NotoSans fonts, with fallback to system fonts.

        @param fontName The base font name (e.g., "NotoSans")
        @param style The font style suffix (e.g., "Bold", "Italic", "BoldItalic")
        @return Path to font file or None if not found
    '''
    system = platform.system()
    fontPaths = []
    
    # Map style to filename suffix
    styleMap = {
        "": "Regular",
        "B": "Bold",
        "I": "Italic",
        "BI": "BoldItalic"
    }
    styleSuffix = styleMap.get(style, "Regular")
    
    if fontName == "NotoSans":
        fontFileName = f"NotoSans-{styleSuffix}.ttf"
        
        # Define search paths based on OS
        if system == "Darwin":  # macOS
            fontPaths = [
                "/Library/Fonts/NotoSans-{}.ttf".format(styleSuffix),
                "/System/Library/Fonts/Supplemental/NotoSans-{}.ttf".format(styleSuffix),
                os.path.expanduser("~/Library/Fonts/NotoSans-{}.ttf".format(styleSuffix)),
                # Homebrew installation
                "/opt/homebrew/share/fonts/noto/NotoSans-{}.ttf".format(styleSuffix),
                "/usr/local/share/fonts/noto/NotoSans-{}.ttf".format(styleSuffix),
            ]
        elif system == "Linux":
            fontPaths = [
                "/usr/share/fonts/truetype/noto/NotoSans-{}.ttf".format(styleSuffix),
                "/usr/share/fonts/noto/NotoSans-{}.ttf".format(styleSuffix),
                "/usr/local/share/fonts/noto/NotoSans-{}.ttf".format(styleSuffix),
                os.path.expanduser("~/.fonts/NotoSans-{}.ttf".format(styleSuffix)),
                os.path.expanduser("~/.local/share/fonts/NotoSans-{}.ttf".format(styleSuffix)),
            ]
        elif system == "Windows":
            fontPaths = [
                os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", f"NotoSans-{styleSuffix}.ttf"),
                os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "Windows", "Fonts", f"NotoSans-{styleSuffix}.ttf"),
            ]
    
    # Try to find the font
    for fontPath in fontPaths:
        if os.path.exists(fontPath):
            return fontPath
    
    # Fallback: try to find any suitable system font
    if system == "Darwin":  # macOS
        # Try Helvetica (built-in macOS font)
        if style == "B":
            return None  # Will use built-in Helvetica-Bold
        elif style == "I":
            return None  # Will use built-in Helvetica-Oblique
        elif style == "BI":
            return None  # Will use built-in Helvetica-BoldOblique
        return None  # Will use built-in Helvetica
    elif system == "Linux":
        # Try DejaVu Sans as fallback
        fallbackPaths = [
            f"/usr/share/fonts/truetype/dejavu/DejaVuSans-{styleSuffix}.ttf",
            f"/usr/share/fonts/dejavu/DejaVuSans-{styleSuffix}.ttf",
        ]
        for fallbackPath in fallbackPaths:
            if os.path.exists(fallbackPath):
                return fallbackPath
    
    return None


class PDF(FPDF):
    def __init__(self):
        super().__init__()

        # Try to find NotoSans fonts, with fallback to system fonts
        fontFound = False
        fontPaths = {}
        self.fontFamily = 'Helvetica'  # Default fallback
        
        for style in ["", "B", "I", "BI"]:
            fontPath = findFontPath("NotoSans", style)
            if fontPath:
                try:
                    self.add_font("NotoSans", style=style, fname=fontPath)
                    fontPaths[style] = fontPath
                    fontFound = True
                except Exception as e:
                    print(f'Warning: Could not load NotoSans font ({style}): {e}')
        
        # If NotoSans not found, use system default fonts
        if not fontFound:
            system = platform.system()
            if system == "Darwin":  # macOS - use Helvetica (built-in)
                print('NotoSans font not found. Using system default font (Helvetica).')
                print('For better Unicode support, install NotoSans fonts. See README for instructions.')
                # FPDF2 has built-in Helvetica support, so we don't need to add it
                self.fontFamily = 'Helvetica'
                self.set_font('Helvetica', '', 10)
            elif system == "Linux":
                # Try DejaVu Sans as fallback
                dejaVuFound = False
                dejaVuStyleMap = {"": "Regular", "B": "Bold", "I": "Oblique", "BI": "BoldOblique"}
                for style in ["", "B", "I", "BI"]:
                    styleSuffix = dejaVuStyleMap.get(style, "Regular")
                    dejaVuPaths = [
                        f"/usr/share/fonts/truetype/dejavu/DejaVuSans-{styleSuffix}.ttf",
                        f"/usr/share/fonts/dejavu/DejaVuSans-{styleSuffix}.ttf",
                    ]
                    for dejaVuPath in dejaVuPaths:
                        if os.path.exists(dejaVuPath):
                            try:
                                self.add_font("DejaVuSans", style=style, fname=dejaVuPath)
                                dejaVuFound = True
                                break
                            except:
                                pass
                
                if dejaVuFound:
                    print('NotoSans font not found. Using DejaVu Sans as fallback.')
                    self.fontFamily = 'DejaVuSans'
                    self.set_font('DejaVuSans', '', 10)
                else:
                    print('NotoSans font not found. Using system default font.')
                    print('For better Unicode support, install NotoSans fonts. See README for instructions.')
                    self.fontFamily = 'Helvetica'
                    self.set_font('Helvetica', '', 10)
            else:  # Windows or other
                print('NotoSans font not found. Using system default font.')
                print('For better Unicode support, install NotoSans fonts. See README for instructions.')
                self.fontFamily = 'Helvetica'
                self.set_font('Helvetica', '', 10)
        else:
            self.fontFamily = 'NotoSans'
            self.set_font('NotoSans', '', 10)
            print(f'Using NotoSans fonts: {", ".join(fontPaths.values())}')
        
        # Try to load Noto Emoji or Noto Color Emoji font as fallback for emojis
        self.emojiFont = None
        emojiFontPath = findEmojiFontPath()
        if emojiFontPath:
            try:
                # Determine font name based on file name
                if "NotoColorEmoji" in emojiFontPath:
                    fontName = "NotoColorEmoji"
                else:
                    fontName = "NotoEmoji"
                
                self.add_font(fontName, style="", fname=emojiFontPath)
                self.emojiFont = fontName
                print(f'Using emoji font: {fontName} from {emojiFontPath}')
            except Exception as e:
                print(f'Warning: Could not load emoji font: {e}')
                self.emojiFont = None
        else:
            print('Noto Emoji font not found. Install Noto Color Emoji or Noto Emoji for better emoji support.')
            print('  macOS:')
            print('    - Try: brew install font-noto-color-emoji')
            print('    - Or download from: https://fonts.google.com/noto/specimen/Noto+Color+Emoji')
            print('    - Then copy NotoColorEmoji.ttf to ~/Library/Fonts/')
            print('  Linux: sudo apt-get install fonts-noto-color-emoji')
            print('  Windows: Download from https://fonts.google.com/noto/specimen/Noto+Color+Emoji')

        self.set_section_title_styles(

            # Level 0 titles:
            TitleStyle(
                font_family="Times",
                font_style="B",
                font_size_pt=24,
                color=(0,0,0),
                underline=True,
                t_margin=5,
                l_margin=0,
                b_margin=5,
            ),
            # Level 1 subtitles:
            TitleStyle(
                font_family="Times",
                font_style="B",
                font_size_pt=20,
                color=(0,0,0),
                underline=True,
                t_margin=5,
                l_margin=0,
                b_margin=5,
            ),
            # Level 2 subtitles:
            TitleStyle(
                font_family="Times",
                font_style="B",
                font_size_pt=15,
                color=(255, 165, 0),
                underline=True,
                t_margin=5,
                l_margin=0,
                b_margin=5,
            )
        )

    def header(self):
        # Use the font family we determined during initialization
        self.set_font(self.fontFamily, style='B', size=12)

        if( channelDisplayName ):
            self.multi_cell(w=0, txt=channelDisplayName, align='C')

        # Line break
        self.ln(15)


    def footer(self):
        # Go to 1.5 cm from bottom
        self.set_y(-15)
        # Use the font family we determined during initialization
        self.set_font(self.fontFamily, style='I', size=8)
        # Print centered85 page number
        self.cell(0, 10, f'Page {self.page_no()}', 0, align='C')
    
    def multi_cell_with_emoji(self, w, h, txt, border=0, align='J', fill=False, markdown=False):
        '''
        multi_cell_with_emoji
        
        Renders text with emoji support. Uses regular font for text rendering.
        Emojis may not render perfectly but text will work.
        '''
        # Just use regular multi_cell - emoji font fallback is complex
        # and causes issues. Regular font should handle most characters.
        return self.multi_cell(w, h, txt, border, align, fill, markdown)


def makeJsonFile(username):
    '''
    makeJsonFile

    Export the messages as JSON

        @param username

    '''
    ## PRINT STATEMENT FOR JSON FILE NEEDED
    jsonPath = os.path.join( baseUserPath, f'{username}.gz' )
    print("Writing JSON to file")
    print(jsonPath)
    with gzip.open(jsonPath, 'wt', encoding="ascii") as zipfile:
        json.dump(channelCache, zipfile)


if __name__ == '__main__':
  main()
