#   Copyright 2018 Samuel Payne sam_payne@byu.edu
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#       http://www.apache.org/licenses/LICENSE-2.0
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import pandas as pd
import numpy as np
import os
import warnings

from cptac.cancer import Source
from cptac.tools.dataframe_tools import *

class BcmBrca(Source):

    def __init__(self, version="latest", no_internet=False):
        """Define which bcmbrca dataframes as are available in the self.load_functions dictionary variable, with names as keys.

        Parameters:
        version (str, optional): The version number to load, or the string "latest" to just load the latest datafreeze. Default is "latest".
        no_internet (bool, optional): Whether to skip the index update step because it requires an internet connection. This will be skipped automatically if there is no internet at all, but you may want to manually skip it if you have a spotty internet connection. Default is False.
        """

        # Set some needed variables, and pass them to the parent Dataset class __init__ function

        # This keeps a record of all versions that the code is equipped to handle. That way, if there's a new data release but they didn't update their package, it won't try to parse the new data version it isn't equipped to handle.
        self.valid_versions = ["1.0"]

        self.data_files = {
            "1.0": {
                "transcriptomics" : "BRCA-gene_RSEM_tumor_normal_UQ_log2(x+1)_BCM.txt", 
                "mapping" : "gencode.v34.basic.annotation-mapping.txt"
            }
        }
        
        self.load_functions = {
            'transcriptomics' : self.load_transcriptomics,
        }
        
        if version == "latest":
            version = sorted(self.valid_versions)[-1]

        # Call the parent class __init__ function
        super().__init__(cancer_type="brca", source='bcm', version=version, valid_versions=self.valid_versions, data_files=self.data_files, no_internet=no_internet)

        
    def load_mapping(self):
        df_type = 'mapping'
        # self._helper_tables is a dictionary of helpful dataframes that the user does not need to access
        # dataframes here are used to load the other data types, but don't show up when the user lists available data
        # this way mapping only needs to be loaded once and all other types can use it when they are loaded
        if df_type not in self._helper_tables:
            
            file_path = self.perform_initial_checks(df_type)
            
            df = pd.read_csv(file_path, sep="\t")
            df = df[["gene","gene_name"]] #only need gene (database gene id) and gene_name (common gene name)
            df = df.set_index("gene")
            df = df.drop_duplicates()
            self._helper_tables["gene_key"] = df 
            
        
    def load_transcriptomics(self):
        """Load and parse all files for bcm brca transcriptomics data
           Populates self._data with transcriptomics data in a Pandas dataframe
        """
        df_type = 'transcriptomics'
        if df_type not in self._data:
            # get file path to the correct data (defined in source.py, the parent class)
            file_path = self.perform_initial_checks(df_type)

            # process the file and add it to self._data
            df = pd.read_csv(file_path, sep='\t')
            df.index.name = 'gene'
            # in order to finish parsing the file we need mapping information (the gene_key)
            # make sure self._helper_tables has gene_key parsed and loaded
            self.load_mapping()
            # get gene key to use for transcriptomics
            gene_key = self._helper_tables["gene_key"]
            transcript = gene_key.join(df,how = "inner") #keep only gene_ids with gene names
            transcript = transcript.reset_index()
            transcript = transcript.rename(columns={"gene_name":"Name","gene":"Database_ID"})
            transcript = transcript.set_index(["Name", "Database_ID"])
            transcript = transcript.sort_index() #alphabetize
            transcript = transcript.T
            transcript.index.name = "Patient_ID"
            self._data["transcriptomics"] = transcript
            
            
            
    # Last hitch in the road
    self._data = sort_all_rows_pancan(self._data)  # Sort IDs (tumor first then normal)
