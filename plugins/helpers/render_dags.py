import logging

from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn import datasets as data_sets
from sklearn.model_selection import train_test_split
import numpy as np
import pandas as pd

from airflow import DAG, settings
from airflow.operators.python_operator import PythonOperator
# tasks: get_training_data_from_s3, train_model, put_predicted_data_to_s3

# Load dataset
iris = data_sets.load_iris()
X, y = iris['data'], iris['target']


def ml_model_predictions(X, y, test_size, model_name):
    """

    :param X: Input Numpy array
    :param y: Output
    :param model_name:
    :param test_size:
    :return:
    """
    # Split data into training and testing sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=42)

    # Create model
    model = eval(model_name + '()')

    # Train model
    model.fit(X_train, y_train)

    # Make predictions
    y_pred = model.predict(X_test)

    final_op = []
    for i in range(0, len(X_test)):
        a = np.insert(X_test[i], 4, y_pred[i])
        final_op.append(list(a))

    df = pd.DataFrame(final_op)
    logging.info('df = %s', df)

    #return df



def generate_ml_dags(dag_id, ml_config, default_args, ml_config_dict):
    """
    :param dag_id:
    :param ml_config:
    :param default_args:
    :param ml_config_dict:
    :return:
    """

    retrieved_schedule = ml_config_dict.get('schedule')
    retrieved_ml_algo = ml_config_dict.get('algo_name')
    dag = DAG(dag_id, schedule_interval=retrieved_schedule, default_args=default_args, catchup=False, tags=['ML'])
    with dag:
        ml_task = PythonOperator(
                    task_id='ml_test',
                    provide_context=True,
                    python_callable=ml_model_predictions,
                    op_args=[X, y, 0.2, retrieved_ml_algo],
                    dag=dag
    )

    return dag