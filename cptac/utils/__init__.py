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
import scipy.stats
import statsmodels.stats.multitest
import re
import sys
import urllib3
import json
import operator
import collections
import os

import requests
import webbrowser
import operator

from cptac.exceptions import HttpResponseError, InvalidParameterError, MissingFileError, NoInternetError, FileNotUpdatedWarning, ParameterWarning
import warnings


'''
@Param df:
    A dataframe containing the label column, and one or more real valued comparison columns.

@Param label_column:
    The name of the label column. This column must be in the dataframe, and must contain exactly 2 unique values.

@Param comparison_columns (default - will use all in dataframe):
    A list of columns on which t-tests will be performed. Each column must be in the dataframe, and must be real valued.
    If no value is specified, by default it will use every column in the dataframe, aside from the specified label column.

@Param alpha (default = .05):
    Significance level. Will be adjusted using parameter correction_method if more than 1 comparison is done.

@Param return_all (default = False):
    Boolean. If true, will return a dataframe containing all comparisons and p-values, regardless of significance.
    If false, will only return significant comparisons and p-values in the dataframe, or None if no significant comparisons.

@Param correction_method (default = 'bonferroni')
    String. Specifies method of adjustment for multiple testing. See -
    https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html
    - for documentation and available methods.

@Return:
    A pandas dataframe of column names and corresponding p-values which were determined to be significant in
    the comparison, sorted by significance (smallest p-values at the head). The 2 columns of the dataframe are
    'Comparison' and 'P_Value'.
    Returns None if dataframe was not formatted properly, or if no comparison was significant.

This method takes as a parameter a dataframe. Must be formatted in the following way. 1 column declared as the label column, with
the name of this column passed in as the second parameter. The Label column must contain exactly 2 unique entries,
and every row in the dataframe must have one of these 2 values in this column. The remaining columns will be real
valued columns on which t-tests will be done. A list of real valued columns on which to do t-tests will be passed in
as the third parameter. No t-test will be done on columns not included in this list.

The wrap_ttest method will then compare the two groups, as partitioned by the two values in the Label column, and
perform t-tests for each real valued column in the passed in list, generating a p-value.
The resulting p-values will be corrected for multiple testing, using a specified 'correction_method', and a dataframe with
the significant results will be returned as a dataframe, sorted by p-value.
'''

def wrap_ttest(df, label_column, comparison_columns=None, alpha=.05, return_all=False, correction_method='bonferroni'):
    try:
        '''Verify precondition that label column exists and has exactly 2 unique values'''
        label_values = df[label_column].unique()
        if len(label_values) != 2:
            print("Incorrectly Formatted Dataframe! Label column must have exactly 2 unique values.")
            return None

        '''Partition dataframe into two sets, one for each of the two unique values from the label column'''
        partition1 = df.loc[df[label_column] == label_values[0]]
        partition2 = df.loc[df[label_column] == label_values[1]]

        '''If no comparison columns specified, use all columns except the specified labed column'''
        if not comparison_columns:
            comparison_columns = list(df.columns)
            comparison_columns.remove(label_column)

        '''Determine the number of real valued columns on which we will do t-tests'''
        number_of_comparisons = len(comparison_columns)

        '''Store comparisons and p-values in two arrays'''
        comparisons = []
        pvals = []

        '''Loop through each comparison column, perform the t-test, and record the p-val'''
        for column in comparison_columns:
            stat, pval = scipy.stats.ttest_ind(partition1[column].dropna(axis=0), partition2[column].dropna(axis=0))
            comparisons.append(column)
            pvals.append(pval)

        '''Correct for multiple testing to determine if each comparison meets the new cutoff'''
        results = statsmodels.stats.multitest.multipletests(pvals=pvals, alpha=alpha, method=correction_method)
        reject = results[0]

        '''Format results in a pandas dataframe'''
        results_df = pd.DataFrame(columns=['Comparison','P_Value'])

        '''If return all, add all comparisons and p-values to dataframe'''
        if return_all:
            results_df['Comparison'] = comparisons
            results_df['P_Value'] = pvals

            '''Else only add significant comparisons'''
        else:
            for i in range(0, len(reject)):
                if reject[i]:
                    results_df = results_df.append({'Comparison':comparisons[i],'P_Value':pvals[i]}, ignore_index=True)


        '''Sort dataframe by ascending p-value'''
        results_df = results_df.sort_values(by='P_Value', ascending=True)
        results_df = results_df.reset_index(drop=True)

        '''If results df is not empty, return it, else return None'''
        if len(results_df) > 0:
            return results_df
        else:
            return None


    except:
        print("Incorrectly Formatted Dataframe!")
        return None


'''
@Param protein:
    The name of the protein that you want to generate a list of interacting proteins for.

@Param number (default=25):
    The number of interacting proteins that you want to get.

@Return:
    A list of proteins known by the String api to be interacting partners with the specified protein.
    Returns None if specified protein isn't found in String database, or connection to String api fails.


This method takes as a parameter the name of a protein. It then accesses the STRING database, through
a call to their public API, and generates a list of proteins known to be interacting partners with the specified
protein. Optional second parameter is number (which by default is 25), which specifies in the API call how many
interacting partners to retrieve from the database. The list of interacting proteins is returned to the caller
as a python list.
'''

def get_interacting_proteins_string(protein, number=25):
    '''Use urllib3 to access the string database api, gather list of interacting proteins'''
    urllib3.disable_warnings()
    string_api_url = "https://string-db.org/api"
    output_format = "json"
    method = "network"

    '''Use the specified gene and homo sapiens species code'''
    my_protein = [protein]
    species = "9606"

    '''Format the api request to collect the appropriate information'''
    request_url = string_api_url + "/" + output_format + "/" + method + "?"
    request_url += "identifiers=%s" % "%0d".join(my_protein)
    request_url += "&" + "species=" + species
    request_url += "&" + "limit=" + str(number)

    '''Send a request to the API, print the response status'''
    try:
        http = urllib3.PoolManager()
        response = http.request('GET',request_url)
        '''Catch exception if it fails while accessing the api'''
    except urllib3.HTTPError as err:
        error_message = err.read()
        print("Error accessing STRING api, " , error_message)
        sys.exit()

    '''Get the data from the api response'''
    interacting_proteins = []
    if response.status == 200:
        '''Get the data from the API's response'''
        data = response.data
        y = json.loads(data)

        '''Make a list of the resulting interacting proteins'''
        for entry in y:
            if entry["preferredName_A"] not in interacting_proteins:
                interacting_proteins.append(entry["preferredName_A"])
            if entry["preferredName_B"] not in interacting_proteins:
                interacting_proteins.append(entry["preferredName_B"])

        if protein not in interacting_proteins:
            interacting_proteins.append(protein)

        return interacting_proteins

        '''If we didnt get a successful response from the api, notify the caller and return None'''
    else:
        print("\nSpecified gene was not found in String database, double check that you have it correctly!")
        return None


