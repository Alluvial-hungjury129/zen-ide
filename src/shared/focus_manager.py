"""
Focus Manager for Zen IDE.

Manages focus state for main IDE components (terminal, editor, treeview, AI chat).
When a component gains focus, it shows a colored border and scrollbars.
When unfocused, the border dims and scrollbars are hidden.
"""

from typing import Callable, Dict, Optional

# Singleton instance for component focus management
_focus_manager_instance: Optional["FocusManager"] = None


def get_focus_manager() -> "FocusManager":
    """Get the singleton FocusManager instance."""
    global _focus_manager_instance
    if _focus_manager_instance is None:
        _focus_manager_instance = FocusManager()
    return _focus_manager_instance


class FocusManager:
    """
    Manages focus state for main IDE components (terminal, editor, treeview, etc.).

    When a component gains focus, all other registered components are automatically
    notified to unfocus.
    """

    def __init__(self):
        self._components: Dict[str, dict] = {}
        self._current_focus: Optional[str] = None

    def register(
        self,
        component_id: str,
        on_focus_in: Optional[Callable[[], None]] = None,
        on_focus_out: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Register a component with its focus callbacks.

        Args:
            component_id: Unique identifier for the component
            on_focus_in: Called when this component gains focus
            on_focus_out: Called when this component loses focus
        """
        self._components[component_id] = {
            "on_focus_in": on_focus_in,
            "on_focus_out": on_focus_out,
            "has_focus": False,
        }

    def set_focus(self, component_id: str) -> None:
        """
        Set focus to a component, automatically unfocusing others.
        """
        if component_id not in self._components:
            return

        # Already focused? No-op
        if self._current_focus == component_id:
            return

        # Unfocus previously focused component
        if self._current_focus and self._current_focus in self._components:
            old_component = self._components[self._current_focus]
            old_component["has_focus"] = False
            if old_component["on_focus_out"]:
                try:
                    old_component["on_focus_out"]()
                except Exception:
                    self._report_callback_error(component_id=self._current_focus, callback_name="on_focus_out")

        # Focus the new component
        self._current_focus = component_id
        component = self._components[component_id]
        component["has_focus"] = True
        if component["on_focus_in"]:
            try:
                component["on_focus_in"]()
            except Exception:
                self._report_callback_error(component_id=component_id, callback_name="on_focus_in")

    def clear_focus(self, component_id: str) -> None:
        """Clear focus from a component without focusing another."""
        if component_id not in self._components:
            return

        component = self._components[component_id]
        if component["has_focus"]:
            component["has_focus"] = False
            if component["on_focus_out"]:
                try:
                    component["on_focus_out"]()
                except Exception:
                    self._report_callback_error(component_id=component_id, callback_name="on_focus_out")
            if self._current_focus == component_id:
                self._current_focus = None

    def has_focus(self, component_id: str) -> bool:
        """Check if a component currently has focus."""
        if component_id not in self._components:
            return False
        return self._components[component_id]["has_focus"]

    def get_current_focus(self) -> Optional[str]:
        """Get the ID of the currently focused component, or None."""
        return self._current_focus

    def clear_all(self) -> None:
        """Clear focus from all components."""
        if self._current_focus and self._current_focus in self._components:
            self.clear_focus(self._current_focus)
        self._current_focus = None

    @staticmethod
    def _report_callback_error(component_id: str, callback_name: str) -> None:
        # Boundary catch: callbacks are plugin/UI boundaries. Surface failures to logs.
        try:
            from shared.crash_log import log_message

            log_message(f"Focus callback failed: component={component_id}, callback={callback_name}")
        except Exception:
            # Avoid recursive failures in crash logging.
            pass
