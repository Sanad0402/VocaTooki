import json
import os

# Load the JSON data from the provided JSON file with 'utf-8' encoding
with open("C:/Users/SanadAwesat/Downloads/AR_wordlist.json", 'r', encoding='utf-8') as json_file:
    data = json.load(json_file)

# Load the list of audio file names from the provided text file
with open("C:/Users/SanadAwesat/Downloads/audio_files_vocatooki.txt", 'r') as audio_file:
    audio_files = [line.strip() for line in audio_file]

# Create a set of audio file names for faster lookup
audio_set = set(audio_files)

# Iterate through the words and phrases in the JSON data and check for audio file existence
for item in data:
    word = item['word']
    # Remove spaces and convert to lowercase for phrases
    audio_filename = word.replace(" ", "_").lower() + ".mp3"

    # Check if the corresponding audio file does not exist
    if audio_filename not in audio_set:
        print(f"the word or phrase '{word}' doesn't have audio")

# Check for phrases in the audio files
for audio_filename in audio_files:
    if "_" in audio_filename:
        # Convert back to the original phrase format
        phrase = audio_filename.split(".mp3")[0].replace("_", " ").title()
        # Check if the corresponding phrase does not exist in the JSON data
        if not any(item['word'] == phrase for item in data):
            print(f"'{phrase}' audio exists but not found in JSON data")
