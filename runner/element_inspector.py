"""Element Inspector — Auto-discover AltTester elements via MCP.

This module queries the AltTester app hierarchy and provides utilities to:
- Get all available elements in the app
- Find elements by partial name match
- Cache element hierarchy for performance
- Auto-detect what elements are relevant for test steps
"""

import json
import logging
from typing import Optional, List, Dict, Any
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


class ElementInspector:
    """Auto-discovers AltTester elements via MCP without manual page objects."""

    def __init__(self, altdriver):
        """
        Initialize with AltDriver instance.

        Args:
            altdriver: The AltTester driver instance
        """
        self.driver = altdriver
        self._hierarchy_cache: Optional[Dict[str, Any]] = None
        self._element_map: Dict[str, List[str]] = {}

    def get_app_hierarchy(self, refresh: bool = False) -> Dict[str, Any]:
        """
        Get the full app element hierarchy.

        Args:
            refresh: Force reload from driver instead of cache

        Returns:
            Dict with 'root' element and all children recursively
        """
        if self._hierarchy_cache and not refresh:
            return self._hierarchy_cache

        try:
            root = self.driver.get_root()
            self._hierarchy_cache = self._build_hierarchy(root)
            logger.info(f"App hierarchy loaded: {len(self._get_all_elements())} elements")
            return self._hierarchy_cache
        except Exception as e:
            logger.error(f"Failed to get app hierarchy: {e}")
            return {"root": None, "elements": []}

    def _build_hierarchy(self, element) -> Dict[str, Any]:
        """Recursively build hierarchy from root element."""
        result = {"root": element.name if element else None, "elements": []}

        if not element:
            return result

        visited = set()

        def traverse(elem, depth=0):
            if depth > 20:  # Prevent infinite recursion
                return
            if not elem:
                return

            try:
                elem_name = elem.name
                if elem_name in visited:
                    return
                visited.add(elem_name)

                elem_info = {
                    "name": elem_name,
                    "type": getattr(elem, "type", "Unknown"),
                    "enabled": getattr(elem, "enabled", True),
                    "children": [],
                }
                result["elements"].append(elem_info)

                try:
                    children = elem.get_child_count()
                    for i in range(children):
                        try:
                            child = elem.get_child(i)
                            traverse(child, depth + 1)
                        except Exception:
                            pass
                except Exception:
                    pass
            except Exception as e:
                logger.debug(f"Error traversing element at depth {depth}: {e}")

        traverse(element)
        return result

    def _get_all_elements(self) -> List[str]:
        """Get flat list of all element names."""
        if not self._hierarchy_cache:
            return []
        return [e["name"] for e in self._hierarchy_cache.get("elements", [])]

    def find_element(self, pattern: str, threshold: float = 0.6) -> Optional[str]:
        """
        Find element by partial name match (fuzzy).

        Args:
            pattern: Element name pattern (partial or full)
            threshold: Similarity threshold (0-1)

        Returns:
            Best matching element name or None
        """
        all_elements = self._get_all_elements()

        # Exact match
        if pattern in all_elements:
            return pattern

        # Fuzzy match
        best_match = None
        best_score = threshold

        for elem_name in all_elements:
            similarity = SequenceMatcher(None, pattern.lower(), elem_name.lower()).ratio()
            if similarity > best_score:
                best_score = similarity
                best_match = elem_name

        if best_match:
            logger.debug(f"Matched '{pattern}' → '{best_match}' (score: {best_score:.2f})")
        else:
            logger.warning(f"No element match for pattern: {pattern}")

        return best_match

    def get_elements_by_type(self, elem_type: str) -> List[str]:
        """Get all elements of a specific type (e.g., 'Button', 'InputField')."""
        if not self._hierarchy_cache:
            return []

        matching = [
            e["name"]
            for e in self._hierarchy_cache.get("elements", [])
            if e.get("type", "").lower() == elem_type.lower()
        ]
        return matching

    def get_input_fields(self) -> List[str]:
        """Get all input field elements."""
        return self.get_elements_by_type("InputField")

    def get_buttons(self) -> List[str]:
        """Get all button elements."""
        return self.get_elements_by_type("Button")

    def element_exists(self, name: str) -> bool:
        """Check if an element exists in the app."""
        return name in self._get_all_elements()

    def get_element_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for an element."""
        if not self._hierarchy_cache:
            return None

        for elem in self._hierarchy_cache.get("elements", []):
            if elem["name"] == name:
                return elem
        return None

    def discover_inputs_for_step(self, step_description: str) -> List[str]:
        """
        Auto-discover input fields relevant to a test step.

        E.g., "Enter username" → finds UserInputField, UsernameInput, etc.
        """
        keywords = step_description.lower().split()
        all_inputs = self.get_input_fields()

        relevant = []
        for inp in all_inputs:
            inp_lower = inp.lower()
            if any(kw in inp_lower for kw in keywords):
                relevant.append(inp)

        return relevant or all_inputs  # Fallback: return all inputs if no match

    def discover_buttons_for_action(self, action_description: str) -> List[str]:
        """
        Auto-discover buttons relevant to an action.

        E.g., "Click login" → finds LoginButton, SubmitButton, etc.
        """
        keywords = action_description.lower().split()
        all_buttons = self.get_buttons()

        relevant = []
        for btn in all_buttons:
            btn_lower = btn.lower()
            if any(kw in btn_lower for kw in keywords):
                relevant.append(btn)

        return relevant or all_buttons  # Fallback: return all buttons

    def as_dict(self) -> Dict[str, Any]:
        """Export hierarchy as dict (for debugging/logging)."""
        return self._hierarchy_cache or {}
