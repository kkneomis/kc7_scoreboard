# Import external modules
from inspect import istraceback
from multiprocessing.dummy import Process
from flask import Flask, abort
import pandas as pd
import json
from azure.kusto.data import KustoClient, KustoConnectionStringBuilder
from azure.kusto.data.exceptions import KustoServiceError
from azure.kusto.data.helpers import dataframe_from_result_table
from azure.kusto.data.data_format import DataFormat
from azure.kusto.ingest import QueuedIngestClient, IngestionProperties, FileDescriptor, BlobDescriptor, ReportLevel, ReportMethod
from flask import current_app
from azure.kusto.data.helpers import dataframe_from_result_table



class LogUploader():
    """
    Object allows us to upload data to azure
    Logs are batched and uploaded to their corresponding table after queue is full
    First: ingestion properties are read from the flaks config in Config.py

    see: https://github.com/Azure/azure-kusto-python/blob/master/azure-kusto-ingest/tests/sample.py
    """

    def __init__(self, queue_limit=1000):
        # set Azure tenant config variables

        if not current_app.config["ADX_DEBUG_MODE"]:
            self.AAD_TENANT_ID = current_app.config["AAD_TENANT_ID"]
            self.KUSTO_URI = current_app.config["KUSTO_URI"]
            self.KUSTO_INGEST_URI = current_app.config["KUSTO_INGEST_URI"]
            self.DATABASE = current_app.config["DATABASE"]
    
            # Aauthenticate with AAD application.
            self.client_id = current_app.config["CLIENT_ID"]
            self.client_secret = current_app.config["CLIENT_SECRET"]


            # authentication for ingestion client
            kcsb_ingest = KustoConnectionStringBuilder.with_aad_application_key_authentication(self.KUSTO_INGEST_URI,
                                                                                            self.client_id, self.client_secret, self.AAD_TENANT_ID)

            # authentication for general client
            kcsb_data = KustoConnectionStringBuilder.with_aad_application_key_authentication(self.KUSTO_URI,
                                                                                            self.client_id, self.client_secret, self.AAD_TENANT_ID)
        
            #TODO handle errors here
            self.ingest = QueuedIngestClient(kcsb_ingest)
            self.client = KustoClient(kcsb_data)
        
     

            # The queue will allow us to upload multiple rows at once
            # This allows the game to runs faster and enable us to make fewer API calls
            # self.queue will be in the format:
            # {
            #   "table_name": [dict, dict, dict],
            #   "table_name2": [dict, dict, dict]
            # }
            self.queue = {}
            # how many records do we hold until submitting everything to kusto
            self.queue_limit = queue_limit
        else:
            print("Running in DEBUG MODE...NO NEED TO INITIALIZE KUSTO")



    @staticmethod
    def _create_user_permission_command(user_string:str, database: str) -> str:
        """
        Take a user string of the following format:
        aaduser=user@contoso.com
        msauser=user@outlook.com
        """
        # Does the user_string contain one of the required identifiers?
        if not any(prefix in user_string for prefix in ['aaduser=','msauser=']):
            raise Exception("ERROR: The user identifier must be prefixed by either aaduser= or msauser=")
        return f".add database {database} viewers ('{user_string}')"

    def get_user_permissions(self) -> list:
        """
        Get a list of user permissions from ADX
        """
        show_permissions_command = f".show database {self.DATABASE} principals | distinct PrincipalDisplayName"
        response = self.client.execute_mgmt(self.DATABASE, show_permissions_command)

        # Handle errors from Kusto Client
        if response.get_exceptions():
            raise response.get_exceptions()

        return dataframe_from_result_table(response.primary_results[0])['PrincipalDisplayName'].unique().tolist()


    def add_user_permissions(self, user_string: str) -> None:
        permission_command = LogUploader._create_user_permission_command(user_string, self.DATABASE)
        response = self.client.execute_mgmt(self.DATABASE, permission_command)
        # Raise any errors that come back from 
        if response.get_exceptions():
            raise response.get_exceptions()

   
    def get_queue_length(self):
        """
        Get the number of records stored in the queue
        this does a sum of lengths for lists under each tablename key
        """
        return sum([len(val) for key, val in self.queue.items()])

    def send_request(self, data: dict, table_name: str) -> None:
        """
        Data is ingested as JSON
        convert to a pandas dataframe and upload to KUSTO
        """

        # put data in a dataframe for ingestion
        if isinstance(data, list):
            data = data[0]

        # Add the data to the queue
        # Data is appended to a list under table_name key in self.queue
        # e.g. {
        #    "table_name": [data]
        # }
        if table_name in self.queue:
            self.queue[table_name].append(data)
        else:
            self.queue[table_name] = [data]

        # reached the queue limit
        # submit all existing records and clear the queue
        if self.get_queue_length() > self.queue_limit:
            for table_name, data in self.queue.items():
                self.ingestion_props = IngestionProperties(
                    database=self.DATABASE,
                    table=table_name,
                    data_format=DataFormat.CSV,
                    report_level=ReportLevel.FailuresAndSuccesses
                )

                # turn list of rows in a dataframe
                # TODO: sort by time before uploading -
                #   need to first standardize time columns accross tables
                data_table_df = pd.DataFrame(self.queue[table_name])
                
                try:
                    # if possible sort value using the "timestamp" column
                    data_table_df = data_table_df.sort_values("timestamp", ascending=True)
                except:
                    pass

                print(f"uploading data for type {table_name}")
                print(data_table_df.shape)

                if current_app.config["ADX_DEBUG_MODE"]:
                    # If ADX_DEBUG_MODE is enabled, print JSON representation of data
                    # Then, return early to prevent queueing and uploading to ADX
                    print(f"Uploading to table {table_name}...")

                    print(data_table_df.to_markdown())
                else:
                    # submit logs to Kusto
                    result = self.ingest.ingest_from_dataframe(
                        data_table_df, ingestion_properties=self.ingestion_props)
                    print(result)
                    print(f"....adding data to azure for {table_name} table")

            # reset the quee
            self.queue = {}