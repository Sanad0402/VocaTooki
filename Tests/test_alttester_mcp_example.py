"""
Example: Using AltTester MCP for game automation.

This test demonstrates the high-level MCP wrapper for programmatic game control.
Perfect for CI/CD, parallel execution, or advanced automation scenarios.

Prerequisites:
  1. Start the AltTester MCP server: `alttester mcp`
  2. Have your game running with AltTester SDK instrumented
  3. Ensure the game is accessible on localhost:13000
"""

import pytest
import time
from Utilities.alttester_mcp import AltTesterMCP, AltTesterMCPHelper, AltTesterMCPError


@pytest.fixture
def mcp():
    """MCP client fixture."""
    client = AltTesterMCP(host="127.0.0.1", port=13000)
    yield client
    client.disconnect()


class TestAltTesterMCPBasics:
    """Basic MCP operations — object finding, interaction, verification."""

    def test_connect_and_status(self, mcp):
        """Test: Connect to game and check status."""
        # Connect to the game (replace "MyGame" with your actual app name)
        try:
            mcp.connect("MyGame", timeout=5)
        except AltTesterMCPError as e:
            pytest.skip(f"Game not running: {e}")

        # Verify connection
        status = mcp.status()
        assert status is not None

    def test_find_object(self, mcp):
        """Test: Find a game object by name."""
        try:
            mcp.connect("MyGame", timeout=5)
        except AltTesterMCPError:
            pytest.skip("Game not running")

        # Find button (adapt to your game's UI)
        obj = mcp.find("PlayButton", by="NAME", wait=True, timeout=10)

        assert obj is not None
        assert "name" in obj
        assert "x" in obj and "y" in obj
        print(f"Found object: {obj['name']} at ({obj['x']}, {obj['y']})")

    def test_find_at_coordinates(self, mcp):
        """Test: Find object at specific screen position."""
        try:
            mcp.connect("MyGame", timeout=5)
        except AltTesterMCPError:
            pytest.skip("Game not running")

        # Find what's at center of screen
        obj = mcp.find_at_coordinates(960, 540)
        print(f"Object at (960, 540): {obj}")

    def test_screen_size(self, mcp):
        """Test: Get game screen resolution."""
        try:
            mcp.connect("MyGame", timeout=5)
        except AltTesterMCPError:
            pytest.skip("Game not running")

        size = mcp.screen_size()
        assert "width" in size or "height" in size
        print(f"Screen size: {size}")


class TestAltTesterMCPInteraction:
    """User interaction — taps, clicks, text input."""

    def test_tap_object(self, mcp):
        """Test: Tap a button."""
        try:
            mcp.connect("MyGame", timeout=5)
        except AltTesterMCPError:
            pytest.skip("Game not running")

        # Tap PlayButton
        mcp.tap("PlayButton", count=1)
        time.sleep(1)

        # Verify button was tapped (e.g., scene changed)
        # Adapt this to your game's behavior
        print("PlayButton tapped successfully")

    def test_set_and_get_text(self, mcp):
        """Test: Set text in input field and read it back."""
        try:
            mcp.connect("MyGame", timeout=5)
        except AltTesterMCPError:
            pytest.skip("Game not running")

        # Set text in input field (adapt to your game)
        input_field = "UsernameInput"
        mcp.set_text(input_field, "testuser@example.com")
        time.sleep(0.5)

        # Read it back
        actual_text = mcp.get_text(input_field)
        assert actual_text == "testuser@example.com"
        print(f"Text field value: {actual_text}")

    def test_keyboard_input(self, mcp):
        """Test: Keyboard input (key press)."""
        try:
            mcp.connect("MyGame", timeout=5)
        except AltTesterMCPError:
            pytest.skip("Game not running")

        # Press Escape key
        mcp.press("Escape", duration=0.1)
        time.sleep(0.5)
        print("Escape key pressed")

    def test_swipe_gesture(self, mcp):
        """Test: Swipe gesture (mobile-style)."""
        try:
            mcp.connect("MyGame", timeout=5)
        except AltTesterMCPError:
            pytest.skip("Game not running")

        # Swipe from right to left (common in mobile UIs)
        mcp.swipe(start_x=800, start_y=400, end_x=200, end_y=400, duration=0.5)
        time.sleep(0.5)
        print("Swipe gesture executed")


