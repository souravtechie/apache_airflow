import io
import logging
from io import StringIO # python3; python2: BytesIO
import pickle
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.tree import DecisionTreeClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn import datasets as data_sets
from sklearn.model_selection import train_test_split
import numpy as np
import pandas as pd
from airflow.hooks.S3_hook import S3Hook
from airflow import DAG, settings
from airflow.operators.python_operator import PythonOperator

s3 = S3Hook(aws_conn_id='s3_test')
s3.get_conn()

def ternary_map(x):
    return x.map({"Setosa": 0, "Versicolor": 2, "Virginica": 3})

def binary_map(x):
    return x.map({'yes': 1, "no": 0})


def get_modeling_data(model_config):
    """
    This function returns the S3 key of the input file
    :param model_name:
    :return:
    """
    key = model_config.get("input_file_key")
    input_file = s3.check_for_key(key=key, bucket_name='yt-ml-demo')

    if input_file:
        return {"file_key": key}

    else:
        logging.info("No input data found")
        return None


def preprocess(model_config, **kwargs):
    """
    This function creates a pre-processed file from the input data and stores it to S3
    :param model_config:
    :return: None
    """
    s3 = S3Hook(aws_conn_id='s3_test')
    s3.get_conn()
    #file_key = ti.xcom_pull(key="file_key", task_ids="get_modeling_data")
    file_key = kwargs['ti'].xcom_pull(task_ids="get_modeling_data")['file_key']
    logging.info(f"file_key = %s", file_key)

    input_file = s3.get_key(key=file_key, bucket_name='yt-ml-demo')
    df = pd.read_csv(io.BytesIO(input_file.get()['Body'].read()))

    # Do cleaning and pre processing
    binary_varlist = model_config.get("binary_map")

    if binary_varlist is not None:
        df[binary_varlist] = df[binary_varlist].apply(binary_map)

    ternary_varlist = model_config.get("ternary_map")

    if ternary_varlist is not None:
        df[ternary_varlist] = df[ternary_varlist].apply(ternary_map)


    if model_config.get("dummies") is not None:
        for dummy_col in model_config.get("dummies"):
            status = pd.get_dummies(df[dummy_col], drop_first=True)
            df = pd.concat([df, status], axis=1)
            df.drop([dummy_col], axis=1, inplace=True)

    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    s3.load_string(string_data=csv_buffer.getvalue(), key=f'pre_processed_data/{model_config.get("algo_name")}/pre_processed_file.csv', bucket_name='yt-ml-demo', replace=True)


def train_model(ml_config):
    """
    This function creates a trained model from the pre-processed data and stores the model to S3 as a pickle file
    :param ml_config:
    :return: None
    """
    pre_processed_file_key = f'pre_processed_data/{ml_config.get("algo_name")}/pre_processed_file.csv'

    input_file = s3.get_key(key=pre_processed_file_key, bucket_name='yt-ml-demo')
    df = pd.read_csv(io.BytesIO(input_file.get()['Body'].read()))

    df_train, df_test = train_test_split(df, train_size=0.7, test_size=0.3, random_state=100)

    y_train = df_train.pop(ml_config.get("y")).to_numpy()
    X_train = df_train.to_numpy()

    y_test = df_test.pop(ml_config.get("y")).to_numpy()
    X_test = df_test.to_numpy()

    model = eval(ml_config.get("algo_name") + '()')

    # Train model
    model.fit(X_train, y_train)

    s3_key = f'trained_models/{ml_config.get("algo_name")}/model.sav'

    # save the model to disk
    filename = 'finalized_model.sav'

    if s3.check_for_key(key=s3_key, bucket_name='yt-ml-demo'):
        s3.delete_objects(keys=s3_key, bucket='yt-ml-demo')

    pickle.dump(model, open(filename, 'wb'))
    s3.load_file(filename=filename, key=s3_key, bucket_name='yt-ml-demo')

    # Make predictions
    # TODO: Need to only train model in this func
    # TODO: making predictions and storing to S# should be done in the next func.
    # TODO: Update the script after making the code change.
    # y_pred = model.predict(X_test)
    #
    # final_op = []
    # for i in range(0, len(X_test)):
    #     a = np.insert(X_test[i], 4, y_pred[i])
    #     final_op.append(list(a))
    #
    # output_df = pd.DataFrame(final_op, columns=df.columns)
    # csv_buffer = StringIO()
    # output_df.to_csv(csv_buffer, index=False)
    # s3.load_string(string_data=csv_buffer.getvalue(), key=f'output_data/{ml_config.get("algo_name")}/output_file.csv', bucket_name='yt-ml-demo', replace=True)

    return


def get_model_predictions(ml_config):
    """
    This function reads a model from S3 and makes predictions
    :param ml_config:
    :return: None
    """
    pre_processed_file_key = f'pre_processed_data/{ml_config.get("algo_name")}/pre_processed_file.csv'

    input_file = s3.get_key(key=pre_processed_file_key, bucket_name='yt-ml-demo')
    df = pd.read_csv(io.BytesIO(input_file.get()['Body'].read()))

    df_train, df_test = train_test_split(df, train_size=0.7, test_size=0.3, random_state=100)

    y_test = df_test.pop(ml_config.get("y")).to_numpy()
    X_test = df_test.to_numpy()


    s3_key = f'trained_models/{ml_config.get("algo_name")}/model.sav'
    model_file = s3.get_key(key=s3_key, bucket_name='yt-ml-demo')
    model = pickle.loads(model_file.get()['Body'].read())

    # Make predictions
    y_pred = model.predict(X_test)
    print(f"y_pred = {y_pred}")
    col_name_list = df.columns.values.tolist()
    y_index = col_name_list.index(ml_config.get("y"))

    final_op = []
    for i in range(0, len(X_test)):
        a = np.insert(X_test[i], y_index, y_pred[i])
        final_op.append(list(a))


    output_df = pd.DataFrame(final_op, columns=df.columns)
    csv_buffer = StringIO()
    output_df.to_csv(csv_buffer, index=False)
    s3.load_string(string_data=csv_buffer.getvalue(), key=f'output_data/{ml_config.get("algo_name")}/output_file.csv', bucket_name='yt-ml-demo', replace=True)

    return


def generate_ml_dags(dag_id, ml_config, default_args):
    """
    :param dag_id: Id/name of the the DAG
    :param ml_config: config dictionary
    :param default_args:
    :return: the ML dag
    """

    retrieved_schedule = ml_config.get('schedule')
    # retrieved_ml_algo = ml_config.get('algo_name')
    dag = DAG(dag_id, schedule_interval=retrieved_schedule, default_args=default_args, catchup=False, tags=['ML'])
    with dag:

        check_for_file = PythonOperator(
            task_id='get_modeling_data',
            provide_context=True,
            python_callable=get_modeling_data,
            op_args=[ml_config],
            dag=dag
        )

        pre_process_data = PythonOperator(
            task_id='preprocess_and_clean_data',
            provide_context=True,
            python_callable=preprocess,
            op_args=[ml_config],
            dag=dag
        )
        check_for_file.set_downstream(pre_process_data)

        train_data = PythonOperator(
            task_id='train_data',
            provide_context=True,
            python_callable=train_model,
            op_args=[ml_config],
            dag=dag
        )
        pre_process_data.set_downstream(train_data)

        predict_data = PythonOperator(
            task_id='make_model_predictions',
            provide_context=True,
            python_callable=get_model_predictions,
            op_args=[ml_config],
            dag=dag
        )
        train_data.set_downstream(predict_data)

    return dag