'''
@Param protein:
    The name of the protein that you want to generate a list of interacting proteins for.

@Param number (default=25):
    The number of interacting proteins that you want to get.

@Return:
    A list of proteins known by the biogrid api to be interacting partners with the specified protein.
    Returns None if specified protein isn't found in biogrid database, or connection to biogrid api fails.


This method takes as a parameter the name of a protein. It then accesses the biogrid database, through
a call to their public API, and generates a list of proteins known to be interacting partners with the specified
protein. Optional second parameter is number (which by default is 25), which specifies in the API call how many
interacting partners to retrieve from the database. The list of interacting proteins is returned to the caller
as a python list.
'''
def get_interacting_proteins_biogrid(protein, number=25):
    '''Store interacting proteins in a list'''
    interacting_proteins = []
    urllib3.disable_warnings()

    '''Configure url for request'''
    request_url = "https://webservice.thebiogrid.org/interactions/?searchNames=true&geneList=" + protein +"&includeInteractors=true&format=json&taxId=9606&start=0&max=" + str(number) + "&accesskey=0ff59dcf3511928e78aad499688381c9"
    try:
        '''Send request, get response'''
        http = urllib3.PoolManager()
        response = http.request('GET',request_url)

        '''If response was successful'''
        if response.status == 200:
            '''Get the data from the API's response'''
            data = response.data
            y = json.loads(data)

            '''Add name of each protein to list of interacting proteins'''
            for entry in y:
                if y[entry]['OFFICIAL_SYMBOL_A'] not in interacting_proteins:
                    interacting_proteins.append(y[entry]['OFFICIAL_SYMBOL_A'])

            '''Return this list to caller'''
            return interacting_proteins

        else:
            '''If response was not successful, notify caller of error, return None'''
            print("Error accessing api!")
            return None

        '''Catch exception, notify caller of error, return None'''
    except Exception as err:
        print("Error accessing api, " , err)
        return None


'''
@Param protein:
    The name of the protein that you want to generate a list of interacting proteins for.

@Param number (default=25):
    The number of interacting proteins that you want to get from both STRING and BioGrid(used by uniprot). This
    number of proteins will be generated by both String and BioGrid, and the two will be combined. The actual number of
    proteins in the list returned by this method will be between the number specified and 2 times the number specified,
    depending on how many of the interacting proteins the two APIs 'agree' on.

@Return:
    A list of proteins known by the String and BioGrid APIs to be interacting partners with the specified protein.
    Returns None if specified protein isn't found in either database, or both API calls fail.


This method takes as a parameter the name of a protein. It then accesses the STRING and BioGrid databases, through
a call to their public API, and generates a list of proteins known to be interacting partners with the specified
protein. Optional second parameter is number (which by default is 25), which specifies in the API call how many
interacting partners to retrieve from the database. The list of interacting proteins is returned to the caller
as a python list.
'''
def get_interacting_proteins(protein, number=25):
    string_list = get_interacting_proteins_string(protein, number)
    biogrid_list = get_interacting_proteins_biogrid(protein, number)

    if string_list == None and biogrid_list == None:
        return None

    else:
        interacting_proteins = []
        for prot in string_list:
            if prot not in interacting_proteins:
                interacting_proteins.append(prot)
        for prot in biogrid_list:
            if prot not in interacting_proteins:
                interacting_proteins.append(prot)

        return interacting_proteins


'''
@Param protein:
    The name of the protein that you want to generate a list of interacting proteins for.

@Return:
    A list of proteins which are interacting partners with the specified protein, according to the bioplex data table.
    Returns None if specified protein isn't found, or no interacting partners are found.

This method takes as a parameter the name of a protein. It then accesses the bioplex data table and returns a list of any protein found to be an interacting partner to the given protein.
'''

def get_interacting_proteins_bioplex(protein, secondary_interactions=False):
    path_here = os.path.abspath(os.path.dirname(__file__))
    file_name = "BioPlex_interactionList_v4a.tsv"
    file_path = os.path.join(path_here, file_name)

    bioplex_interactions = pd.read_csv(file_path, sep='\t')

    A_df = bioplex_interactions.loc[bioplex_interactions['SymbolA'] == protein]
    B_df = bioplex_interactions.loc[bioplex_interactions['SymbolB'] == protein]

    A_interactions = list(A_df['SymbolB'])
    B_interactions = list(B_df['SymbolA'])

    all_interactions = list(set(A_interactions + B_interactions))

    if secondary_interactions:
        secondary_interactions_list = []
        for interaction in all_interactions:
            secondary = get_interacting_proteins_bioplex(interaction, False)
            for si in secondary:
                secondary_interactions_list.append(si)

        for asi in secondary_interactions_list:
            if asi not in all_interactions:
                all_interactions.append(asi)

    if len(all_interactions) > 0:
        return all_interactions
    else:
        return None


"""
Takes a cancer object and find the frequently
mutated genes (in the tumor samples) compared to the cutoff.

@Param cancer_object:
    Cancer dataset object from the cptac module.

@Param cutoff:
    Float. Used as a comparison to determine the status of
    gene mutation frequency.

@Return:
    DataFrame of frequently mutated genes passing the cutoff.
    Columns contain the fractions of total unique mutations,
    missense type mutations, and truncation type mutations per gene.

The Missense_Mut column includes:
    In_Frame_Del, In_Frame_Ins, Missense_Mutation

The Truncation_Mut column includes:
    Frame_Shift_Del, Frame_Shift_Ins, Splice_Site,
    Nonsense_Mutation, Nonstop_Mutation

These columns count multiple mutations of one gene in the
same sample, so fractions in the last two columns may
exceed the Unique_Samples_Mut column which only counts if
the gene was mutated once per sample."""

