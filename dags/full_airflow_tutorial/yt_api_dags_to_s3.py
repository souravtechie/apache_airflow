from datetime import datetime
import pandas as pd
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from googleapiclient.discovery import build
from airflow.hooks.S3_hook import S3Hook
from io import StringIO

api_service_name = "youtube"
api_version = "v3"
credentials = ''
my_channel_id = ''

def get_channel_stats(youtube):
    """
    This function gets channel stats
    @param youtube: Youtube API object
    Returns: dataframe with all channel stats for each channel ID
    """

    request = youtube.channels().list(
        part="snippet,contentDetails,statistics",
        id=my_channel_id
    )
    channel_response = request.execute()['items'][0]


    playlist_id = channel_response['contentDetails']['relatedPlaylists']['uploads']


    return playlist_id


def get_video_ids(youtube, playlist_id):
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

    df = pd.DataFrame(vids_details)

    s3 = S3Hook(aws_conn_id='s3_test')
    csv_buffer = StringIO()

    df.to_csv(csv_buffer, index=False)
    s3.load_string(string_data=csv_buffer.getvalue(), key='yt_api_data/test_csv_file.csv', bucket_name='yt-bucket-demo', replace=True)



# Define the DAG
with DAG(
    dag_id="youtube_views_data_to_S3_only",
    start_date=datetime(2023, 1, 1),
    schedule_interval="0 10 * * *",
    catchup=False,
    tags=['YT demo'],
) as dag:

    # Define Postgres task
    cleanup_query_task = PythonOperator(
        task_id='youtube_to_s3',
        python_callable=call_yt_apis
    )

