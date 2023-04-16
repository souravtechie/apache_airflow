import json
from helpers.render_dags import generate_ml_dags
import os
from airflow.configuration import conf
from airflow.models import Variable


dag_folder = conf['core']['dags_folder']

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': '2022-04-04',
    'catchup': False,
}


for ml_config in os.listdir(f"{dag_folder}/ml_configs"):
    file_contents = open(os.path.join(f"{dag_folder}/ml_configs/{ml_config}"))
    ml_config_dict = json.load(file_contents)

    dag_id = 'run_ml_model_' + ml_config.replace('.json', '')

    returned_dag = generate_ml_dags(
        dag_id=dag_id,
        ml_config=ml_config_dict,
        default_args=default_args,
    )

    if returned_dag is not None:
        globals()[dag_id] = returned_dag