def get_frequently_mutated(cancer_object, cutoff = 0.1):  
    # Get total tumors/patients
    omics_and_mutations = cancer_object.join_omics_to_mutations(
        mutations_genes = 'TP53', omics_df_name = 'proteomics', omics_genes = 'TP53')
    tumors = omics_and_mutations.Sample_Status

    if isinstance(tumors, pd.DataFrame): # This would happen if our proteomics dataframe has a column multiindex, which leads to a joined df with a column multiindex, and causes our selection to be a dataframe instead of a series.
        tumors = tumors.iloc[:, 0]
        tumors.name = "Sample_Status"

    v = tumors.value_counts()
    total_tumors = v['Tumor']
    total_tumor_count = float(total_tumors)
    
    # Get mutations data frame
    somatic_mutations = cancer_object.get_somatic_mutation() 

    # Drop silent mutations for Hnscc, Ovarian, and Ccrcc dataset, and synonymous SNV (i.e. silent) mutations in HNSCC
    if 'Silent' in somatic_mutations['Mutation'].unique():
        origin_df = somatic_mutations.loc[somatic_mutations['Mutation'] != 'Silent'].reset_index()
    elif 'synonymous SNV' in somatic_mutations['Mutation'].unique():
        origin_df = somatic_mutations.loc[somatic_mutations['Mutation'] != 'synonymous SNV'].reset_index()
    else:
        origin_df = somatic_mutations.reset_index() #prepare to count unique samples
        
    # Create two categories in Mutation column - 'M': Missense, 'T': Truncation
    if cancer_object.get_cancer_type() in ('hnscc') and cancer_object.version() == '0.1':
        dif_mut_names = True
    elif cancer_object.get_cancer_type() in ('colon'):
        dif_mut_names = True
    else: 
        dif_mut_names = False
        
    if dif_mut_names == True:
        missense_truncation_groups = {'frameshift substitution': 'T', 
            'frameshift deletion': 'T', 'frameshift insertion': 'T', 
            'stopgain': 'T', 'stoploss': 'T', 'nonsynonymous SNV': 'M',
            'nonframeshift insertion': 'M','nonframeshift deletion': 'M', 
            'nonframeshift substitution': 'M'}
    else: 
        missense_truncation_groups = {'In_Frame_Del': 'M', 'In_Frame_Ins': 'M',
            'Missense_Mutation': 'M', 'Frame_Shift_Del': 'T','Nonsense_Mutation': 'T', 
            'Splice_Site': 'T', 'Frame_Shift_Ins': 'T','Nonstop_Mutation':'T'}
    
    mutations_replaced_M_T = origin_df.replace(missense_truncation_groups)
    
    # replace non_coding mutations for Gbm
    unique_mutations = len(mutations_replaced_M_T['Mutation'].unique())
    gbm = False
    if cancer_object.get_cancer_type() == 'gbm':
        gbm = True
        non_coding = {'Intron': 'NC', 'RNA': 'NC', "5'Flank": 'NC', "3'Flank": 'NC', 
            "5'UTR": 'NC', "3'UTR": 'NC', 'Splice_Region' : 'NC'}
        mutations_replaced_M_T = mutations_replaced_M_T.replace(non_coding)
        unique_mutations_2 = len(mutations_replaced_M_T['Mutation'].unique())
        
    elif unique_mutations != 2: # Check that all mutation names are catagorized
        print('Warning: New mutation name not classified. Counts will be affected.')
    
    # Find frequently mutated genes (total fraction > cutoff)
    # Same steps will be repeated for finding the missense and truncation mutation frequencies
    # Step 1 - group by gene and count unique samples
    # Step 2 - format
    # Step 3 - filter using the cutoff and create fraction 
    count_mutations = origin_df.groupby(['Gene']).nunique()
    count_mutations = count_mutations.rename(columns={"Patient_ID": "Unique_Samples_Mut"}) # Step 2 
    count_mutations = count_mutations.drop(['Gene', 'Mutation', 'Location'], axis = 1)
    fraction_mutated = count_mutations.apply(lambda x: x / total_tumor_count) # Step 3 
    fraction_greater_than_cutoff = fraction_mutated.where(lambda x: x > cutoff) #na used when not > cutoff
    filtered_gene_df = fraction_greater_than_cutoff.dropna() # drop genes below cutoff
    
    # Create and join Missense column (following similar steps as seen above) *Counts missense once in sample
    miss = mutations_replaced_M_T.loc[mutations_replaced_M_T['Mutation'] == 'M']
    count_miss = miss.groupby(['Gene']).nunique()
    missense_df = count_miss.rename(columns={"Patient_ID": "Missense_Mut"})
    missense_df = missense_df.drop(['Gene', 'Mutation', 'Location'], axis = 1)
    fraction_missense = missense_df.apply(lambda x: x / total_tumor_count)
    freq_mutated_df = filtered_gene_df.join(fraction_missense, how='left').fillna(0)
    
    # Create and join Truncation column (following similar steps as seen above)
    trunc = mutations_replaced_M_T.loc[mutations_replaced_M_T['Mutation'] == 'T']
    count_trunc = trunc.groupby(['Gene']).nunique()
    truncation_df = count_trunc.rename(columns={"Patient_ID": "Truncation_Mut"})
    truncation_df = truncation_df.drop(['Gene', 'Mutation', 'Location'], axis = 1)
    fraction_truncation = truncation_df.apply(lambda x: x / total_tumor_count)
    freq_mutated_df = freq_mutated_df.join(fraction_truncation, how='left').fillna(0)
    
    if gbm == True:
        # Create and join non-coding column (following similar steps as seen above)
        nc = mutations_replaced_M_T.loc[mutations_replaced_M_T['Mutation'] == 'NC']
        count_nc = nc.groupby(['Gene']).nunique()
        nc_df = count_nc.rename(columns={"Patient_ID": "Non-Coding"})
        nc_df = nc_df.drop(['Gene', 'Mutation', 'Location'], axis = 1)
        fraction_nc = nc_df.apply(lambda x: x / total_tumor_count)
        freq_mutated_df = freq_mutated_df.join(fraction_nc, how='left').fillna(0)
        
    freq_mutated_df = freq_mutated_df.reset_index() #move genes to their own column
    
    return freq_mutated_df





