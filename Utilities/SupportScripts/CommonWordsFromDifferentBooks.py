import json

def extract_words_from_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    word_set = set()
    for lesson in data.get("lessons", []):
        word_set.update(lesson.get("words", []))
    return word_set

def main():
    # File paths to the four JSON files
    json_files = [
        r"C:\Users\sanad\Downloads\10.json",
        r"C:\Users\sanad\Downloads\11.json",
        r"C:\Users\sanad\Downloads\12.json"

    ]
    # Extract words from each JSON file
    all_word_sets = [extract_words_from_json(path) for path in json_files]

    # Find common words
    common_words = set.intersection(*all_word_sets)

    # Output result
    print("✅ Common word IDs across all 4 classes:")
    print(sorted(common_words))

if __name__ == "__main__":
    main()