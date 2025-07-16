import requests
import time

# Define the API endpoint URL
url = "http://vtbe.vocatooki.com/data/get-user-state"

# JSON body data
data = {
    "user_id": 15099,
    "avatar_version": 1,
    "awards_version": 1,
    "lessons_version": 12,
    "add_is_complete": False
}

# Number of retries for each request
max_retries = 3

# Number of requests to send
num_requests = 50

# Send the POST requests and display the level in each response
for request_num in range(1, num_requests + 1):
    for i in range(max_retries):
        try:
            response = requests.post(url, json=data)
            response.raise_for_status()  # Raise an exception if the response status code is not 200

            # Check if the request was successful (status code 200)
            result_data = response.json()
            print(f"Request {request_num}: Level {result_data['level']}")
            print(f"Request {request_num}: OpenLevel {result_data['opened_level']}")

            break  # Break the retry loop if successful
        except requests.exceptions.RequestException as e:
            print(f"Request {request_num}: Error - {e}")
            if i < max_retries - 1:
                print("Retrying in 5 seconds...")
                time.sleep(5)  # Wait for 5 seconds before retrying
            else:
                print("Max retries reached.")

    # Add a delay between requests (adjust as needed to comply with any rate limits)
    time.sleep(1)  # Wait for 1 second between requests
