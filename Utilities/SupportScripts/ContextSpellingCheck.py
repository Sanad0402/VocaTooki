import json
import openai
import difflib

# Set your OpenAI API key here
api_key = "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"

# Define the path to your JSON file
json_file_path = "C:\\Users\\SanadAwesat\\Downloads\\AR_wordlist.json"

# Initialize the OpenAI API client
openai.api_key = api_key


# Function to check spelling of a list of contexts
def check_spelling(contexts):
    corrected_contexts = []

    for context in contexts:
        response = openai.Completion.create(
            engine="text-davinci-002",
            prompt=f"Check the spelling of the following text: '{context}'\n",
            max_tokens=50,  # Adjust as needed
            n=1,
            stop=None,
            temperature=0,
        )

        corrected_text = response.choices[0].text.strip()
        corrected_contexts.append(corrected_text)
        differences = count_differing_words(context, corrected_text)

        if differences <= 3:
            # Print the results live
            print(f"Original context: {context}")
            print(f"Corrected context: {corrected_text}")
            print(f"Differences:\n{display_differences(context, corrected_text)}")
            print("------")

    return corrected_contexts


# Function to extract contexts from the JSON data
def extract_contexts_from_json(json_data):
    contexts = []
    for word_obj in json_data:
        word_contexts = word_obj.get("word_contexts")
        if word_contexts:
            for context_obj in word_contexts:
                context = context_obj.get("context")
                if context:
                    contexts.append(context)
    return contexts


# Function to display differences between two strings
def display_differences(original, corrected):
    d = difflib.Differ()
    diff = list(d.compare(original.split(), corrected.split()))
    highlighted_diff = ' '.join(diff)
    return highlighted_diff


# Function to count the number of differing words
def count_differing_words(original, corrected):
    original_words = original.split()
    corrected_words = corrected.split()
    count = 0

    for orig_word, corrected_word in zip(original_words, corrected_words):
        if orig_word != corrected_word:
            count += 1

    return count


# Read the JSON file and parse its contents
with open(json_file_path, "r", encoding="utf-8") as json_file:
    data = json.load(json_file)

# Extract contexts from the JSON data
contexts_to_check = extract_contexts_from_json(data)

# Check spelling of the extracted contexts
corrected_contexts = check_spelling(contexts_to_check)

print("Spelling check completed.")
