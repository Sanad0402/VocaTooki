import pytest
from Pages.LoginPage import LoginPage
from Pages.StartScreen import StartScreen
from Pages.new_page import NewPage

@pytest.mark.newpage
class TestNewPage:

    @pytest.fixture(autouse=True)
    def setup(self, altdriver, user):
        self.driver, self.platform = altdriver

        LoginPage(self.driver).login(user["username"], user["password"])
        StartScreen(self.driver).wait_until_open(timeout=25)

        yield

    def test_open_new_page(self):
        # navigate (your StartScreen method that you created)
        page = StartScreen(self.driver).go_to_new_page(timeout=25)
        assert page.is_open(), "New page should be open"

    def test_save_title(self):
        page = StartScreen(self.driver).go_to_new_page(timeout=25)

        page.set_title("Hello")
        page.save()

        # assert expected result (examples):
        # 1) success popup exists
        # 2) text appears somewhere
        # 3) scene changed
        assert page.is_open(), "Still should be on NewPage after save (change this to real assert)"


# ✅ Every TC should look like:
#page = StartScreen(driver).go_to_new_page()
#page.do_action()
#assert something_happened

