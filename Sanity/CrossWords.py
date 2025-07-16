import time

from alttester import By, AltKeyCode, AltDriver
def altdriver():
    altdriver = AltDriver(enable_logging=False)

def radar(altdriver):
    time.sleep(3)
    # Fetch all radar objects and the target word
    radar_objects = altdriver.find_objects(By.NAME, 'radarObj')
    answer_obj = altdriver.find_object(By.NAME, 'Radar_activity')
    target_word = answer_obj.get_component_property('com.kideo.learn.english.RadarActivityManagement', 'radarGameManager.targetWord', 'Assembly-CSharp')

    # List to hold the radar text values
    radar_objects_texts = []
    for radar_object in radar_objects:
        radar_text = radar_object.get_component_property('com.kideo.learn.english.RadarObjectController', 'word', 'Assembly-CSharp')
        radar_objects_texts.append(radar_text)

    # Iterate through radar objects and click on those that match the target word
    for index, radar_text in enumerate(radar_objects_texts):
        if radar_text == target_word:
            # Perform the first click
            radar_objects[index].click()
            # Wait for a short duration before the second click
            time.sleep(0.5)  # Adjust this delay as needed (0.5 seconds here)
            # Perform the second click
            radar_objects[index].click()
            continue
