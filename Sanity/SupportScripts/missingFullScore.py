import json

# Read data from file
file_path = "C:\\Users\\SanadAwesat\\Downloads\\testtest.json"
with open(file_path, "r") as file:
    data = json.load(file)

# Iterate through data and filter out values
for key, value in data.items():
    if 'score' in value:
        scores = value['score']
        if isinstance(scores, int):  # If scores is an integer, convert it to a list
            scores = [scores]
        if not any(score in scores for score in [80, 420, 1160]):
            print(f"Values in level {value['level']} do not contain 80, 420, or 1160.")
