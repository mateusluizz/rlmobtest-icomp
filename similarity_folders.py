import os
import re


def compare_documents_in_folder(folder_path):
    # List to store the names of similar files
    similar_files = []
    files_to_discard = []  # List to store the names of files to be discarded

    # Get the list of files in the provided directory
    file_list = os.listdir(folder_path)

    # Loop to compare all pairs of files
    for i in range(len(file_list)):
        for j in range(i+1, len(file_list)):
            file1 = os.path.join(folder_path, file_list[i])
            file2 = os.path.join(folder_path, file_list[j])
            similarity_percentage = compare_documents(file1, file2)

            # Check the similarity between the files
            if similarity_percentage > 90:
                similar_files.append((file_list[i], file_list[j]))

                # Determine which file can be discarded based on the number of lines
                lines_file1 = len(open(file1).readlines())
                lines_file2 = len(open(file2).readlines())

                if lines_file1 < lines_file2:
                    files_to_discard.append(file1)
                else:
                    files_to_discard.append(file2)

    return similar_files, remover_duplicatas(files_to_discard)

def remover_duplicatas(lista):
    lista_unica = list(set(lista))
    return lista_unica

def list_arquivos(folder_path, files_to_exclude):
    # Get the list of files in the provided directory
    file_list = os.listdir(folder_path)

    list_docs = []
    # Loop to list the files, excluding those present in the files_to_exclude list
    for file_name in file_list:
        file_path = os.path.join(folder_path, file_name)
        if file_path not in files_to_exclude:
            list_docs.append(file_path)
    
    return list_docs


def compare_documents(doc1, doc2):
    # Read the content of the first document and preprocess the lines
    with open(doc1, 'r') as file1:
        text1 = file1.read().splitlines()
        lines1 = set(preprocess(text1))
    # Read the content of the second document and preprocess the lines
    with open(doc2, 'r') as file2:
        text2 = file2.read().splitlines()
        lines2 = set(preprocess(text2))
    # Find the common lines between the two documents
    common_lines = lines1.intersection(lines2)
    # Calculate the similarity percentage based on the number of common lines
    similarity_percentage = (len(common_lines) / min(len(lines1), len(lines2))) * 100

    return similarity_percentage


def preprocess(text):
    # Define a regular expression pattern to match screen references
    screen_pattern = re.compile(r'Screen: states/state_\d{8}-\d{6}\.png')
    # Process each line in the text and replace screen references with '<SCREEN>'
    processed_lines = []
    for line in text:
        processed_line = re.sub(screen_pattern, '<SCREEN>', line)
        processed_lines.append(processed_line)

    return processed_lines