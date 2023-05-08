import os
import zenodopy
import wget
import cptac

STATIC_DOI = '10.5281/zenodo.7897498'
INDEX_FILE_NAME = 'all_index.txt'
DATA_DIR = os.path.join(cptac.CPTAC_BASE_DIR, "data/")

def download_data(cancer, source, datatype):
    index_path = download_index_file_if_needed()

    file_urls = get_file_urls(cancer, source, datatype, index_path)

    output_folder = os.path.join(DATA_DIR, f"data_{source}_{cancer}")

    for url in file_urls:
        download_file(url, output_folder)

def download_index_file_if_needed():
    index_path = os.path.join(DATA_DIR, INDEX_FILE_NAME)
    if not os.path.exists(index_path):
        index_url = get_index_file_url()
        wget.download(index_url, index_path)

    return index_path

def get_index_file_url():
    zenodo = zenodopy.Client()
    record = zenodo.get_urls_from_doi(STATIC_DOI)

    for url in record:
        if url.endswith(INDEX_FILE_NAME):
            return url

    raise FileNotFoundError(f"Index file '{INDEX_FILE_NAME}' not found in Zenodo record (DOI: {STATIC_DOI})")

def get_file_urls(cancer, source, datatype, index_path):
    file_urls = []

    with open(index_path, 'r') as input:
        for line in input:
            columns = line.split('\t')
            identifiers = columns[0].split('_')

            if identifiers[0] == source and identifiers[1] == cancer and identifiers[2] == datatype:
                file_urls.append(columns[1].strip())

    return file_urls

def download_file(url, output_folder):
    file_name = url.split('/')[-1]
    output_path = os.path.join(output_folder, file_name)

    if not os.path.exists(output_path):
        wget.download(url, output_path)

