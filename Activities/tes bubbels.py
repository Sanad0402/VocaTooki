import time
import alttester
from alttester import By, AltDriver

# Initialize AltDriver
altdriver = AltDriver(enable_logging=False)

# Find activity object
print("Searching for 'LettersBubbles_activity'...")
activity_obj = altdriver.find_object(By.NAME, 'LettersBubbles_activity')
activity_play_mode = int(activity_obj.get_component_property(
    'com.kideo.learn.english.LettersBubblesActivityManagement',
    'sessionData_.LettersActivityPlayMode',
    'Assembly-CSharp'
))
print(f"Activity Play Mode: {activity_play_mode}")

# Get the target letter
print("Retrieving target letter...")
letter_obj = altdriver.find_objects(By.NAME, 'WordPanel')
if not letter_obj:
    print("Error: No WordPanel objects found.")
    exit()

letter_text = letter_obj[0].get_component_property('WordPanel', 'word_.letter', 'Assembly-CSharp')

if letter_text:
    letter_text = letter_text.lower().strip()
    print(f"Target letter to match: {letter_text}")
else:
    print("Error: letter_text is None")
    exit()

# Continuously scan bubbles until activity progress indicates completion
while True:
    # Check if ExitButton exists
    try:
        print("Checking for ExitButton...")
        exit_button = altdriver.find_object(By.NAME, 'ExitButton')
        if exit_button:
            print("ExitButton found. Clicking and stopping execution.")
            exit_button.click()
            break  # Stop execution after clicking the ExitButton
    except alttester.exceptions.NotFoundException:
        print("ExitButton not found, continuing...")

    # Scan bubbles objects
    print("Scanning for bubbles...")
    time.sleep(5)
    bubbels_objs = altdriver.find_objects(By.NAME, 'LettersBubble(Clone)')

    if not bubbels_objs:
        print("No bubbles found, skipping iteration.")
        continue  # Skip to the next loop iteration

    for index, bubble in enumerate(bubbels_objs):
        print(f"\n🔍 Iteration {index}: Checking bubble...")

        # Skip first index
        if index == 0:
            print(f"Skipping bubble at index {index} (First item)")
            continue  # Skip the first index

        if not bubble:
            print(f"Skipping index {index}: Bubble object is None")
            continue

        try:
            # Initialize text as None
            text = None

            # Try to get 'alphabet.letter' first
            try:
                text = bubble.get_component_property('com.kideo.learn.english.LettersBubble', 'alphabet.letter', 'Assembly-CSharp')
                if text:
                    print(f"✅ Found 'alphabet.letter' for bubble at index {index}: {repr(text)}")
            except alttester.exceptions.NotFoundException:
                print(f"⚠️ 'alphabet.letter' not found for bubble at index {index}, falling back to 'alphabet.word'...")

            # Fallback to 'alphabet.word' if 'alphabet.letter' is empty or None
            if not text:
                try:
                    text = bubble.get_component_property('com.kideo.learn.english.LettersBubble', 'alphabet.word', 'Assembly-CSharp')
                    if text:
                        print(f"✅ Found 'alphabet.word' for bubble at index {index}: {repr(text)}")
                except alttester.exceptions.NotFoundException:
                    print(f"⚠️ 'alphabet.word' not found for bubble at index {index}, skipping...")

            # If both are still None or empty, skip this bubble
            if not text or text.strip() == "":
                print(f"⚠️ No valid text found for bubble at index {index}, skipping...")
                continue

            text = text.lower().strip()
            print(f"✅ Final text for bubble at index {index}: {text}")

            # Click the bubble if the letter matches
            if text == letter_text or text.startswith(letter_text):
                print(f"✅ Match found! Clicking bubble at index {index} 🚀")
                bubble.click()
            else:
                print(f"❌ No match for '{text}', skipping bubble at index {index}")

        except alttester.exceptions.NotFoundException:
            print(f"❌ Bubble at index {index} not found or destroyed, skipping.")
            continue  # Skip to the next bubble

    # Wait a short period before rescanning bubbles
    time.sleep(1)
