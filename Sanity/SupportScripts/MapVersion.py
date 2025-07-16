import requests

url = "http://vtbe.vocatooki.com/data/get-class-map/344"
num_requests = 1000

for i in range(num_requests):
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx or 5xx)
        print(f"Request {i + 1} successful")
    except requests.RequestException as e:
        print(f"Request {i + 1} failed: {e}")

# If you want to see a specific message for failure, you can customize the exception handling