def parse_hotspot(path, mut_df):
    '''
    @Param path:
        (String) The path to the cluster output file that is on your computer after running the Hotspot analysis

    @Param mut_df:
        (Dataframe) The dataframe that is obtained by performing the .get_somatic_mutation() function of cptac

    @Return:
        There will be four outputs for this function:

        vis_hs_df:
            visualize hotspot dataframe

            A small dataframe which will allow quick visualization regarding the number of cancer patients that contain hotspot mutations

        bin_hs_df:
            binary hotspot dataframe

            A larger dataframe that contains boolean values for each patient and their relationship with the hotspot(True = patient has a hotspot mutation, False = patient does not have a hotspot mutation)

        det_hs_df:
            detailed hotspot dataframe

            A larger dataframe that contains nonbinary values for each patient and their relationship with the hotspot(No = no mutation, Yes = mutation but not in the hotspot, Yes_HS = mutation in the hotspot)

        mut_dict:
            mutations dictionary

            A dictionary that contains the hotspot gene as the key, and a list of mutations that make up that hotspot

    This function will take two parameters (cluster file path and mutations dataframe) and use them to parse the Hotspot3D program output. It creates a cluster dataframe from the Hotspot3D output, and identifies the patients who contain hotspot mutations. The outputs of this function can be used to run further statistical analysis and exploration on the cancer datasets.
    '''
    #Importing the desired cluster file from the specified path on the computer
    cluster_df = pd.read_csv(path, sep = '\t')

    #Creating a list of all the identified hotspot clusters
    cluster_list_initial = (cluster_df.Cluster.unique()).tolist()
    cluster_list = list()

    #Checking each cluster to make sure that only clusters containing 2 or more mutations are looked at ('clusters' with only 1 mutation are technically just frequently mutated)
    for value in cluster_list_initial:
        length = len(cluster_df[cluster_df['Cluster'] == value])
        if length >= 2:
            cluster_list.append(value)

    #Sorting the list numerically
    cluster_list.sort()

    #If there are no clusters that have more than one mutation, the function ends and returns the statement below
    if len(cluster_list) == 0:
        print('There are no hotspot clusters that contain more than one mutation.')
        return None

    #creating the multiple dictionaries that are used to compile hotspots and corresponding mutations
    gene_dict = {}
    mut_dict = {}
    rev_mut_dict = {}
    hs_count = {}

    #This loop contructs a reverse dictionary to be used to classify patients' mutations as well as the mutation dictionary output
    for value in cluster_list:
        gene_dict[value] = cluster_df.loc[cluster_df['Cluster'] == value, 'Gene/Drug'].values[0]
        mut_list = cluster_df[cluster_df['Cluster'] == value]['Mutation/Gene'].values.tolist()
        if str(value).endswith('0'):
            mut_dict[gene_dict[value]] = mut_list
            hs_count[gene_dict[value]] = 0
        else:
            mut_dict[str(gene_dict[value]) + '_' + str(value)[-1]] = mut_list
            hs_count[str(gene_dict[value]) + '_' + str(value)[-1]] = 0

    #This loop finalizes the reverse dictionary
    for hs in mut_dict.keys():
        for mutation in mut_dict[hs]:
            rev_mut_dict[mutation] = hs

    #The three dataframe outputs are initialized
    vis_hs_df = pd.DataFrame()
    vis_hs_df['hotspot_id'] = mut_dict.keys()

    bin_hs_df = pd.DataFrame()
    bin_hs_df['sample_id'] = mut_df.index.unique()

    det_hs_df = pd.DataFrame()
    det_hs_df['sample_id'] = mut_df.index.unique()

    #This loop populates default values for each patient and hotspot
    for hs in mut_dict.keys():
        bin_hs_df[hs] = False
        det_hs_df[hs] = 'No'

    #This loop iterates through each individual mutation and then properly identifies the mutation in the different dataframes
    for row in mut_df.iterrows():
        info = list(row[1])
        gene = info[0]
        location = info[2]
        if str(location)[0] != 'p':
            location = 'p.'+str(location)
        sample_id = row[0]

        #This statement checks to see if the mutation is one of the hotspot mutations
        if location in rev_mut_dict.keys():
            hs = rev_mut_dict[location]
            hs_count[hs] += 1

            bin_hs_df.loc[bin_hs_df['sample_id'] == sample_id, hs] = True
            det_hs_df.loc[det_hs_df['sample_id'] == sample_id, hs] = 'Yes_HS'

        #This statement is used if the mutation is not a hotspot mutation, but if it still on one of the proteins that contains a hotspot
        elif gene in mut_dict.keys():
            det_hs_df.loc[det_hs_df['sample_id'] == sample_id, hs] = 'Yes'

    #This loop adds the patient count for each hotspot to the small visualize hotspot dataframe
    for hs in hs_count.keys():
        vis_hs_df.loc[vis_hs_df['hotspot_id'] == hs, 'patients_within'] = hs_count[hs]

    bin_hs_df = bin_hs_df.set_index('sample_id')
    det_hs_df = det_hs_df.set_index('sample_id')

    #Return of the three dataframes and mutation dictionary
    return(vis_hs_df, bin_hs_df, det_hs_df, mut_dict)

"""
@param protein:
	String. The name of the protein
@Return:
	A list of proteins known by the most recent WikiPathways download to be interacting parters with the specified protein.
	Returns None if specified protein is not found in the WikiPathways dataframe (which was intersected with Uniprot).

This function takes a path to WikiPathways Dataframe file and protein name and returns a list of all the proteins that interact with it, using the pathways from the WikiPathways relsease file.
This function loads the WikiPathways dataframe, and iterates through the row labelled with that protein name, return every protein in a pathway that also contains that protein.
"""

def get_interacting_proteins_wikipathways(protein):
    path_here = os.path.abspath(os.path.dirname(__file__))
    file_name = "WikiPathwaysDataframe.tsv"
    file_path = os.path.join(path_here, file_name)
    proteinName = protein

    df =pd.read_csv(file_path, sep="\t", index_col=False)
    df.set_index("Unnamed: 0", inplace=True)
    if (proteinName in df.index):
    	row = df.loc[proteinName]
    	filtered_df = df.loc[:, row.values.tolist()]
    	def has_true(values):
    		for val in values:
    			if val == True:
    				return True
    		return False
    	filtered_df_final = filtered_df.loc[filtered_df.apply(lambda row: has_true(row.values.tolist()), axis=1), :]
    	return filtered_df_final.index.tolist()
    return list()  # The protein was not found.

