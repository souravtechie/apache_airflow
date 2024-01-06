from datetime import datetime
import pandas as pd
from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.providers.postgres.hooks.postgres import PostgresHook
from custom_operators.my_postgres_operator import MyPostgresOperator
from airflow.providers.slack.operators.slack import SlackAPIPostOperator
#from airflow.operators.email import EmailOperator
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
    s3.load_string(string_data=csv_buffer.getvalue(), key='yt_api_data/test_csv_file.csv', bucket_name='yt-bucket-demo', replace=True)


def load_s3_file_to_pg():
    pg_hook = PostgresHook(postgres_conn_id='yt_pg')
    s3_hook = S3Hook(aws_conn_id='s3_test')

    local_file = s3_hook.download_file(key='yt_api_data/test_csv_file.csv', bucket_name='yt-bucket-demo', local_path='local/', preserve_file_name=True)
    #local_file = s3_hook.get_conn().download_file(Key='yt_api_data/test_csv_file.csv', Filename='test_csv_file_local.csv', Bucket='yt-bucket-demo')

    print(f'type of local file = {type(local_file)}')
    print(f'Local file = {local_file}')

    conn = pg_hook.get_conn()
    pg_cursor = conn.cursor()

    with open(local_file, 'r') as f:
        print(f'file contents are: {f.read()}')

    pg_cursor.copy_from(open(local_file, 'r'), 'video_details', sep=',', columns=('video_id', 'view_count', 'like_count', 'comment_count', 'load_timestamp'))
    conn.commit()
    conn.close()


# Define the DAG
with DAG(
    dag_id="email_alerting",
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

    transfer_s3_to_sql = MyPostgresOperator(
        task_id='yt_pg',
        sql='',
        postgres_conn_id='yt_pg',
        full_s3_key='yt-bucket-demo/yt_api_data/test_csv_file.csv',
        pg_table_name='video_details',
        aws_conn_id='s3_test'
    )

    test_sql = MyPostgresOperator(
        task_id='yt_pg_test',
        sql='SELECT * FROM video_details;',
        postgres_conn_id='yt_pg',
    )

    # email_failure = EmailOperator(
    #     task_id='failure_alert',
    #     to='souravbhowmik21@gmail.com',
    #     subject='Job failure alert',
    #     html_content='Job email_alert has failed',
    # )

    slack_success = SlackAPIPostOperator(
        task_id='success_alert',
        slack_conn_id='slack_conn',
        channel='#full-airflow-tutorial',
        text=':white_check_mark: DAG *email_alert* ran successfully!!! :white_check_mark:'
    )


    transfer_s3_to_sql.set_upstream(cleanup_query_task)
    test_sql.set_upstream(transfer_s3_to_sql)
    test_sql >> slack_success
