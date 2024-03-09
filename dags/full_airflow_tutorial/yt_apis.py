"""
This python script prints the details of
all videos from a YT channel using YT apis
"""

from googleapiclient.discovery import build
from helpers.constants import CREDENTIALS, MY_CHANNEL_ID

api_service_name = "youtube"
api_version = "v3"
credentials = CREDENTIALS
my_channel_id = MY_CHANNEL_ID


def get_playlist_id(youtube):
    """
    This function gets channel stats
    @param youtube: Youtube API object
    Returns: (playlist_id) The ID of the playlist that contains the channel's uploaded videos
    """

    request = youtube.channels().list(
        part="snippet, contentDetails, statistics",
        id=my_channel_id
    )
    channel_response = request.execute()['items'][0]

    # See YT APIs docs here https://developers.google.com/youtube/v3/docs/channels#contentDetails.relatedPlaylists.uploads
    playlist_id = channel_response['contentDetails']['relatedPlaylists']['uploads']

    return playlist_id


def get_video_ids(youtube, playlist_id):
    """
    This function returns a list of video IDs of all videos in a YT playlist.
    :param youtube: Youtube API object
    :param playlist_id: ID of the playlist
    :return: list of video IDs
    """
    video_ids = []

    request = youtube.playlistItems().list(
        part="snippet,contentDetails",
        playlistId=playlist_id,
        maxResults=50
    )
    response = request.execute()

    for item in response['items']:
        video_ids.append(item['contentDetails']['videoId'])

    next_page_token = response.get('nextPageToken')
    while next_page_token is not None:
        request = youtube.playlistItems().list(
            part='contentDetails',
            playlistId=playlist_id,
            maxResults=50,
            pageToken=next_page_token)
        response = request.execute()

        for item in response['items']:
            video_ids.append(item['contentDetails']['videoId'])

        next_page_token = response.get('nextPageToken')

    return video_ids


def get_video_details(youtube, video_ids):
    """
    This function gets details for a video
    :param youtube: YT API client object
    :param video_ids: IDs of the videos we want the details for
    :return: A list of details for each video
    """
    all_video_info = []

    for i in range(0, len(video_ids), 50):
        request = youtube.videos().list(
            part="snippet,contentDetails,statistics",
            id=','.join(video_ids[i:i + 50])
        )
        response = request.execute()

        for video in response['items']:
            stats_to_keep = {'snippet': ['title', 'publishedAt'],
                             'statistics': ['viewCount', 'likeCount', 'commentCount'],
                             #'contentDetails': ['duration']
                             }
            video_info = {}
            video_info['video_id'] = video['id']

            for k in stats_to_keep.keys():
                for v in stats_to_keep[k]:
                    try:
                        video_info[v] = video[k][v]
                    except:
                        video_info[v] = None

            all_video_info.append(video_info)

    return all_video_info


if __name__ == "__main__":
    # Get credentials and create an API client
    youtube = build(
        api_service_name, api_version, developerKey=credentials)

    # Get playlist ID which contains all videos in the channel
    playlist_id = get_playlist_id(youtube)

    # Get video IDs of all videos in the playlist
    video_ids = get_video_ids(youtube, playlist_id)

    # Get details of each video in the playlist.
    # Details such as title, publish date, view count, like count and comment count
    vids_details = get_video_details(youtube, video_ids)

    # Print the details
    for vid in vids_details:
        print(vid)
