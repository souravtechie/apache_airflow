from datetime import datetime
import pandas as pd
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from googleapiclient.discovery import build
from airflow.hooks.S3_hook import S3Hook
from io import StringIO
from helpers.constants import CREDENTIALS, MY_CHANNEL_ID

api_service_name = "youtube"
api_version = "v3"
credentials = CREDENTIALS
my_channel_id = MY_CHANNEL_ID

def get_channel_stats(youtube):
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
    :param youtube: YT object
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


def call_yt_apis(*args, **kwargs):
    # Get credentials and create an API client
    youtube = build(
        api_service_name, api_version, developerKey=credentials)

    playlist_id = get_channel_stats(youtube)
    video_ids = get_video_ids(youtube, playlist_id)
    vids_details = get_video_details(youtube, video_ids)

    for vid in vids_details:
        print(vid)


    # Docs to hooks https://airflow.apache.org/docs/apache-airflow/stable/authoring-and-scheduling/connections.html#hooks
    s3_hook = S3Hook(aws_conn_id='s3_test')
    csv_buffer = StringIO()

    df = pd.DataFrame(vids_details)
    df.to_csv(csv_buffer, index=False)
    s3_hook.load_string(string_data=csv_buffer.getvalue(), key='yt_api_data/video_details.csv', bucket_name='yt-bucket-demo', replace=True)


# # Define the DAG
with DAG(
    dag_id="youtube_views_data_to_S3_only",
    start_date=datetime(2023, 1, 1),
    schedule_interval="0 10 * * *",
    catchup=False,
    tags=['YT demo'],
) as dag:

    # Define Postgres task
    youtube_to_s3clear = PythonOperator(
        task_id='youtube_to_s3',
        python_callable=call_yt_apis
    )

