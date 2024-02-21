import json
import os
from datetime import datetime
import pandas as pd
import requests
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from custom_operators.my_postgres_operator import MyPostgresOperator
from airflow.providers.slack.operators.slack import SlackAPIPostOperator
from googleapiclient.discovery import build
from airflow.hooks.S3_hook import S3Hook
from io import StringIO
from helpers.constants import CREDENTIALS, MY_CHANNEL_ID, SLACK_WEBHOOK

api_service_name = "youtube"
api_version = "v3"
credentials = CREDENTIALS
my_channel_id = MY_CHANNEL_ID

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

                video_info['loadTimestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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

    # Create S3 Hook
    s3 = S3Hook(aws_conn_id='s3_test')
    csv_buffer = StringIO()

    df.to_csv(csv_buffer, index=False, header=False)

    #Store file to S3
    s3.load_string(string_data=csv_buffer.getvalue(), key='yt_api_data/video_details.csv', bucket_name='yt-bucket-demo', replace=True)


def on_failure_callback(context):
    webhook_url = SLACK_WEBHOOK
    slack_data = {
        'text': f""":red_circle: DAG *{context['dag'].dag_id}*'s task *{context['task'].task_id}* has failed!!! :red_circle:"""
    }

    response = requests.post(
        webhook_url, data=json.dumps(slack_data),
        headers={'Content-Type': 'application/json'}
    )


# Define the DAG
with DAG(
    dag_id="failure_alert_demo",
    start_date=datetime(2024, 1, 1),
    schedule_interval="0 10 * * *",
    catchup=False,
    tags=['YT demo'],
    on_failure_callback=on_failure_callback
) as dag:

    # Define Postgres task
    yt_apis_to_s3 = PythonOperator(
        task_id='youtube_to_s3',
        python_callable=call_yt_apis,
        provide_context=True,
    )

    transfer_s3_to_sql = MyPostgresOperator(
        task_id='yt_pg',
        sql='',
        postgres_conn_id='yt_pg',
        full_s3_key='yt-bucket-demo/yt_api_data/test_csv_file.csv',
        pg_table_name='video_detail',
        aws_conn_id='s3_test',
    )


    slack_success = SlackAPIPostOperator(
        task_id='success_alert',
        slack_conn_id='slack_conn',
        channel='#full-airflow-tutorial',
        text=':white_check_mark: DAG *{{ dag_id }}* ran successfully!!! :white_check_mark:'
    )

    transfer_s3_to_sql.set_upstream(yt_apis_to_s3)
    transfer_s3_to_sql >> slack_success
