from airflow import DAG
from airflow.operators.dummy import DummyOperator
from airflow.operators.python_operator import PythonOperator
from airflow.operators.python import BranchPythonOperator
from datetime import datetime


def predict_views():

    video_scores = {'0OQqLbgdLBU': 2000,
            'sv2v1kDgiZQ': 3000,
            'dobGIxQJA6U': 500,
            'GmN1emEe4Jo': 4444,
            '5b2ZRswqSZc': 9898,
            'DEAIUu2E24A': 123}

    return video_scores


def branch_func(**kwargs):
    ti = kwargs['ti']
    xcom_value = ti.xcom_pull(task_ids='make_weekly_views_prediction')
    length = len(xcom_value)

    if sum(xcom_value.values())*1.0/length <= 3500:
        return 'run_instagram_ads_campaign'
    else:
        return 'stop_task'


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2022, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'catchup': False
}

dag = DAG('xcom_demo',
          default_args=default_args,
          schedule_interval="0 10 * * *")

start_task = DummyOperator(task_id='get_youtube_data',
                           dag=dag)

preprocess = DummyOperator(task_id='preprocess_and_clean_data',
                           dag=dag)

views_prediction = PythonOperator(task_id='make_weekly_views_prediction',
                                  dag=dag,
                                  python_callable=predict_views)

branch_operator = BranchPythonOperator(
    task_id='make_data_driven_decision',
    provide_context=True,
    python_callable=branch_func,
    dag=dag)

end_task = DummyOperator(task_id='end_task',
                         dag=dag)

trigger_ig_campaign = DummyOperator(task_id='run_instagram_ads_campaign',
                                    dag=dag)

start_task >> preprocess >> views_prediction >> branch_operator
branch_operator >> [end_task, trigger_ig_campaign]