'''
@ Param: protein:
	The name of the protein that you want to generate the list of pathways for
@ Return:
	A list of pathways the given protein is involved in.

Uses the WikiPathwaysDataframe to find the pathways the given protein is involved in.
'''
def get_protein_pathways(protein):
    path_here = os.path.abspath(os.path.dirname(__file__))
    file_name = "WikiPathwaysDataframe.tsv"
    file_path = os.path.join(path_here, file_name)

    proteinName = protein
    df =pd.read_csv(file_path, sep="\t", index_col=False)
    df.set_index("Unnamed: 0", inplace=True)
    if (proteinName in df.index):
    	row = df.loc[proteinName]
    	filtered_df = df.loc[:, row.values.tolist()]
    	return list(filtered_df.columns)
    return list()  # The protein was not found.


'''
@ Return:
	A list of all the possible pathways
Uses the WikipathwaysDataFrame to return a list of all the possible pathways found.
'''
def list_pathways():
    path_here = os.path.abspath(os.path.dirname(__file__))
    file_name = "WikiPathwaysDataframe.tsv"
    file_path = os.path.join(path_here, file_name)

    df =pd.read_csv(file_path, sep="\t", index_col=False)
    df.set_index("Unnamed: 0", inplace=True)
    return list(df.columns)

'''
@ Param pathway:
	String. The name of a pathway
@ Return:
	A list of all the proteins involved in the given pathway
Uses the WikiPathwaysDataFrame to find all the genes involved in the given pathway.
'''
def get_proteins_in_pathway(pathway):
    path_here = os.path.abspath(os.path.dirname(__file__))
    file_name = "WikiPathwaysDataframe.tsv"
    file_path = os.path.join(path_here, file_name)

    df =pd.read_csv(file_path, sep="\t", index_col=False)
    df.set_index("Unnamed: 0", inplace=True)
    if (pathway in df.columns):
    	col = df[pathway]
    	filtered_df = df.loc[col, :]
    	return list(filtered_df.index)
    return list()  # The protein was not found.

'''
@Param df: Dataframe.Each column is a different gene/ comparison. Rows contains numeric values (such as proteomics) for correlation test
@Param label_column: String. Name of column that will be your x axis and will be compared to all values in df unless otherwise specified.
@Param alpha: significant level
@Param comparison_columns: columns that will be looped through and used as y axis for correlation test.
All other columns beside label column unless specified here.
@Param correction_method: String. Specifies method of adjustment for multiple testing. See -
https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html
    - for documentation and available methods.
This function will return a data frame with the columns comparison, the correlation coefficient, and the p value.
'''
def wrap_pearson_corr(df,label_column, alpha=.05,comparison_columns=None,correction_method='bonferroni',return_all = True):


    #df = df.dropna(axis=1, how="all")

    '''If no comparison columns specified, use all columns except the specified labed column'''
    if not comparison_columns:
        comparison_columns = list(df.columns)
        comparison_columns.remove(label_column)
    '''Store comparisons,p-values, correlation in their own array'''
    comparisons = []
    pvals = []
    correlation=[]


    '''Format results in a pandas dataframe'''
    newdf = pd.DataFrame(columns=['Comparison','Correlation','P_value'])
    for gene in comparison_columns:
        #create subset df with interacting gene/ gene (otherwise drop NaN drops everything)
        df_subset = df[[label_column,gene]]
        #do a linear regression to see if it's a meaningful association
        #dropna will remove rows with nan
        df_subset = df_subset.dropna(axis=0, how="any")
        count_row = df_subset.shape[0]
        if count_row > 20:
            x1 = df_subset[[label_column]].values
            y1 = df_subset[[gene]].values
            x1 = x1[:,0]
            y1 = y1[:,0]
            corr, pval = scipy.stats.pearsonr(x1,y1)

            comparisons.append(gene)
            pvals.append(pval)
            correlation.append(corr)


    '''Correct for multiple testing to determine if each comparison meets the new cutoff'''
    results = statsmodels.stats.multitest.multipletests(pvals=pvals, alpha=alpha, method=correction_method)
    reject = results[0]

    if return_all:
        for i in range(0,len(comparisons)):
            newdf = newdf.append({'Comparison': comparisons[i],"Correlation": correlation[i],'P_value': pvals[i]}, ignore_index=True)

    '''Else only add significant comparisons'''
    if (return_all == False):
            for i in range(0, len(reject)):
                if reject[i]:
                    newdf = newdf.append({'Comparison': comparisons[i],"Correlation": correlation[i],'P_value': pvals[i]}, ignore_index=True)

    '''Sort dataframe by ascending p-value'''
    newdf = newdf.sort_values(by='P_value', ascending=True)
    '''If results df is not empty, return it, else return None'''
    return newdf

