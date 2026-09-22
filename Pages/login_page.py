import time
from alttester import By


class LoginPage:
    """
    LoginPage (Page Object Model)

    What is this class?
    - It represents the Login screen in the app.
    - Instead of writing "find username field, type, find password field, type, click login"
      in every test, we keep it here in one place.

    What this class does:
    1) Checks if the login screen is currently open
    2) Enters username
    3) Enters password
    4) Clicks the login button
    """

    # These are the Unity object names on the Login screen.
    # We keep them here so if the UI name changes, we change it only once.
    USER_INPUT = "UserInputField"
    PASSWORD_INPUT = "PasswordInputField"
    LOGIN_BUTTON = "LoginButton"
    Apple_Login = "Apple"
    Google_Login = "Google"
    Microsoft_Login = "Microsoft"
    MOE_Login = "MinistryOfEducationLogin"
    Sign_Up_Button = "SignUpButton"
    Login_Title = "WelcomeText"
    NOTIF_TEXT = "notifText"
    LOCATION_BUTTON = "LocationButton"
    EXIT_BUTTON = "Exit"

    BRAZIL_CHECKMARK_PATH = (
        "/NewLoginSystem/SelectionPanel/LocationSelectCanvas(Clone)/Panel/Scroll View/Viewport/Content/CountryTextToggle(Clone)[2]"
    )
    ISRAEL_CHECKMARK_PATH = (
        "/NewLoginSystem/SelectionPanel/LocationSelectCanvas(Clone)/Panel/Scroll View/Viewport/Content/CountryTextToggle(Clone)[5]"

    )

    def __init__(self, driver):
        """
        Constructor:
        - driver is the AltTester driver.
        - We save it so all functions can use it to find/click/type UI elements.
        """
        self.driver = driver

    def is_present(self, name: str) -> bool:
        """
        Step: Check if a UI element exists on the current screen.

        How it works:
        - If driver.find_object finds the element -> return True
        - If it throws an error (element not found) -> return False

        Why this is useful:
        - We can safely check the screen state without crashing the test.
        """
        try:
            self.driver.find_object(By.NAME, name)
            return True
        except Exception:
            return False

    def is_open(self) -> bool:
        """
        Step: Check if we are on the Login screen.

        We assume the Login screen is open if ALL 3 elements exist:
        - Username input field
        - Password input field
        - Login button
        """
        return (
            self.is_present(self.USER_INPUT)
            and self.is_present(self.PASSWORD_INPUT)
            and self.is_present(self.LOGIN_BUTTON)
        )

    def wait_until_open(self, timeout=10):
        """
        Step: Wait until the Login screen is shown (for slow loading).

        How it works:
        - We loop until 'timeout' seconds.
        - Every 0.5 seconds we check: is_open()?
        - If yes -> stop waiting and return.
        - If timeout is reached -> raise an error (test fails).

        Why we need it:
        - Sometimes UI takes time to appear after app launch / scene load.
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.is_open():
                return
            time.sleep(0.5)

        raise AssertionError("Login screen did not appear (User/Password/Login not found).")

    def set_username(self, username: str):
        """
        Step: Type the username in the username input field.

        - wait_for_object makes sure the field exists and is enabled.
        - set_text writes the username into the field.
        """
        self.driver.wait_for_object(By.NAME, self.USER_INPUT, enabled=True).set_text(username)

    def set_password(self, password: str):
        """
        Step: Type the password in the password input field.

        - wait_for_object makes sure the field exists and is enabled.
        - set_text writes the password into the field.
        """
        self.driver.wait_for_object(By.NAME, self.PASSWORD_INPUT, enabled=True).set_text(password)

    def click_login(self):
        """
        Step: Click the Login button to submit the credentials.
        """
        self.driver.wait_for_object(By.NAME, self.LOGIN_BUTTON).click()

    def login(self, username: str, password: str):
        """
        Step: Full login flow (one function that does everything).

        What it does in order:
        1) Wait until login screen is visible
        2) Enter username
        3) Enter password
        4) Click Login button
        """
        self.wait_until_open()
        self.set_username(username)
        self.set_password(password)
        self.click_login()

    def wait_until_notif_visible(self, timeout=5):
        """
        Wait until notifText exists on screen.
        (Some apps show it only after a failed login)
        """
        start = time.time()
        while time.time() - start < timeout:
            if self.is_present(self.NOTIF_TEXT):
                return
            time.sleep(0.2)

    def get_notif_text(self, timeout=2) -> str:
        """
        Returns the text shown in notifText.
        If notifText is missing or empty, returns "".
        """
        self.wait_until_notif_visible(timeout=timeout)

        try:
            notif_obj = self.driver.find_object(By.NAME, self.NOTIF_TEXT)
            text = (notif_obj.get_text() or "").strip()
            return text
        except Exception:
            return ""

    def select_israel_location(self):
        # 1) Open popup
        self.driver.find_object(By.NAME, self.LOCATION_BUTTON, enabled=True).click()
        time.sleep(2)

        # 2) Select region: Middle East
        self.driver.find_object(By.NAME, "Middle East", enabled=True).click()
        time.sleep(2)  # wait for country list to refresh

        # 3) Select Israel by PATH (checkmark)
        self.driver.find_object(By.PATH, self.ISRAEL_CHECKMARK_PATH, enabled=True).click()
        time.sleep(2)

        # 4) Close popup (Exit)
        self.driver.find_object(By.NAME, self.EXIT_BUTTON, enabled=True).click()
        time.sleep(10)


    def select_brazil_location(self):
        # 1) Open popup
        self.driver.find_object(By.NAME, self.LOCATION_BUTTON, enabled=True).click()
        time.sleep(3)

        # 2) Select region: South America
        self.driver.find_object(By.NAME, "South America").click()
        time.sleep(3)  # wait for country list refresh

        # 3) Select Brazil by PATH
        self.driver.find_object(By.PATH, self.BRAZIL_CHECKMARK_PATH, enabled=True).click()
        time.sleep(3)

        # 4) Close popup (Exit)
        self.driver.find_object(By.NAME, self.EXIT_BUTTON).click()
        time.sleep(10)

    def clear_username(self):
        self.driver.wait_for_object(By.NAME, self.USER_INPUT, enabled=True).set_text("")

    def clear_password(self):
        self.driver.wait_for_object(By.NAME, self.PASSWORD_INPUT, enabled=True).set_text("")
