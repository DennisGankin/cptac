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

# Import necessary modules
import pandas as pd
from cptac.cancers.source import Source

class BcmLscc(Source):
    def __init__(self, no_internet=False):
        """Initializes the BcmLscc class by defining which bcmlscc dataframes are available in the self.load_functions dictionary variable, with names as keys.

        Parameters:
        no_internet (bool, optional): If True, skips the index update step because it requires an internet connection. Default is False.
        """

        # Define data files
        self.data_files = {
            "circular_RNA" : "LSCC-circRNA_rsem_tumor_normal_UQ_log2(x+1)_BCM.txt.gz",
            "mapping" : "gencode.v34.basic.annotation-mapping.txt.gz",
            "transcriptomics" : "LSCC-gene_rsem_removed_circRNA_tumor_normal_UQ_log2(x+1)_BCM.txt.gz"
        }
        
        # Define load functions
        self.load_functions = {
            'circular_RNA' : self.load_circular_RNA,
            'transcriptomics' : self.load_transcriptomics,
        }
        
        # Call the parent class __init__ function
        super().__init__(cancer_type="lscc", source='bcm', data_files=self.data_files, load_functions=self.load_functions, no_internet=no_internet)

    def load_circular_RNA(self):
        """Load circular RNA data."""

        df_type = 'circular_RNA'
        # Check if data is not loaded
        if df_type not in self._data:
            # perform initial checks and get file path (defined in source.py, the parent class)
            file_path = self.locate_files(df_type)
            
            # Load data and apply necessary transformations
            df = pd.read_csv(file_path, sep='\t')
            df = df.rename_axis('INDEX').reset_index()
            df[["circ","chrom","start","end","gene"]] = df.INDEX.str.split('_', expand=True)
            df["circ_chromosome"] = df["circ"] +"_" + df["chrom"]
            df = df.set_index('gene')
            
            # Add gene names to circular RNA data
            self.load_mapping()
            gene_key = self._helper_tables["gene_key"]
            df = gene_key.join(df, how = "inner")
            df = df.reset_index()
            df = df.rename(columns= {"gene_name": "Name", "gene": "Database_ID"}) # change names to match cptac package
            df = df.set_index(["Name","circ_chromosome", "start", "end", "Database_ID"]) #create multi-index
            df.drop(['INDEX', 'circ', 'chrom'], axis=1, inplace=True)
            df = df.sort_index()
            df = df.T
            df.index = df.index.str.replace(r"_T", "", regex=True) # remove Tumor label
            df.index = df.index.str.replace(r"_A", ".N", regex=True)# Normal samples labeled with .N
            df.index.name = "Patient_ID"

            # save df in self._data
            self.save_df(df_type, df)

    def load_mapping(self):
        """Load mapping data. This method is used by other loading methods to map gene names."""

        df_type = 'mapping'
        # Check if helper tables are not loaded
        if not self._helper_tables:
            file_path = self.locate_files(df_type)
            
            # Load data and apply necessary transformations
            df = pd.read_csv(file_path, sep='\t')
            df = df[["gene","gene_name"]] #only need gene (database gene id) and gene_name (common gene name)
            df = df.set_index("gene")
            df = df.drop_duplicates()
            self._helper_tables["gene_key"] = df

    def load_transcriptomics(self):
        """Load transcriptomics data."""

        df_type = 'transcriptomics'

        # Check if data is not loaded
        if df_type not in self._data:
            # perform initial checks and get file path (defined in source.py, the parent class)
            file_path = self.locate_files(df_type)
            
            # Load data and apply necessary transformations
            df = pd.read_csv(file_path, sep='\t')
            df.index.name = 'gene'
            
            # Add gene names to transcriptomic data
            self.load_mapping()
            gene_key = self._helper_tables["gene_key"]
            transcript = gene_key.join(df, how = "inner") #keep only gene_ids with gene names
            transcript = transcript.reset_index()
            transcript = transcript.rename(columns={"gene_name":"Name","gene":"Database_ID"})
            transcript = transcript.set_index(["Name", "Database_ID"])
            transcript = transcript.sort_index() #alphabetize
            transcript = transcript.T
            transcript.index = transcript.index.str.replace(r"_T", "", regex=True)
            transcript.index = transcript.index.str.replace(r"_A", ".N", regex=True)# Normal samples labeled with .N
            transcript.index.name = "Patient_ID"

            df = transcript
            # save df in self._data
            self.save_df(df_type, df)
