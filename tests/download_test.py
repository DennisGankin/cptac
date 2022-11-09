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

import time
import cptac
import logging
import pytest
from itertools import product
from cptac.exceptions import InvalidParameterError

class TestDownload:
    '''
    A class for testing the loading of datasets

    Methods
    -------
    test_datasets_download:
        test downloading the datasets
    '''
    def inputs():
        # get options df from cptac
        options = cptac.get_options()
        options.drop(["Loadable datatypes"],  axis=1, inplace=True)
        options.set_index("Cancers")

        # convert Datatypes from type string to type list
        options.Datatypes = options.Datatypes.apply(lambda x: x.split(", "))

        # make a list of [(cancer, {source:datatype})] items
        combos = options.apply(lambda x: [(x[0], {source: datatype}) for (source, datatype) in list(product([x[1]], x[2]))], axis=1)
        
        # return a flattened list of (cancer, {source:datatype}) items
        return [item for sublist in combos.to_list() for item in sublist]

    # def get_public_datasets(get_all_datasets):
    #     public_datasets = []
    #     for dataset in get_all_datasets:
    #         if dataset.loc[dataset, "Data reuse stats"] == "no restricions":
    #             public_datasets.append(dataset.lower())
    #     return public_datasets


    @pytest.mark.parametrize("cancer, source", inputs())
    def test_datasets_redownload(self, cancer, source):
        time.sleep(1)
        # awgconf is currently password protected, so to speed up test time:
        if 'awgconf' not in source:
            assert cptac.download(sources=source, cancers=cancer, redownload=True)

    @pytest.mark.parametrize("cancer, source", inputs())
    def test_datasets_no_redownload(self, cancer, source):
        time.sleep(1)
        if 'awgconf' not in source:
            assert cptac.download(sources=source, cancers=cancer, redownload=False)