def reactome_pathway_overlay(df, pathway, open_browser=True, export_path=None, image_format="png", display_col_idx=0, diagram_colors="Modern", overlay_colors="Standard", quality=7):
    """Visualize numerical data (e.g. protein expression) on a Reactome pathway diagram, with each node's color corresponding to the expression value provided for that molecule.

    Parameters:
    df (pandas.DataFrame or pandas.Series): The data you want to overlay. Each row corresponds to a particular gene/protein/etc, and each column is expression or other data for a sample or aggregate. Index must be unique identifiers. Multiple data columns allowed. All dtypes must be numeric. No NaNs allowed--we want the user to decide how to handle missing values, depending on the context of their analysis.
    pathway (str): The Reactome ID for the pathway you want to overlay the data on, e.g. "R-HSA-73929".
    open_browser (bool, optional): Whether to automatically open the diagram in a new web browser tab. Default True.
    export_path (str, optional): A string providing a path to export the diagram to. Must end in a file name with the same extension as the "image_format" parameter. Default None causes no figure to be exported.
    image_format (str, optional): If export_path is not none, this specifies the format to export the diagram to. Options are "png", "gif", "svg", "jpg", "jpeg", or "pptx". Must match the file extension in the export path. If you're creating a gif and you want more than one column's data to be included in the image, make sure to pass None to the display_col_idx parameter. Default "png".
    display_col_idx (int, optional): If export_path is not none, this specifies which column in the dataframe to overlay expression data from. Must be a valid column index for the given table, or None. None will cause the first column to be displayed, unless you're creating a gif, in which case it will cause all columns to be included in the gif. Default None.
    diagram_colors (str, optional): If export_path is not none, this specifies the Reactome color scheme to use for the underlying diagram. Options are "Modern" or "Standard". Default "Modern".
    overlay_colors (str, optional): If export_path is not none, this specifies the Reactome color scheme to use for the data overlay. Options are "Standard", "Strosobar", or "Copper Plus". Default "Standard".
    quality (int, optional): If export_path is not none, this specifies what relative quality to export the image at. Must be between 1 and 10 inclusive. Default 7.

    Returns:
    str: If export_path is None, returns URL to diagram with data overlaid in Reactome Pathway Browser. Otherwise returns the path the image was exported to.
    """
    # If they gave us a series, make it a dataframe
    if isinstance(df, pd.Series):
        if df.name is None:
            df.name = "data"
        df = pd.DataFrame(df)

    # Parameter checking
    if export_path is not None:

        if image_format not in ("png", "gif", "svg", "jpg", "jpeg", "pptx"):
            raise InvalidParameterError(f"Invalid value for 'image_format' parameter. Valid options are 'png', 'gif', 'svg', 'jpg', 'jpeg', or 'pptx'. You passed '{image_format}'.")

        if display_col_idx is None:
            display_col_idx = ""        
        elif display_col_idx not in range(0, df.shape[1]):
            raise InvalidParameterError(f"Invalid value for 'display_col_idx' parameter. Must be either None, or an int between 0 and one less than the number of columns in df (which is {df.shape[1] - 1} for this df), inclusive. You passed {display_col_idx}.")

        if diagram_colors not in ("Modern", "Standard"):
            raise InvalidParameterError(f"Invalid value for 'diagram_colors' parameter. Valid options are 'Modern' or 'Standard'. You passed '{diagram_colors}'.")

        if overlay_colors not in ("Standard", "Strosobar", "Copper Plus"):
            raise InvalidParameterError(f"Invalid value for 'overlay_colors' parameter. Valid options are 'Standard', 'Strosobar', or 'Copper Plus'. You passed '{overlay_colors}'.")

        if quality not in range(1, 11):
            raise InvalidParameterError(f"Invalid value for 'quality' parameter. Must be an int between 1 and 10 inclusive. You passed {quality}.")

        if image_format != export_path.split('.')[-1]:
            raise InvalidParameterError(f"The file extension in the 'export_path' parameter must match the 'image_format' parameter. For the image_format parameter, you passed '{image_format}'. The extension at the end of your export path was '{export_path.split('.')[-1]}'.")

        if export_path[:2] == "~/":
            raise InvalidParameterError("The export path you provided appeared to start with a reference to the user home directory. To avoid confusion, this function will not expand that reference. Please provide a full path instead.")

    # The identifier series (the index) needs to have a name starting with "#"
    if df.index.name is None:
        df.index.name = "#identifier"
    elif not df.index.name.startswith("#"):
        df.index.name = "#" + df.index.name

    # Take care of NaNs
    df = df.astype(str) # This represents NaNs as 'nan', which Reactome is OK with

    # Get the df as a tab-separated string
    df_str = df.to_csv(sep='\t')

    # Post the data to the Reactome analysis service
    analysis_url = "https://reactome.org/AnalysisService/identifiers/projection"
    headers = {"Content-Type": "text/plain"}
    view_resp = requests.post(analysis_url, headers=headers, data=df_str)

    # Check that the response came back good
    if view_resp.status_code != requests.codes.ok:
        raise HttpResponseError(f"Submitting your data for analysis returned an HTTP status {view_resp.status_code}. The content returned from the request may be helpful:\n{view_resp.content.decode('utf-8')}")    

    # Get the token for accessing the analysis results
    token = view_resp.json()["summary"]["token"]

    # Use the token and the pathway ID to open the pathway diagram with the data overlaid in the Reactome Pathway Browser
    viewer_url = f"https://reactome.org/PathwayBrowser/#/{pathway}&DTAB=AN&ANALYSIS={token}"
    if open_browser:
        webbrowser.open(viewer_url)

    if export_path is not None:

        # Get the diagram
        export_url = f"https://reactome.org/ContentService/exporter/diagram/{pathway}.{image_format}?token={token}&resource=TOTAL&diagramProfile={diagram_colors}&analysisProfile={overlay_colors}&expColumn={display_col_idx}&quality={quality}"
        export_resp = requests.get(export_url)

        # Check that the response came back good
        if export_resp.status_code != requests.codes.ok:
            raise HttpResponseError(f"Submitting your data for analysis returned an HTTP status {export_resp.status_code}. The content returned from the request may be helpful:\n{export_resp.content.decode('utf-8')}")    

        # Save the image
        with open(export_path, 'wb') as dest:
            dest.write(export_resp.content)

    if export_path is None:
        return viewer_url
    else:
        return export_path

def search_reactome_pathways_with_proteins(ids, resource="UniProt", quiet=False):
    """Query the Reactome REST API to find Reactome pathways containing a particular gene or protein.

    Parameters:
    ids (str or list of str): The id(s) to look for matches to.
    resource (str, optional): The database the identifier(s) come from. Default is UniProt. Other options include HGNC, Ensembl, and GO. For more options, consult <https://reactome.org/content/schema/objects/ReferenceDatabase>.
    quiet (bool, optional): Whether to suppress warnings issued when identifiers are not found. Default False.

    Returns:
    pandas.DataFrame: A table of pathways containing the given genes or proteins, with pathway names and their Reactome identifiers (the latter are needed for the pathway_overlay function).
    """
    # Process string input
    if isinstance(ids, str):
        ids = [ids]

    # Set headers and params
    headers = {"accept": "application/json"}
    params = {"species": "Homo sapiens"}

    # Loop over ids and get the interacting pathways
    all_pathway_df = pd.DataFrame()
    for id in ids:
        url = f"https://reactome.org/ContentService/data/mapping/{resource}/{id}/pathways"
        resp = requests.get(url, headers=headers, params=params)

        # Check that the response came back good
        if resp.status_code == 404:
            try:
                msg = resp.json()["messages"]
            except (json.JSONDecodeError, KeyError):
                raise HttpResponseError(f"Your query returned an HTTP status {resp.status_code}. The content returned from the request may be helpful:\n{resp.content.decode('utf-8')}") from None
            else:
                if not quiet:
                    warnings.warn(f"The query for '{id}' returned HTTP 404 (not found). You may have mistyped the gene/protein ID or the resource name. The server gave the following message: {msg}", ParameterWarning, stacklevel=2)
                continue
        elif resp.status_code != requests.codes.ok:
            raise HttpResponseError(f"Your query returned an HTTP status {resp.status_code}. The content returned from the request may be helpful:\n{resp.content.decode('utf-8')}")

        # Parse out pathway IDs and names
        pathway_dict = resp.json()
        names = []
        ids = []
        for pathway in pathway_dict:
            names.append(pathway["displayName"])
            ids.append(pathway["stId"])

        pathway_df = pd.DataFrame({"id": id, "pathway": names, "pathway_id": ids})
        pathway_df = pathway_df.sort_values(by="pathway_id")
        all_pathway_df = all_pathway_df.append(pathway_df)

    all_pathway_df = all_pathway_df.reset_index(drop=True)
    return all_pathway_df

