"""
AltTester MCP Integration — Command-line wrapper for programmatic game control.

Enables real-time game automation via `alttester` CLI commands while the MCP server runs.
Use this for advanced automation scenarios, CI/CD integration, or parallel test execution.

Example:
    mcp = AltTesterMCP()
    mcp.connect("MyGame")
    button = mcp.find("PlayButton")
    mcp.tap(button)
    text = mcp.get_text("ScoreLabel")
    mcp.disconnect()
"""

import subprocess
import json
import time
from typing import Optional, Dict, List, Any
from pathlib import Path


class AltTesterMCPError(Exception):
    """Base exception for AltTester MCP operations."""
    pass


class AltTesterMCP:
    """
    Programmatic interface to AltTester CLI via MCP server.

    Assumes `alttester mcp` is running in a separate terminal/process.
    """

    def __init__(self, host: str = "127.0.0.1", port: int = 13000):
        """
        Initialize MCP client configuration.

        Args:
            host: Server host (default: localhost)
            port: Server port (default: 13000)
        """
        self.host = host
        self.port = port
        self.session_name: Optional[str] = None

    def _run_command(self, *args, json_output: bool = False) -> str:
        """
        Execute an alttester CLI command.

        Args:
            *args: Command arguments (e.g., "find", "PlayButton", "--by", "NAME")
            json_output: Parse response as JSON

        Returns:
            Command output (raw or parsed)

        Raises:
            AltTesterMCPError: On command failure
        """
        cmd = ["alttester", f"--host={self.host}", f"--port={self.port}"]

        if self.session_name:
            cmd.extend(["--session", self.session_name])

        cmd.extend(args)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )

            if result.returncode != 0:
                raise AltTesterMCPError(
                    f"Command failed: {' '.join(cmd)}\n"
                    f"stderr: {result.stderr}"
                )

            output = result.stdout.strip()

            if json_output and output:
                try:
                    return json.loads(output)
                except json.JSONDecodeError as e:
                    raise AltTesterMCPError(f"Failed to parse JSON: {output}") from e

            return output

        except subprocess.TimeoutExpired:
            raise AltTesterMCPError(f"Command timeout: {' '.join(cmd)}")
        except FileNotFoundError:
            raise AltTesterMCPError(
                "alttester CLI not found. Install via: alttester install-cli"
            )

    def connect(self, app_name: str, timeout: int = 5, session_name: Optional[str] = None):
        """
        Connect to a running game instance.

        Args:
            app_name: Game/app name registered with AltTester
            timeout: Connection timeout in seconds
            session_name: Optional session name for multiple concurrent connections

        Raises:
            AltTesterMCPError: If connection fails
        """
        self.session_name = session_name
        self._run_command("connect", "--app-name", app_name, "--timeout", str(timeout))

    def disconnect(self):
        """Disconnect from the current game session."""
        try:
            self._run_command("disconnect")
        except AltTesterMCPError:
            pass  # Already disconnected is okay

    def status(self) -> Dict[str, Any]:
        """Check connection status."""
        output = self._run_command("status")
        return {"status": output}

    def find(self, value: str, by: str = "NAME", contains: bool = False,
             wait: bool = True, timeout: int = 20) -> Dict[str, Any]:
        """
        Find a game object.

        Args:
            value: Object name/identifier
            by: Locator strategy (NAME, PATH, ID, TAG, LAYER, TEXT, COMPONENT)
            contains: Partial name match
            wait: Wait for object to appear
            timeout: Search timeout in seconds

        Returns:
            AltObject dict with: name, id, x, y, enabled, type, etc.
        """
        cmd = ["find", value, "--by", by]
        if contains:
            cmd.append("--contains")
        if wait:
            cmd.extend(["--wait", "--timeout", str(timeout)])

        return self._run_command(*cmd, json_output=True)

    def find_all(self, value: str, by: str = "NAME",
                 enabled_only: bool = False) -> List[Dict[str, Any]]:
        """Find all matching objects."""
        cmd = ["find", value, "--by", by, "--all"]
        if enabled_only:
            cmd.append("--enabled-only")

        output = self._run_command(*cmd, json_output=True)
        return output if isinstance(output, list) else [output]

    def find_at_coordinates(self, x: int, y: int) -> Dict[str, Any]:
        """Find object at specific screen coordinates."""
        return self._run_command(
            "find-at-coordinates", "--x", str(x), "--y", str(y),
            json_output=True
        )

    def get_all_elements(self, enabled_only: bool = False) -> List[Dict[str, Any]]:
        """Get all game objects in the scene."""
        cmd = ["get-all-elements"]
        if enabled_only:
            cmd.append("--enabled-only")

        output = self._run_command(*cmd, json_output=True)
        return output if isinstance(output, list) else [output]

    def tap(self, obj_or_name: str, count: int = 1, by: str = "NAME") -> None:
        """
        Tap/click an object (mobile-style).

        Args:
            obj_or_name: Object name or AltObject dict
            count: Number of taps
            by: Locator strategy
        """
        name = obj_or_name if isinstance(obj_or_name, str) else obj_or_name["name"]
        cmd = ["tap", name, "--by", by]
        if count > 1:
            cmd.extend(["--count", str(count)])
        self._run_command(*cmd)

    def click(self, obj_or_name: str, by: str = "NAME") -> None:
        """Click an object (desktop-style)."""
        name = obj_or_name if isinstance(obj_or_name, str) else obj_or_name["name"]
        self._run_command("click", name, "--by", by)

    def press(self, key: str, duration: float = 0.1) -> None:
        """
        Press a keyboard key.

        Args:
            key: Key name (e.g., "Return", "Space", "Escape")
            duration: Press duration in seconds
        """
        self._run_command("press", key, "--duration", str(duration))

    def key_down(self, key: str) -> None:
        """Press and hold a key."""
        self._run_command("key-down", key)

    def key_up(self, key: str) -> None:
        """Release a held key."""
        self._run_command("key-up", key)

    def swipe(self, start_x: int, start_y: int, end_x: int, end_y: int,
              duration: float = 0.5) -> None:
        """Swipe from one position to another."""
        self._run_command(
            "swipe",
            "--start-x", str(start_x), "--start-y", str(start_y),
            "--end-x", str(end_x), "--end-y", str(end_y),
            "--duration", str(duration)
        )

    def scroll(self, vertical: int = -1, duration: float = 0.5) -> None:
        """
        Scroll the screen.

        Args:
            vertical: Scroll direction (-1=down, 1=up)
            duration: Scroll duration
        """
        self._run_command("scroll", "--vertical", str(vertical), "--duration", str(duration))

    def move_mouse(self, x: int, y: int, duration: float = 0.5) -> None:
        """Move mouse cursor to coordinates."""
        self._run_command("move-mouse", "--x", str(x), "--y", str(y), "--duration", str(duration))

    def get_text(self, obj_or_name: str, by: str = "NAME") -> str:
        """Get text content of an object."""
        name = obj_or_name if isinstance(obj_or_name, str) else obj_or_name["name"]
        return self._run_command("get-text", name, "--by", by)

    def set_text(self, obj_or_name: str, text: str, by: str = "NAME") -> None:
        """Set text content of an object."""
        name = obj_or_name if isinstance(obj_or_name, str) else obj_or_name["name"]
        self._run_command("set-text", name, "--text", text, "--by", by)

    def screenshot(self, path: str = "screenshot.png") -> str:
        """
        Take a screenshot.

        Args:
            path: Output file path

        Returns:
            Path to saved screenshot
        """
        self._run_command("screenshot", "--path", path)
        return path

    def get_property(self, obj_or_name: str, component: str, property_name: str,
                     assembly: str = "", by: str = "NAME") -> Any:
        """
        Get a component property value.

        Args:
            obj_or_name: Object name
            component: Component class name
            property_name: Property name
            assembly: Assembly name (optional)
            by: Locator strategy

        Returns:
            Property value
        """
        name = obj_or_name if isinstance(obj_or_name, str) else obj_or_name["name"]
        cmd = [
            "get-property", name,
            "--component", component, "--property", property_name,
            "--by", by
        ]
        if assembly:
            cmd.extend(["--assembly", assembly])

        return self._run_command(*cmd, json_output=True)

    def set_property(self, obj_or_name: str, component: str, property_name: str,
                     value: str, assembly: str = "", by: str = "NAME") -> None:
        """Set a component property value."""
        name = obj_or_name if isinstance(obj_or_name, str) else obj_or_name["name"]
        cmd = [
            "set-property", name,
            "--component", component, "--property", property_name,
            "--set-value", value, "--by", by
        ]
        if assembly:
            cmd.extend(["--assembly", assembly])

        self._run_command(*cmd)

    def get_scene(self) -> str:
        """Get current scene name."""
        return self._run_command("scene", "--list")

    def load_scene(self, scene_name: str) -> None:
        """Load a scene by name."""
        self._run_command("scene", "--load", scene_name)

    def game_state(self, root: Optional[str] = None) -> Dict[str, Any]:
        """Get full game object hierarchy."""
        cmd = ["game-state"]
        if root:
            cmd.extend(["--root", root])
        return self._run_command(*cmd, json_output=True)

    def snapshot(self, show: bool = False, file_path: Optional[str] = None) -> str:
        """
        Get or display a snapshot of the game state.

        Returns:
            Path to snapshot file
        """
        cmd = ["snapshot"]
        if show:
            cmd.append("--show")
        if file_path:
            cmd.extend(["--file", file_path])
        return self._run_command(*cmd)

    def screen_size(self) -> Dict[str, int]:
        """Get screen resolution."""
        return self._run_command("screen-size", json_output=True)

    def get_time_scale(self) -> float:
        """Get game time scale."""
        return float(self._run_command("get-time-scale"))

    def set_time_scale(self, scale: float) -> None:
        """
        Set game time scale.

        Args:
            scale: 0 = paused, 1 = normal, 2 = 2x speed, etc.
        """
        self._run_command("set-time-scale", str(scale))

    def reset_input(self) -> None:
        """Reset all active input states."""
        self._run_command("reset-input")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit — automatically disconnect."""
        self.disconnect()


class AltTesterMCPHelper:
    """High-level test helper wrapping common patterns."""

    def __init__(self, mcp: AltTesterMCP):
        self.mcp = mcp

    def wait_for_object(self, name: str, by: str = "NAME", timeout: int = 20) -> Dict[str, Any]:
        """Wait for object to appear."""
        return self.mcp.find(name, by=by, wait=True, timeout=timeout)

    def tap_and_wait(self, name: str, wait_for: str, by: str = "NAME") -> Dict[str, Any]:
        """Tap an object then wait for another to appear."""
        self.mcp.tap(name, by=by)
        time.sleep(0.5)
        return self.wait_for_object(wait_for, by=by)

    def read_and_verify(self, obj_name: str, expected_text: str, by: str = "NAME") -> bool:
        """Get text from object and verify it matches."""
        actual = self.mcp.get_text(obj_name, by=by)
        return actual == expected_text

    def login_flow(self, username_field: str, password_field: str,
                   login_button: str, username: str, password: str) -> None:
        """Perform a login sequence."""
        self.mcp.set_text(username_field, username)
        self.mcp.set_text(password_field, password)
        self.mcp.tap(login_button)
        time.sleep(2)
