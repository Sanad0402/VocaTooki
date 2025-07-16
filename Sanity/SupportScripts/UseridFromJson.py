import json

# Path to your JSON file
file_path = "C:\\Users\\sanad\\Downloads\\new 2.json"

# Read JSON data from file
with open(file_path, 'r', encoding='utf-8') as file:
    data = json.load(file)

# Extracting user IDs
user_ids = [item['user_id'] for item in data]
print(user_ids)

'''''''''
also it can be typed like this

user_ids = []

for item in data:
    user_ids.append(item['user_id'])


print(user_ids) 
'''''''''