def search_reactome_proteins_in_pathways(pathway_ids, quiet=False):
    """Query the Reactome REST API to get a list of proteins contained in a particular pathway.

    Parameters:
    pathway_id (str): The pathway to get the contained proteins for.

    Returns:
    list: The proteins contained in the pathway.
    """
    # Process string input
    if isinstance(pathway_ids, str):
        pathway_ids = [pathway_ids]

    # Set headers and url
    headers = {"accept": "application/json"}

    # Loop over ids and get the interacting pathways
    all_pathway_df = pd.DataFrame()
    for pathway_id in pathway_ids:

        # Send the request
        url = f"https://reactome.org/ContentService/data/participants/{pathway_id}"
        resp = requests.get(url, headers=headers)

        if resp.status_code == 404 or (resp.status_code == requests.codes.ok and (len(resp.content.decode("utf-8")) == 0 or len(resp.json()) == 0)):
            if not quiet:
                warnings.warn(f"The query for '{pathway_id}' found no results. You may have mistyped the pathway ID.", ParameterWarning, stacklevel=2)
            continue
        elif resp.status_code != requests.codes.ok:
            raise HttpResponseError(f"Your query returned an HTTP status {resp.status_code}. The content returned from the request may be helpful:\n{resp.content.decode('utf-8')}")

        # Parse all the proteins/genes out of the response
        all_members = resp.content.decode("utf-8").split('"')
        member_proteins = [member.split(" ")[1] for member in all_members if member.startswith("UniProt")]

        pathway_df = pd.DataFrame({"pathway_id": pathway_id, "member": member_proteins})
        pathway_df = pathway_df.sort_values(by="member")
        all_pathway_df = all_pathway_df.append(pathway_df)

    all_pathway_df = all_pathway_df.drop_duplicates(keep="first")
    all_pathway_df = all_pathway_df.reset_index(drop=True)
    return all_pathway_df

def permutation_test_means(group1, group2, num_permutations, paired=False):
    """Use permutation testing to calculate a P value for the difference between the means of two groups. You would use this instead of a Student's t-test if your data do not follow a normal distribution. Note that permutation tests are still subject to the assumption of the Student's t-test that if you want to see if the means of the two groups are different, they need to have the same variance.

    Parameters:
    group1 (pandas.Series): The first group of samples. NaNs will be dropped before any analysis. If doing a paired test, samples from the same subject must have the same index value in both group1 and group2.
    group2 (pandas.Series): The second group of samples. NaNs will be dropped before any analysis. If doing a paired test, samples from the same subject must have the same index value in both group1 and group2.
    num_permutations (int): The number of permutations to perform
    paired (bool, optional): Whether to do a paired test. Default is False.

    Returns:
    float: The difference between the means
    float: The P value for the null hypothesis that the two groups have the same mean
    list of float: The generated null distribution for the difference between the means
    """
    # Drop NaN values
    group1 = group1.dropna()
    group2 = group2.dropna()

    null_dist = []
    extreme_count = 0

    # Create an independent pseudo-random number generator
    generator = np.random.RandomState(0)

    if paired:

        # Calculate the paired differences, and the paired difference in the means
        paired_diffs = group1.combine(group2, operator.sub).dropna().values
        actual_diff = np.mean(paired_diffs)
        abs_actual_diff = abs(actual_diff)

        for i in range(num_permutations):

            # Randomly flip the signs of the differences and recalculate the mean
            random_signs = generator.choice([1, -1], size=paired_diffs.size)
            diffs_signs_perm = random_signs * paired_diffs
            perm_diff = np.mean(diffs_signs_perm)

            # Add the permuted paired difference in the means to our null distribution
            null_dist.append(perm_diff)

            # Keep count of how many are as or more extreme than the actual difference
            if abs(perm_diff) >= abs_actual_diff: # We compare the absolute values for a two-tailed test
                extreme_count += 1

    else:

        # Concatenate the series
        both = group1.append(group2)

        # Calculate the actual difference in the means
        actual_diff = np.mean(group1) - np.mean(group2)
        abs_actual_diff = abs(actual_diff)

        for i in range(num_permutations):

            # Permute values
            perm_array = generator.permutation(both.values)

            # Split out permuted groups
            perm_group1 = perm_array[:group1.size]
            perm_group2 = perm_array[group1.size:]

            # Calculate the permutation's difference in the means
            perm_diff = np.mean(perm_group1) - np.mean(perm_group2)

            # Add it to our null distribution
            null_dist.append(perm_diff)

            # Keep count of how many are as or more extreme than the actual difference
            if abs(perm_diff) >= abs_actual_diff: # We compare the absolute values for a two-tailed test
                extreme_count += 1

    # Calculate the P value
    P_val = extreme_count / num_permutations # Don't need to multiply by 2 because we compared the absolute values of difference between means.

    return actual_diff, P_val, null_dist

def permutation_test_corr(data, num_permutations):
    """Use permutation testing to calculate a P value for the linear correlation coefficient between two variables in several samples. You would use this if your distribution didn't follow the Pearson correlation test's assumption of being bivariate normal.

    Parameters:
    data (pandas.DataFrame): A dataframe where the rows are samples, and the columns are the two variables we're testing correlation between.

    Returns:        
    float: The linear correlation coefficient for the two variables.
    float: The P value for the null hypothesis that the correlation coefficient is zero.
    """

    # Check the table dimensions
    if data.shape[1] != 2:
        raise ValueError(f"Expected 2 columns in dataframe. Found {data.shape[1]}.")

    # Drop NaN values
    data = data.dropna()

    # Extract the values
    var1 = data.iloc[:, 0].values
    var2 = data.iloc[:, 1].values

    # Create an independent pseudo-random number generator
    generator = np.random.RandomState(0)

    # Calculate the actual correlation coefficient
    actual_coef = np.corrcoef(var1, var2)[0, 1]

    null_dist = []
    extreme_count = 0

    for i in range(num_permutations):
        var1_perm = generator.permutation(var1)
        perm_coef = np.corrcoef(var1_perm, var2)[0, 1]

        # Add it to our null distribution
        null_dist.append(perm_coef)

        # Keep count of how many are as or more extreme than our coefficient
        if abs(perm_coef) >= abs(actual_coef): # We compare the absolute values for a two-tailed test
            extreme_count += 1

    # Calculate the P value
    P_val = extreme_count / num_permutations # Don't need to multiply by 2 because we compared the absolute values of coefficients.

    return actual_coef, P_val, null_dist

