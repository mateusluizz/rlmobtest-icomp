from openai import OpenAI, APIError
from config import APIKEY
import os
import similarity_folders 

# OpenAI API KEY
client = OpenAI(api_key=APIKEY)

index = 0

def read_text_file(file_path):
    with open(file_path, 'r') as file:
        text = file.read()
        # Remove extra white spaces
        text = text.strip()
        # Remove blank lines
        text = '\n'.join(line for line in text.splitlines() if line.strip())
        return text

# Function to write into the file
def write_text_file(file_path, text):
    with open(file_path, 'w') as file:
        file.write(text)

def the_world_is_our(input_folder, output_folder):
    global index
    print(len(os.listdir(input_folder)))
    
    # Identify and discard similar documents
    similar_documents, documents_to_discard = similarity_folders.compare_documents_in_folder(input_folder)

    # List the remaining documents after discarding similar ones
    list_docs = similarity_folders.list_arquivos(input_folder, documents_to_discard)
    # Print the number of documents after similarity check
    print(len(list_docs))
    # Create the output folder if it doesn't exist
    os.makedirs(output_folder, exist_ok=True)
    print("=======The program is running=======")

    while index < len(list_docs):
        try:
            for i in list_docs[index:]:
                # Extract the base name of the file
                tc_name = os.path.basename(i)
                # Read the content of the current document
                input_text = read_text_file(i)

                # Generate a response using the OpenAI GPT-3.5 Turbo model
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo-1106",
                    messages=[
                        # Training the model using Few-Shot learning
                        {'role': 'user', 'content': read_text_file('files/Scripts/TC_.activity.account.AccountsActivity_20210411-144635.txt')},
                        {'role': 'assistant', 'content': read_text_file('files/Transcriptions/TC_.activity.account.AccountsActivity_20210411-144635.txt')},
                        {'role': 'user', 'content': read_text_file('files/Scripts/TC_.activity.account.TransferActivity_20210411-144754.txt')},
                        {'role': 'assistant', 'content': read_text_file('files/Transcriptions/TC_.activity.account.TransferActivity_20210411-144754.txt')},
                        {'role': 'user', 'content': input_text}
                    ],
                    max_tokens=1100,
                    n=1,
                    temperature=0.5
                )

                # Extract the generated output text
                output_text = response.choices[0].message.content.strip()
                # Construct the output file path and write the result to the file
                output_file_path = os.path.join(output_folder, tc_name)
                write_text_file(output_file_path, output_text)
                # Print a message indicating that the result has been saved to the file
                print("The result has been saved to the file", output_file_path)

                index += 1  # Increment the value of index

        except APIError as te:
            if te.http_status == "502":
                print(te)
                last_doc = index + list_docs[index:].index(i)
                print(f"Error occurred at index {last_doc} - {i}")
                index = last_doc

        except Exception as e:
            print(e)
            last_doc = index + list_docs[index:].index(i)
            print(f"Error occurred at index {last_doc} - {i}")
            index = last_doc + 1

    print("=======The program is finished========")
