import json

file_path = "C:\\Users\\SanadAwesat\\Downloads\\response.json"
with open(file_path, 'r') as file:
    data = json.load(file)

total_score = 0

for level_data in data.values():
    for score_data in level_data.values():
        if isinstance(score_data, dict) and "score" in score_data:
            scores = score_data["score"]
            if isinstance(scores, list):
                total_score += sum(scores)

print("Total Score:", total_score)