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
import datetime

from cptac.dataset import Dataset
from cptac.dataframe_tools import *
from cptac.exceptions import FailedReindexWarning, PublicationEmbargoWarning, ReindexMapError


class UmichCoad(Dataset):

    def __init__(self, no_internet, version):
        """Load all of the umichcoad dataframes as values in the self._data dict variable, with names as keys, and format them properly.

        Parameters:
        version (str, optional): The version number to load, or the string "latest" to just load the latest building. Default is "latest".
        no_internet (bool, optional): Whether to skip the index update step because it requires an internet connection. This will be skipped automatically if there is no internet at all, but you may want to manually skip it if you have a spotty internet connection. Default is False.
        """

        # Set some needed variables, and pass them to the parent Dataset class __init__ function

        # This keeps a record of all versions that the code is equipped to handle. That way, if there's a new data release but they didn't update their package, it won't try to parse the new data version it isn't equipped to handle.
        valid_versions = ["1.0", "1.1"]

        data_files = {
            "1.0": ["Report_abundance_groupby=protein_protNorm=MD_gu=2.tsv",
                    "Report_abundance_groupby=multi-site_protNorm=MD_gu=2.tsv",
                    "CRC_Prospective sample info.xlsx"
                #"S039_BCprospective_observed_0920.tsv.gz",
                #"S039_BCprospective_imputed_0920.tsv.gz"
            ],
            
            "1.1": ["Report_abundance_groupby=protein_protNorm=MD_gu=2.tsv",
                    "Report_abundance_groupby=multi-site_protNorm=MD_gu=2.tsv",
                    "CRC_Prospective sample info.xlsx"
            ]
        }

        # Call the parent class __init__ function
        super().__init__(cancer_type="umichcoad", version=version, valid_versions=valid_versions, data_files=data_files, no_internet=no_internet)

        # Load the data into dataframes in the self._data dict
        loading_msg = f"Loading {self.get_cancer_type()} v{self.version()}"
        for file_path in self._data_files_paths: # Loops through files variable

            # Print a loading message. We add a dot every time, so the user knows it's not frozen.
            loading_msg = loading_msg + "."
            print(loading_msg, end='\r')

            path_elements = file_path.split(os.sep) # Get a list of the levels of the path
            file_name = path_elements[-1] # The last element will be the name of the file. We'll use this to identify files for parsing in the if/elif statements below
            
            # Proteomics
            if file_name == "Report_abundance_groupby=protein_protNorm=MD_gu=2.tsv":
                df = pd.read_csv(file_path, sep = "\t")
                df['Database_ID'] = df.Index.apply(lambda x: x.split('|')[0]) # Get protein identifier 
                df['Name'] = df.Index.apply(lambda x: x.split('|')[6]) # Get protein name 
                df = df.set_index(['Name', 'Database_ID']) # set multiindex
                df = df.drop(columns = ['Index', 'MaxPepProb', 'NumberPSM', 'Gene']) # drop unnecessary  columns
                df = df.transpose()
                ref_intensities = df.loc["ReferenceIntensity"] # Get reference intensities to use to calculate ratios 
                df = df.subtract(ref_intensities, axis="columns") # Subtract reference intensities from all the values
                df = df.iloc[1:,:] # drop ReferenceIntensity row 
                df.index.name = 'Patient_ID'

                drop_cols = ['colonRef22-2', 'RefInt_ColonRef01', 'RefInt_ColonRef02',
                   'RefInt_ColonRef03', 'RefInt_ColonRef04', 'RefInt_ColonRef05',
                   'RefInt_ColonRef06', 'RefInt_ColonRef07', 'RefInt_ColonRef08',
                   'RefInt_ColonRef09', 'RefInt_ColonRef10', 'RefInt_ColonRef11',
                   'RefInt_ColonRef12', 'RefInt_ColonRef13', 'RefInt_ColonRef14',
                   'RefInt_ColonRef15', 'RefInt_ColonRef16', 'RefInt_ColonRef17',
                   'RefInt_ColonRef18', 'RefInt_ColonRef19', 'RefInt_ColonRef20',
                   'RefInt_ColonRef21', 'RefInt_ColonRef22-1']
                
                # Drop qauality control and ref intensity cols
                df = df.drop(drop_cols, axis = 'index')
                self._data["proteomics"] = df              
                
            
            # Phosphoproteomics
            elif file_name == "Report_abundance_groupby=multi-site_protNorm=MD_gu=2.tsv":
                df = pd.read_csv(file_path, sep = "\t") 
                # Parse a few columns out of the "Index" column that we'll need for our multiindex
                df[['Database_ID','Transcript_ID',"Gene_ID","Havana_gene","Havana_transcript","Transcript","Name","Site"]] = df.Index.str.split("\\|",expand=True)
                df[['num1','start',"end","detected_phos","localized_phos","Site"]] = df.Site.str.split("_",expand=True) 

                 # Some rows have at least one localized phosphorylation site, but also have other phosphorylations that aren't localized. We'll drop those rows, if their localized sites are duplicated in another row, to avoid creating duplicates, because we only preserve information about the localized sites in a given row. However, if the localized sites aren't duplicated in another row, we'll keep the row.
                unlocalized_to_drop = df.index[~df["detected_phos"].eq(df["localized_phos"]) & df.duplicated(["Name", "Site", "Peptide", "Database_ID"], keep=False)]# dectected_phos of the split "Index" column is number of phosphorylations detected, and localized_phos is number of phosphorylations localized, so if the two values aren't equal, the row has at least one unlocalized site
                df = df.drop(index=unlocalized_to_drop)

                df = df[df['Site'].notna()] # only keep columns with phospho site 
                df = df.set_index(['Name', 'Site', 'Peptide', 'Database_ID']) # This will create a multiindex from these columns, in this order.
                #drop columns not needed in df 
                df.drop([ 'Gene', "Index","num1","start","end","detected_phos","localized_phos","Havana_gene","Havana_transcript","MaxPepProb","Gene_ID","Transcript_ID","Transcript"], axis=1, inplace=True)

                df = df.T #transpose df 
                ref_intensities = df.loc["ReferenceIntensity"]# Get reference intensities to use to calculate ratios 
                df = df.subtract(ref_intensities, axis="columns") # Subtract reference intensities from all the values, to get ratios
                df = df.iloc[1:,:] # drop ReferenceIntensity row 
                drop_cols = ['colonRef22-2', 'RefInt_ColonRef01', 'RefInt_ColonRef02',
                   'RefInt_ColonRef03', 'RefInt_ColonRef04', 'RefInt_ColonRef05',
                   'RefInt_ColonRef06', 'RefInt_ColonRef07', 'RefInt_ColonRef08',
                   'RefInt_ColonRef09', 'RefInt_ColonRef10', 'RefInt_ColonRef11',
                   'RefInt_ColonRef12', 'RefInt_ColonRef13', 'RefInt_ColonRef14',
                   'RefInt_ColonRef15', 'RefInt_ColonRef16', 'RefInt_ColonRef17',
                   'RefInt_ColonRef18', 'RefInt_ColonRef19', 'RefInt_ColonRef20',
                   'RefInt_ColonRef21', 'RefInt_ColonRef22-1']
                # Drop qauality control and ref intensity cols
                df = df.drop(drop_cols, axis = 'index')
                df.index.name = 'Patient_ID'
                self._data["phosphoproteomics"] = df
            
            # mapping file to get patient_IDs
            elif file_name == "CRC_Prospective sample info.xlsx":
                df = pd.read_excel(file_path)
                df = df[['Label','Sample Code']]
                self._helper_tables["map_ids"] = df

            '''
            if file_name == "S039_BCprospective_observed_0920.tsv.gz":
                df = pd.read_csv(file_path, sep="\t")
                df = df.transpose()
                df.index.name = 'Patient_ID'
                df.columns.name = 'Name'
                df = average_replicates(df)
                df = df.sort_values(by=["Patient_ID"])
                self._data["proteomics"] = df  
                
            if file_name == "S039_BCprospective_imputed_0920.tsv.gz":
                df = pd.read_csv(file_path, sep="\t")
                df = df.transpose()
                df.index.name = 'Patient_ID'
                df.columns.name = 'Name'
                df = average_replicates(df)
                df = df.sort_values(by=["Patient_ID"])
                self._data["proteomics_imputed"] = df'''
                
          
        print(' ' * len(loading_msg), end='\r') # Erase the loading message
        formatting_msg = "Formatting dataframes..."
        print(formatting_msg, end='\r')
        
        if self._version == "1.1": 
            # Proteomics
            # Get Patient_IDs
            prot = self._data['proteomics']
            mapping_df = self._helper_tables['map_ids']
            index_list = list(prot.index)
            cancer_df = mapping_df.loc[mapping_df['Label'].isin(index_list)]
            # Create dictionary with labels as keys and sample code (case_ID with sample identifier) as values
            matched_ids = {}
            for i, row in cancer_df.iterrows():
                matched_ids[row['Label']] = row['Sample Code']
            prot = prot.reset_index()
            prot = prot.replace(matched_ids) # replace label with Patient_IDs
            prot.Patient_ID = prot.Patient_ID.apply(lambda x: x[1:]+'.N' if x[0] == 'N' else x[1:]) # change normals to have .N
            prot = prot.set_index('Patient_ID')
            # Sort
            normal = prot.loc[prot.index.str.contains('\.N$', regex = True)]
            normal = normal.sort_values(by=["Patient_ID"])
            tumor = prot.loc[~ prot.index.str.contains('\.N$', regex = True)]
            tumor = tumor.sort_values(by=["Patient_ID"])
            all_df = tumor.append(normal)
            self._data['proteomics'] = all_df
            
            # Phosphoproteomics
            phos = self._data["phosphoproteomics"] 
            phos.index.name = 'Patient_ID'
            phos = phos.reset_index()
            phos = phos.replace(matched_ids) # replace label with Patient_IDs
            phos.Patient_ID = phos.Patient_ID.apply(lambda x: x[1:]+'.N' if x[0] == 'N' else x[1:]) # change normals to have .N
            phos = phos.set_index('Patient_ID')
            
            # Sort values
            normal_phos = phos.loc[phos.index.str.contains('\.N$', regex = True)]
            normal_phos = normal_phos.sort_values(by=["Patient_ID"])
            tumor_phos = phos.loc[~ phos.index.str.contains('\.N$', regex = True)]
            tumor_phos = tumor_phos.sort_values(by=["Patient_ID"])
            all_phos = tumor_phos.append(normal_phos)
            self._data["phosphoproteomics"] = all_phos

        # Get a union of all dataframes' indices, with duplicates removed
        ###FILL: If there are any tables whose index values you don't want
        ### included in the master index, pass them to the optional 'exclude'
        ### parameter of the unionize_indices function. This was useful, for
        ### example, when some datasets' followup data files included samples
        ### from cohorts that weren't in any data tables besides the followup
        ### table, so we excluded the followup table from the master index since
        ### there wasn't any point in creating empty representative rows for
        ### those samples just because they existed in the followup table.