class TestAltTesterMCPSnapshot:
    """Game state inspection — snapshots, screenshots."""

    def test_screenshot(self, mcp, tmp_path):
        """Test: Take a screenshot."""
        try:
            mcp.connect("MyGame", timeout=5)
        except AltTesterMCPError:
            pytest.skip("Game not running")

        screenshot_path = str(tmp_path / "game_screenshot.png")
        result = mcp.screenshot(path=screenshot_path)
        assert result is not None
        print(f"Screenshot saved to: {result}")

    def test_game_state_snapshot(self, mcp):
        """Test: Get full game object hierarchy."""
        try:
            mcp.connect("MyGame", timeout=5)
        except AltTesterMCPError:
            pytest.skip("Game not running")

        state = mcp.game_state()
        assert state is not None
        print(f"Game state keys: {list(state.keys()) if isinstance(state, dict) else 'list'}")

    def test_get_scene(self, mcp):
        """Test: Get current scene name."""
        try:
            mcp.connect("MyGame", timeout=5)
        except AltTesterMCPError:
            pytest.skip("Game not running")

        scene = mcp.get_scene()
        assert scene is not None
        print(f"Current scene: {scene}")


class TestAltTesterMCPWithHelper:
    """Using the high-level helper for common patterns."""

    def test_wait_and_tap_flow(self, mcp):
        """Test: Wait for object to appear, then tap it."""
        try:
            mcp.connect("MyGame", timeout=5)
        except AltTesterMCPError:
            pytest.skip("Game not running")

        helper = AltTesterMCPHelper(mcp)

        # Wait for button to appear (up to 20 seconds)
        obj = helper.wait_for_object("PlayButton")
        assert obj is not None

        # Tap it
        mcp.tap(obj)
        time.sleep(1)
        print("Wait-and-tap completed")

    def test_text_verification_flow(self, mcp):
        """Test: Verify text content in UI element."""
        try:
            mcp.connect("MyGame", timeout=5)
        except AltTesterMCPError:
            pytest.skip("Game not running")

        helper = AltTesterMCPHelper(mcp)

        # Check if score label shows expected value
        is_correct = helper.read_and_verify("ScoreLabel", "Score: 100")
        print(f"Score verification: {is_correct}")


class TestAltTesterMCPContextManager:
    """Using MCP with context manager for automatic cleanup."""

    def test_with_context_manager(self):
        """Test: Using MCP as context manager."""
        try:
            with AltTesterMCP() as mcp:
                mcp.connect("MyGame", timeout=5)

                # Perform operations
                obj = mcp.find("PlayButton")
                assert obj is not None

                # Connection automatically closed on exit
        except AltTesterMCPError as e:
            pytest.skip(f"Game not running: {e}")


# ============================================================================
# Integration with Rally Automation Framework
# ============================================================================

class TestMCPWithRally:
    """Example: MCP in Rally-generated tests."""

    def test_rally_scenario_mcp_based(self, mcp):
        """
        Example Rally scenario:
        Scenario: Play game and verify score
        Given: Game is running
        When: User taps Play button
        And: Game plays for 5 seconds
        Then: Score should increase
        """
        try:
            mcp.connect("MyGame", timeout=5)
        except AltTesterMCPError:
            pytest.skip("Game not running")

        # Get initial score
        initial_score = mcp.get_text("ScoreLabel")
        print(f"Initial score: {initial_score}")

        # Tap play button
        mcp.tap("PlayButton")
        time.sleep(5)

        # Get updated score
        updated_score = mcp.get_text("ScoreLabel")
        print(f"Updated score: {updated_score}")

        # Verify score increased (simple comparison)
        assert updated_score != initial_score, "Score should have changed"


if __name__ == "__main__":
    # Quick manual test (when MCP server is running)
    # python -m pytest Tests/test_alttester_mcp_example.py::TestAltTesterMCPBasics::test_connect_and_status -v

    pytest.main([__file__, "-v", "-s"])
