import json

def check_word_in_contexts(json_data, word):
    for item in json_data:
        word_contexts = item["word_contexts"]
        for context in word_contexts:
            if word in context["context"]:
                return True
    return False

# Specify the path to the JSON file
json_file = r"C:\AR_wordlist.json"

# Load JSON data from the file
with open(json_file, 'r', encoding='utf-8') as file:
    json_data = json.load(file)

words_not_found = []

for item in json_data:
    word = item["word"]
    if not check_word_in_contexts(json_data, word):
        words_not_found.append(word)

if words_not_found:
    print("The following words do not appear in any 'context' field:")
    for word in words_not_found:
        print("- {}".format(word))
else:
    print("All words appear in at least one 'context' field.")