def get_corum_protein_lists(update=True):
    """Reads file from CORUM and returns a dictionary where the keys are protein complex names, and the values are lists of proteins that are members of those complexes. Data is downloaded from the CORUM website (https://mips.helmholtz-muenchen.de/corum/#). We also provide get_hgnc_protein_lists to get similar data from HGNC. The CORUM data has more specific subgroups than the HGNC data, but the HGNC data is more comprehensive than the CORUM data--it contains proteins that aren't included in the CORUM data.
    Parameters:
    update (bool, optional): Whether to download the latest version of the file from CORUM. Default True. Otherwise, uses a previously downloaded copy (if one exists).

    Returns:
    dict: Keys are complex names; values are lists of proteins in each complex.
    """

    # Set the paths we need
    path_here = os.path.abspath(os.path.dirname(__file__))
    data_files_path = os.path.join(path_here, "data")
    corum_file_path = os.path.join(data_files_path, 'corum_protein_complexes.tsv.zip')

    if update:

        corum_url = "https://mips.helmholtz-muenchen.de/corum/download/allComplexes.txt.zip"

        try:
            response = requests.get(corum_url)
            response.raise_for_status() # Raises a requests.HTTPError if the response code was unsuccessful

        except requests.RequestException: # Parent class for all exceptions in the requests module
            warnings.warn("Insufficient internet to update data file. Data from most recent download will be used.", FileNotUpdatedWarning, stacklevel=2)

        else:
            # Check that the data directory exists, create if it doesn't
            if not os.path.isdir(data_files_path):
                os.mkdir(data_files_path)

            # Save the file
            with open(corum_file_path, 'wb') as dest:
                dest.write(response.content)

    # Make sure the file exists
    if not os.path.isfile(corum_file_path):
        raise MissingFileError("CORUM data file has not been downloaded previously, and either you passed False to the 'update' parameter, or there wasn't sufficient internet to update the file (in which case a warning has been issued telling you that). Depending on which of these situations is currently yours, either pass True to the 'update' parameter, or try again when you have a better internet connection.")

    member_proteins = pd.read_csv(corum_file_path, sep='\t')
    member_proteins = member_proteins.loc[member_proteins['Organism'] == 'Human']
    member_proteins = member_proteins.set_index("ComplexName")

    # Select the member proteins column and split the proteins in each complex into values of a list
    member_proteins = member_proteins['subunits(Gene name)'].str.split(';')

    # For complexes with multiple entries (due to different samples), combine the lists
    member_proteins = member_proteins.groupby(member_proteins.index).agg(sum) # Sum will concatenate lists
    member_proteins = member_proteins.apply(set).apply(sorted) # Get rid of duplicates by converting to set. Then go back to list.
    member_proteins = member_proteins.to_dict()

    return member_proteins

def get_hgnc_protein_lists(update=True):
    """Reads file from the HGNC gene family dataset and returns a dictionary where the keys are protein complex names, and the values are lists of proteins that are members of those complexes. Data downloaded from the HGNC BioMart server (https://biomart.genenames.org/). We also provide get_corum_protein_lists to get similar data from CORUM. The HGNC data is more comprehensive than the CORUM data--it contains proteins that aren't included in the CORUM data. Additionally, the CORUM data has more specific subgroups than HGNC, so the HGNC data is easier to query when we just want all proteins associated with a particular structure.

    Parameters:
    update (bool, optional): Whether to download the latest version of the file from HGNC. Default True. Otherwise, uses a previously downloaded copy (if one exists).

    Returns:
    dict: Keys are complex names; values are lists of proteins in each complex.
    """
    # Set the paths we need
    path_here = os.path.abspath(os.path.dirname(__file__))
    data_files_path = os.path.join(path_here, "data")
    hgnc_file_path = os.path.join(data_files_path, 'hgnc_protein_families.tsv')

    if update:

        xml_query = '<!DOCTYPE Query><Query client="biomartclient" processor="TSV" limit="-1" header="1"><Dataset name="hgnc_family_mart" config="family_config"><Attribute name="family__name_103"/><Attribute name="family__gene__symbol_104"/></Dataset></Query>'
        hgnc_biomart_url = "https://biomart.genenames.org/martservice/results"

        try:
            response = requests.post(hgnc_biomart_url, data={"query": xml_query})
            response.raise_for_status() # Raises a requests.HTTPError if the response code was unsuccessful

        except requests.RequestException: # Parent class for all exceptions in the requests module
            warnings.warn("Insufficient internet to update data file. Data from most recent download will be used.", FileNotUpdatedWarning, stacklevel=2)

        else:
            # Check that the data directory exists, create if it doesn't
            if not os.path.isdir(data_files_path):
                os.mkdir(data_files_path)

            # Save the file
            with open(hgnc_file_path, 'wb') as dest:
                dest.write(response.content)

    # Make sure the file exists
    if not os.path.isfile(hgnc_file_path):
        raise MissingFileError("HGNC data file has not been downloaded previously, and either you passed False to the 'update' parameter, or there wasn't sufficient internet to update the file (in which case a warning has been issued telling you that). Depending on which of these situations is currently yours, either pass True to the 'update' parameter, or try again when you have a better internet connection.")

    # Read the file
    member_proteins = pd.read_csv(hgnc_file_path, sep='\t')
    member_proteins = member_proteins.set_index("Family name")
    member_proteins = member_proteins["Approved symbol"]

    # Combine multiple rows per family into one row with a list
    member_proteins = member_proteins.groupby(member_proteins.index).agg(list)
    member_proteins = member_proteins.apply(set).apply(sorted) # Get rid of duplicates by converting to set. Then go back to list.
    member_proteins = member_proteins.to_dict()

    return member_proteins
