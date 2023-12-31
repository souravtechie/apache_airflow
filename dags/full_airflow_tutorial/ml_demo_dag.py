from airflow import DAG
from airflow.operators.dummy import DummyOperator
from airflow.operators.python_operator import PythonOperator
from datetime import datetime


def predict_views():
    return {'0OQqLbgdLBU': 2000,
            'sv2v1kDgiZQ': 3000,
            'dobGIxQJA6U': 500,
            'GmN1emEe4Jo': 4444,
            '5b2ZRswqSZc': 9898,
            'DEAIUu2E24A': 123}


default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2022, 1, 1),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1
}

dag = DAG('ml_demo_dag',
          default_args=default_args,
          schedule_interval=None)

start_task = DummyOperator(task_id='get_youtube_data',
                           dag=dag)

task_1 = DummyOperator(task_id='preprocess_and_clean_data',
                       dag=dag)

task_2 = PythonOperator(task_id='make_weekly_views_prediction',
                        dag=dag,
                        python_callable=predict_views)

end_task = DummyOperator(task_id='end_task',
                         dag=dag)

start_task >> task_1 >> task_2 >> end_task