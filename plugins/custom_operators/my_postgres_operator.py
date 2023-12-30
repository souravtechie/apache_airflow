from typing import TYPE_CHECKING, Iterable, Mapping, Optional, Sequence, Union
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.hooks.S3_hook import S3Hook

if TYPE_CHECKING:
    from airflow.utils.context import Context

class MyPostgresOperator(PostgresOperator):
    def __init__(
        self,
        sql,
        postgres_conn_id='postgres_default',
        full_s3_key=None,
        pg_table_name=None,
        column_list=None,
        aws_conn_id='aws_default',
        **kwargs,
    ) -> None:
        self.sql = sql
        self.postgres_conn_id = postgres_conn_id
        super().__init__(sql=self.sql, postgres_conn_id=self.postgres_conn_id, **kwargs)
        self.full_s3_key = full_s3_key
        self.aws_conn_id = aws_conn_id
        self.pg_table_name = pg_table_name
        self.column_list = column_list

    def execute(self, context: 'Context'):
        if self.pg_table_name is not None and self.full_s3_key is not None:
            # call that func
            print('hi')
            self.pg_hook = PostgresHook(postgres_conn_id=self.postgres_conn_id, schema=self.database)
            s3_hook = S3Hook(aws_conn_id=self.aws_conn_id)

            bucket_name = self.full_s3_key.split('/')[0]
            s3_key = self.full_s3_key.replace(bucket_name + '/', '')
            local_file = s3_hook.download_file(key=s3_key, bucket_name=bucket_name,
                                               local_path='local/', preserve_file_name=True)

            print(f'type of local file = {type(local_file)}')
            print(f'Local file = {local_file}')

            pg_conn = self.pg_hook.get_conn()
            pg_cursor = pg_conn.cursor()

            with open(local_file, 'r') as f:
                print(f'file contents are: {f.read()}')

            pg_cursor.copy_from(open(local_file, 'r'), self.pg_table_name, sep=',',
                                columns=self.column_list)
            pg_conn.commit()
            pg_conn.close()
        else:
            super().execute(context)
