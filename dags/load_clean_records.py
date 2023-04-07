from datetime import datetime

from airflow import DAG
from airflow.operators.postgres_operator import PostgresOperator

# Define the DAG
with DAG(
    dag_id="clean_up_pg_videos_table",
    start_date=datetime(2023, 1, 1),
    schedule_interval="0 10 * * *",
    catchup=False,
    tags=['YT demo'],
) as dag:

    # Define Postgres task
    cleanup_query_task = PostgresOperator(
        task_id='cleanup_task',
        sql='sql/de_dup_videos_table.sql',
        postgres_conn_id='rds_pg_12'
    )
