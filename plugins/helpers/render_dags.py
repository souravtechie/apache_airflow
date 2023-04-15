import io
import logging
from io import StringIO # python3; python2: BytesIO

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
from sklearn.preprocessing import MinMaxScaler

# tasks: get_training_data_from_s3, train_model, put_predicted_data_to_s3

# Load dataset
iris = data_sets.load_iris()
X, y = iris['data'], iris['target']


# TODO: paramterize the get_files func (rename func)
# TODO: write output to S3
# TODO: basic transformation on input data
s3 = S3Hook(aws_conn_id='s3_test')
s3.get_conn()

def get_modeling_data(model_name, **kwargs):

    bucket = s3.get_bucket(
        bucket_name='yt-ml-demo'
    )
    # files = s3.list_keys(bucket_name='yt-ml-demo', prefix='input_data/')
    key = f'input_data/{model_name}/input_file.csv'
    input_file = s3.check_for_key(key=key, bucket_name='yt-ml-demo')

    if input_file:
        return {"file_key": key}

    else:
        return None


def binary_map(x):
    return x.map({'yes': 1, "no": 0})


def preprocess(model_name, **kwargs):
    """

    :param ti:
    :return:
    """
    s3 = S3Hook(aws_conn_id='s3_test')
    s3.get_conn()
    #file_key = ti.xcom_pull(key="file_key", task_ids="get_modeling_data")
    file_key = kwargs['ti'].xcom_pull(task_ids="get_modeling_data")['file_key']
    print(f"file_key = {file_key}")

    input_file = s3.get_key(key=file_key, bucket_name='yt-ml-demo')
    df = pd.read_csv(io.BytesIO(input_file.get()['Body'].read()))

    # Do cleaning and pre processing
    varlist = ['mainroad', 'guestroom', 'basement', 'hotwaterheating', 'airconditioning', 'prefarea']

    # Applying the function to the housing list
    df[varlist] = df[varlist].apply(binary_map)

    status = pd.get_dummies(df['furnishingstatus'], drop_first=True)
    print(f"status = {status}")
    df = pd.concat([df, status], axis=1)
    df.drop(['furnishingstatus'], axis=1, inplace=True)

    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False)
    s3.load_string(string_data=csv_buffer.getvalue(), key=f'pre_processed_data/{model_name}/pre_processed_file.csv', bucket_name='yt-ml-demo', replace=True)
    print(f"df = {df}")



def train_model(model_name, **kwargs):
    """

    :param ti:
    :return:
    """
    pre_processed_file_key = f'pre_processed_data/{model_name}/pre_processed_file.csv'

    input_file = s3.get_key(key=pre_processed_file_key, bucket_name='yt-ml-demo')
    df = pd.read_csv(io.BytesIO(input_file.get()['Body'].read()))

    df_train, df_test = train_test_split(df, train_size=0.7, test_size=0.3, random_state=100)
    # scaler = MinMaxScaler()
    # num_vars = ['area', 'bedrooms', 'bathrooms', 'stories', 'parking', 'price']
    # df_train[num_vars] = scaler.fit_transform(df_train[num_vars])

    y_train = df_train.pop('price').to_numpy()
    X_train = df_train.to_numpy()

    y_test = df_test.pop('price').to_numpy()
    X_test = df_test.to_numpy()

    print(f"X_train = \n{len(X_train)}")
    print(f"y_train = \n{len(y_train)}")
    print(f"X_test = \n{len(X_test)}")
    print(f"y_test = \n{len(y_test)}")


    model = eval(model_name + '()')

    # Train model
    model.fit(X_train, y_train)

    # Make predictions
    y_pred = model.predict(X_test)
    #y_pred = pd.DataFrame(y_pred, columns=['price'])
    final_op = []
    for i in range(0, len(X_test)):
        a = np.insert(X_test[i], 4, y_pred[i])
        final_op.append(list(a))

    print(f"final_op = {final_op}, \nlen = {len(final_op)}")

    output_df = pd.DataFrame(final_op, columns=df.columns)
    print(f"y_pred = {len(y_pred)}, output_df=\n{output_df.count()}")

    csv_buffer = StringIO()
    output_df.to_csv(csv_buffer, index=False)
    s3.load_string(string_data=csv_buffer.getvalue(), key=f'output_data/{model_name}/output_file.csv', bucket_name='yt-ml-demo', replace=True)
    return


def get_model_predictions():
    return


def ml_model_predictions(X, y, test_size, model_name):
    """

    :param X: Input Numpy array
    :param y: Output
    :param model_name:
    :param test_size:
    :return:
    """
    print(iris)

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

    # return df


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
        check_for_file = PythonOperator(
            task_id='get_modeling_data',
            provide_context=True,
            python_callable=get_modeling_data,
            op_args=[ml_config.get('algo_name')],
            dag=dag
        )

        pre_process_data = PythonOperator(
            task_id='preprocess_and_clean_data',
            provide_context=True,
            python_callable=preprocess,
            op_args=[ml_config.get('algo_name')],
            dag=dag
        )
        check_for_file.set_downstream(pre_process_data)

        train_data = PythonOperator(
            task_id='train_data',
            provide_context=True,
            python_callable=train_model,
            op_args=[ml_config.get('algo_name')],
            dag=dag
        )
        pre_process_data.set_downstream(train_data)

    return dag