#        master_index = unionize_indices(self._data) 

        # Use the master index to reindex the clinical dataframe, so the clinical dataframe has a record of every sample in the dataset. Rows that didn't exist before (such as the rows for normal samples) are filled with NaN.
#        new_clinical = self._data["clinical"]
#        new_clinical = new_clinical.reindex(master_index)

        # Add a column called Sample_Tumor_Normal to the clinical dataframe indicating whether each sample was a tumor or normal sample. Use a function from dataframe_tools to generate it.

        ###FILL: Your dataset should have some way that it marks the Patient IDs
        ### of normal samples. The example code below is for a dataset that
        ### marks them by putting an 'N' at the beginning of each one. You will
        ### need to write a lambda function that takes a given Patient_ID string
        ### and returns a bool indicating whether it corresponds to a normal
        ### sample. Pass that lambda function to the 'normal_test' parameter of
        ### the  generate_sample_status_col function when you call it. See 
        ### cptac/dataframe_tools.py for further function documentation.
        ###START EXAMPLE CODE###################################################
#        sample_status_col = generate_sample_status_col(new_clinical, normal_test=lambda sample: sample[0] == 'N')
        ###END EXAMPLE CODE#####################################################

#        new_clinical.insert(0, "Sample_Tumor_Normal", sample_status_col)

        # Replace the clinical dataframe in the data dictionary with our new and improved version!
#        self._data['clinical'] = new_clinical

        # Edit the format of the Patient_IDs to have normal samples marked the same way as in other datasets. 
        
        ###FILL: You will need to pass the proper parameters to correctly
        ### reformat the patient IDs in your dataset. The standard format is to
        ### have the string '.N' appended to the end of the normal patient IDs,
        ### e.g. the  normal patient ID corresponding to C3L-00378 would be
        ### C3L-00378.N (this way we can easily match two samples from the same
        ### patient). The example code below is for a dataset where all the
        ### normal samples have  an "N" prepended to the patient IDs. The
        ### reformat_normal_patient_ids function erases that and puts a ".N" at
        ### the end. See cptac/dataframe_tools.py for further function
        ### documentation.
        ###START EXAMPLE CODE###################################################
#        self._data = reformat_normal_patient_ids(self._data, existing_identifier="N", existing_identifier_location="start")
        ###END EXAMPLE CODE#####################################################

        # Call function from dataframe_tools.py to sort all tables first by sample status, and then by the index
#        self._data = sort_all_rows(self._data)

        # Call function from dataframe_tools.py to standardize the names of the index and column axes
#        self._data = standardize_axes_names(self._data)

        print(" " * len(formatting_msg), end='\r') # Erase the formatting message
