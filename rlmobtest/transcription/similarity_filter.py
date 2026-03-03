#!/usr/bin/env python3
"""
Module for comparing and filtering similar test case documents.
"""

import os
import re


def compare_documents_in_folder(folder_path):
    """
    Compare all documents in a folder and identify similar ones.

    Returns:
        tuple: (similar_files, files_to_discard)
    """
    similar_files = []
    files_to_discard = []

    file_list = os.listdir(folder_path)

    for i in range(len(file_list)):
        for j in range(i + 1, len(file_list)):
            file1 = os.path.join(folder_path, file_list[i])
            file2 = os.path.join(folder_path, file_list[j])
            similarity_percentage = compare_documents(file1, file2)

            if similarity_percentage > 90:
                similar_files.append((file_list[i], file_list[j]))

                with open(file1, encoding="utf-8") as f1:
                    lines_file1 = len(f1.readlines())
                with open(file2, encoding="utf-8") as f2:
                    lines_file2 = len(f2.readlines())

                if lines_file1 < lines_file2:
                    files_to_discard.append(file1)
                else:
                    files_to_discard.append(file2)

    return similar_files, remove_duplicates(files_to_discard)


def remove_duplicates(lista):
    """Remove duplicate entries from a list."""
    return list(set(lista))


def list_arquivos(folder_path, files_to_exclude):
    """
    List all files in a folder excluding specified files.

    Args:
        folder_path: Path to the folder
        files_to_exclude: List of file paths to exclude

    Returns:
        list: List of file paths
    """
    file_list = os.listdir(folder_path)

    list_docs = []
    for file_name in file_list:
        file_path = os.path.join(folder_path, file_name)
        if file_path not in files_to_exclude:
            list_docs.append(file_path)

    return list_docs


def compare_documents(doc1, doc2):
    """
    Compare two documents and return similarity percentage.

    Args:
        doc1: Path to first document
        doc2: Path to second document

    Returns:
        float: Similarity percentage (0-100)
    """
    with open(doc1, encoding="utf-8") as file1:
        text1 = file1.read().splitlines()
        lines1 = set(preprocess(text1))

    with open(doc2, encoding="utf-8") as file2:
        text2 = file2.read().splitlines()
        lines2 = set(preprocess(text2))

    common_lines = lines1.intersection(lines2)
    similarity_percentage = (len(common_lines) / min(len(lines1), len(lines2))) * 100

    return similarity_percentage


def preprocess(text):
    """
    Preprocess text lines by normalizing variable references for similarity comparison.

    Args:
        text: List of text lines

    Returns:
        list: Processed lines with variable parts normalized
    """
    screen_pattern = re.compile(r"Screen: states/state_\d{8}-\d{6}\.png")
    state_pattern = re.compile(r"State \d+: states/state_\d{8}-\d{6}\.png")
    error_pattern = re.compile(r"Got Error, see errors\.txt line \d+")
    bounds_pattern = re.compile(r"bounds:\[\d+,\d+\]\[\d+,\d+\]")

    processed_lines = []
    for line in text:
        processed_line = re.sub(screen_pattern, "<SCREEN>", line)
        processed_line = re.sub(state_pattern, "<STATE>", processed_line)
        processed_line = re.sub(error_pattern, "<ERROR>", processed_line)
        processed_line = re.sub(bounds_pattern, "<BOUNDS>", processed_line)
        processed_lines.append(processed_line)

    return processed_lines
