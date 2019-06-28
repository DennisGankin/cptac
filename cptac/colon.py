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

import numpy as np
import pandas as pd
import os
import glob
from .dataset import DataSet
from .sync import get_version_files_paths

class Colon(DataSet):

    def __init__(self, version="latest"):
        """Load all of the colon dataframes as values in the self._data dict variable, with names as keys, and format them properly."""

        # Call the parent DataSet __init__ function, which initializes self._data and other variables we need
        super().__init__()

        # Set the _cancer_type instance variable
        self._cancer_type = "colon"

        # Overload the gene separator for column names in the phosphoproteomics dataframe. In the colon data, it's an underscore, not a dash like most datasets.
        self._gene_separator = "_"

        # Get the paths to all the data files
        data_files = [
            "clinical.tsi.gz",
            "miRNA.cct.gz",
            "mutation_binary.cbt.gz",
            "mutation.txt.gz",
            "phosphoproteomics_normal.gz",
            "phosphoproteomics_tumor.gz",
            "proteomics_normal.cct.gz",
            "proteomics_tumor.cct.gz",
            "transcriptomics.gz"]
        data_files_paths = get_version_files_paths(self._cancer_type, version, data_files)
        if data_files_paths is None: # Version validation error. get_version_files_paths already printed an error message.
            return None

        # Load the data into dataframes in the self._data dict
        for file_path in data_files_paths: # Loops through files variable
            path_elements = file_path.split(os.sep) # Get a list of the levels of the path
            file_name = path_elements[-1] # The last element will be the name of the file
            file_name_split = file_name.split(".")
            df_name = file_name_split[0] # Our dataframe name will be the first section of file name (i.e. proteomics.txt.gz becomes proteomics)

            # Load the file, based on what it is
            print("Loading {} data...".format(df_name), end='\r') # Carriage return ending causes previous line to be erased.

            if file_name == "mutation.txt.gz":
                df = pd.read_csv(file_path, sep="\t")
                df = df.sort_values(by="SampleID")
                df = df[["SampleID","Gene","Variant_Type","Protein_Change"]]
                df = df.rename({"Variant_Type":"Mutation","Protein_Change":"Location"},axis="columns")
                df.name = "somatic_" + df_name
                self._data[df.name] = df # Maps dataframe name to dataframe. self._data was initialized when we called the parent class __init__()

            else:
                df = pd.read_csv(file_path, sep="\t",index_col=0)
                df = df.transpose()
                df.name = df_name
                self._data[df.name] = df # Maps dataframe name to dataframe. self._data was initialized when we called the parent class __init__()

            print("\033[K", end='\r') # Use ANSI escape sequence to clear previously printed line (cursor already reset to beginning of line with \r)

        print("Formatting dataframes...", end="\r")

        # Rename mutation_binary dataframe to somatic_mutation_binary
        df = self._data["mutation_binary"]
        df.name = "somatic_mutation_binary"
        self._data["somatic_mutation_binary"] = df
        del self._data["mutation_binary"]

        # Separate clinical and derived molecular dataframes
        all_clinical_data = self._data.get("clinical")
        clinical_df = all_clinical_data.drop(columns=['StromalScore', 'ImmuneScore', 'ESTIMATEScore', 'TumorPurity','immuneSubtype', 'CIN', 'Integrated.Phenotype'])
        clinical_df.name = "clinical"
        derived_molecular_df = all_clinical_data[['StromalScore', 'ImmuneScore', 'ESTIMATEScore', 'TumorPurity', 'immuneSubtype', 'CIN', 'Integrated.Phenotype']]
        derived_molecular_df.name = "derived_molecular"

        # Put them in our data dictionary
        self._data["clinical"] = clinical_df # Replaces original clinical dataframe
        self._data["derived_molecular"] = derived_molecular_df

        # Combine the two proteomics dataframes
        prot_tumor = self._data.get("proteomics_tumor")
        prot_normal = self._data.get("proteomics_normal") # Normal entries are marked with 'N' on the end of the ID
        prot_combined = prot_tumor.append(prot_normal)
        prot_combined.name = "proteomics"
        self._data[prot_combined.name] = prot_combined
        del self._data["proteomics_tumor"]
        del self._data["proteomics_normal"]

        # Get phosphoproteomics dataframes, so we can process and combine them
        phos_tumor = self._data.get("phosphoproteomics_tumor")
        phos_normal = self._data.get("phosphoproteomics_normal") # Normal entries are not marked

        # Mark entries in phosphoproteomics_normal dataframe with an N at the end of the ID, to match proteomics_normal
        phos_normal_indicies = phos_normal.index.values.tolist()
        for i in range(len(phos_normal_indicies)):
            index = phos_normal_indicies[i]
            index_marked = index + 'N'
            phos_normal_indicies[i] = index_marked
        new_phos_index = pd.Index(phos_normal_indicies)
        phos_normal = phos_normal.set_index(new_phos_index)

        # Combine the two phosphoproteomics dataframes into one dataframe
        phos_combined = phos_tumor.append(phos_normal)
        phos_combined = phos_combined.rename(columns=lambda x: x.split(":")[0]) # Drop everything after ":" in column names--unneeded additional identifiers
        phos_combined = phos_combined.sort_index(axis=1) # Put all the columns in alphabetical order
        phos_combined.name = 'phosphoproteomics'
        self._data[phos_combined.name] = phos_combined
        del self._data["phosphoproteomics_tumor"]
        del self._data["phosphoproteomics_normal"]

        # Rename the somamtic_mutation dataframe's "SampleID" column to "PatientID", then set that as the index, to match the other dataframes
        new_somatic = self._data["somatic_mutation"]
        new_somatic = new_somatic.rename(columns={"SampleID":"Patient_ID"})
        new_somatic = new_somatic.set_index("Patient_ID")
        new_somatic.name = "somatic_mutation"
        self._data["somatic_mutation"] = new_somatic

        # Get a union of all dataframes' indicies, with duplicates removed
        indicies = [df.index for df in self._data.values()]
        master_index = pd.Index([])
        for index in indicies:
            master_index = master_index.union(index)
            master_index = master_index.drop_duplicates()

        # Sort this master_index so all the samples with an N suffix are last. Because the N is a suffix, not a prefix, this is kind of messy.
        status_df = pd.DataFrame(master_index, columns=['Patient_ID']) # Create a new dataframe with the master_index as a column called "Patient_ID"
        status_col = []
        for index in master_index:
            if index[-1] == 'N':
                status_col.append("Normal")
            else:
                status_col.append("Tumor")
        status_df = status_df.assign(Status=status_col)
        status_df = status_df.sort_values(by=['Status', 'Patient_ID'], ascending=[False, True]) # Sorts first by status, and in descending order, so "Tumor" samples are first
        master_index = status_df["Patient_ID"].tolist()

        # Use the master index to reindex the clinical dataframe, so the clinical dataframe has a record of every sample in the dataset. Rows that didn't exist before (such as the rows for normal samples) are filled with NaN.
        master_clinical = self._data['clinical'].reindex(master_index)
        master_clinical.name = self._data["clinical"].name

        # Add a column called Sample_Tumor_Normal to the clinical dataframe indicating whether each sample is a tumor or normal sample. Samples with a Patient_ID ending in N are normal.
        clinical_status_col = []
        for sample in master_clinical.index:
            if sample[-1] == 'N':
                clinical_status_col.append("Normal")
            else:
                clinical_status_col.append("Tumor")
        master_clinical.insert(0, "Sample_Tumor_Normal", clinical_status_col)

        # Replace the clinical dataframe in the data dictionary with our new and improved version!
        self._data['clinical'] = master_clinical 

        # Generate a sample ID for each patient ID
        sample_id_dict = {}
        for i in range(len(master_index)):
            patient_id = master_index[i]
            sample_id_dict[patient_id] = "S{:0>3}".format(i + 1) # Use string formatter to give each sample id the format S*** filled with zeroes, e.g. S001, S023, or S112

        # Give all the dataframes Sample_ID indicies
        for name in self._data.keys(): # Only loop over keys, to avoid changing the structure of the object we're looping over
            df = self._data[name]
            sample_id_column = []

            map_failed = False
            for row in df.index:
                if row in sample_id_dict.keys():
                    sample_id_column.append(sample_id_dict[row])
                else:
                    print("Error mapping sample ids in {0} dataframe. Patient_ID {1} did not have corresponding Sample_ID mapped in clinical dataframe. {0} dataframe not loaded.".format(df.name, row))
                    map_failed = True
            if map_failed:
                del self._data[name]
                continue

            df = df.assign(Sample_ID=sample_id_column)
            old_index_name = df.index.name
            if old_index_name is None:
                old_index_name = 'index' # If the current index doesn't have a name, the column it's put in when we do reset_index will have the default name of 'index'
            df = df.reset_index() # This gives the dataframe a default numerical index and makes the old index a column, which prevents it from being dropped when we set Sample_ID as the index.
            df = df.rename(columns={old_index_name:'Patient_ID'}) # Rename the old index as Patient_ID
            df = df.set_index('Sample_ID') # Make the Sample_ID column the index, which also drops the default numerical index from reset_index
            df = df.sort_index()
            df.name = name
            self._data[name] = df

        # Drop Patient_ID column from dataframes other than clinical. Keep it in clinical, so we have a mapping of Sample_ID to Patient_ID for every sample
        for name in self._data.keys():
            if name != "clinical":
                df = self._data[name]
                df = df.drop(columns="Patient_ID")
                df.name = name
                self._data[name] = df

        # Drop name of column axis for all dataframes
        for name in self._data.keys():
            df_rename_col_axis = self._data[name]
            df_rename_col_axis.columns.name = None
            self._data[name] = df_rename_col_axis

        # Use ANSI escape sequence to clear previously printed line (cursor already reset to beginning of line with \r)
        print("\033[K", end='\r') 

    # Overload the default how_to_cite function, to provide the specific publication information for the Colon dataset
    def how_to_cite(self):
        """Print instructions for citing the data."""
        print('Please include the following statement in publications using colon cancer data accessed through this module:\n"Data used in this publication were generated by the Clinical Proteomic Tumor Analysis Consortium (NCI/NIH, <https://proteomics.cancer.gov/programs/cptac/>). Data were published at <https://www.ncbi.nlm.nih.gov/pubmed/31031003>. Data were accessed through the Python module cptac, available at <https://pypi.org/project/cptac/>."')
