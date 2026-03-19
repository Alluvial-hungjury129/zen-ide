"""
API Key Setup Popup for Zen IDE.

NvimPopup-based dialog for configuring HTTP AI provider API keys.
Saves keys to ~/.zen_ide/api_keys.json.

For Copilot, supports GitHub OAuth device flow — users can authenticate
directly from Zen IDE without needing any other editor installed.
"""

import json
import threading
import webbrowser
from pathlib import Path

from gi.repository import Gdk, GLib, Gtk

from popups.nvim_popup import NvimPopup

_API_KEYS_PATH = Path.home() / ".zen_ide" / "api_keys.json"


def _load_api_keys() -> dict:
    """Load existing api_keys.json or return empty dict."""
    try:
        if _API_KEYS_PATH.exists():
            return json.loads(_API_KEYS_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_api_keys(data: dict):
    """Save api_keys.json, creating parent directory if needed."""
    _API_KEYS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _API_KEYS_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


class ApiKeySetupPopup(NvimPopup):
    """Popup for entering API keys for HTTP AI providers."""

    def __init__(
        self,
        parent: Gtk.Window,
        provider: str,
        on_complete=None,
    ):
        """
        Args:
            parent: Parent window.
            provider: Provider ID — "anthropic_api" or "copilot_api".
            on_complete: Callback when key is saved successfully. Receives provider ID.
        """
        self._provider = provider
        self._on_complete = on_complete
        self._oauth_polling = False
        self._oauth_device_code = None
        self._oauth_poll_source = None
        self._oauth_flow_active = False  # True from "Sign in" click until flow ends

        if provider == "anthropic_api":
            title = "Anthropic API Setup"
            self._key_field = "anthropic"
            self._key_placeholder = "sk-ant-..."
            self._key_env_var = "ANTHROPIC_API_KEY"
            self._has_base_url = False
        elif provider == "copilot_api":
            title = "Copilot Setup"
            self._key_field = "github"
            self._key_placeholder = "ghp_... or gho_..."
            self._key_env_var = "GITHUB_TOKEN"
            self._has_base_url = False
        else:
            title = "Anthropic API Setup"
            self._key_field = "anthropic"
            self._key_placeholder = "sk-ant-..."
            self._key_env_var = "ANTHROPIC_API_KEY"
            self._has_base_url = False

        # Load existing values
        self._existing_keys = _load_api_keys()
        self._existing_key = self._existing_keys.get(self._key_field, "")

        super().__init__(parent, title, width=520)

    def _create_content(self):
        """Create the API key setup form."""
        if self._provider == "copilot_api":
            self._create_copilot_content()
        else:
            self._create_key_content()

    def _create_copilot_content(self):
        """Create Copilot-specific content with OAuth sign-in option."""
        # OAuth sign-in section
        oauth_label = self._create_message_label("Sign in with your GitHub account to use Copilot models.", wrap=False)
        self._content_box.append(oauth_label)

        # Sign in button
        signin_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        signin_box.set_margin_top(12)
        signin_box.set_halign(Gtk.Align.START)

        self._signin_btn = Gtk.Button(label="Sign in with GitHub")
        self._signin_btn.add_css_class("nvim-popup-action")
        self._signin_btn.connect("clicked", self._on_start_oauth)
        signin_box.append(self._signin_btn)
        self._content_box.append(signin_box)

        # OAuth status area (hidden by default)
        self._oauth_status_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self._oauth_status_box.set_margin_top(12)
        self._oauth_status_box.set_visible(False)
        self._content_box.append(self._oauth_status_box)

        # Divider
        divider_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        divider_box.set_margin_top(16)
        divider_box.set_margin_bottom(8)
        divider_label = Gtk.Label(label="── or enter token manually ──")
        divider_label.set_opacity(0.4)
        divider_label.add_css_class("nvim-popup-hint")
        divider_box.append(divider_label)
        self._content_box.append(divider_box)

        # Manual token entry (compact)
        key_label = Gtk.Label(label="GitHub Token")
        key_label.set_halign(Gtk.Align.START)
        key_label.add_css_class("nvim-popup-hint")
        self._content_box.append(key_label)

        self._key_entry = self._create_input_entry(self._key_placeholder, self._existing_key)
        self._key_entry.set_visibility(False)
        self._key_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self._content_box.append(self._key_entry)

        # Auto-detect hint
        auto_hint = Gtk.Label(label="Existing Copilot auth from other editors is also auto-detected")
        auto_hint.set_halign(Gtk.Align.START)
        auto_hint.add_css_class("nvim-popup-hint")
        auto_hint.set_margin_top(4)
        auto_hint.set_opacity(0.6)
        self._content_box.append(auto_hint)

        # Error label
        self._error_label = Gtk.Label()
        self._error_label.set_halign(Gtk.Align.START)
        self._error_label.add_css_class("nvim-popup-hint")
        self._error_label.set_visible(False)
        self._error_label.set_margin_top(4)
        self._content_box.append(self._error_label)

        # Hint bar
        hint_bar = self._create_hint_bar([("Enter", "save token"), ("Esc", "cancel")])
        hint_bar.set_halign(Gtk.Align.END)
        hint_bar.set_margin_top(8)
        self._content_box.append(hint_bar)

        self._key_entry.connect("activate", self._on_activate)

    def _create_key_content(self):
        """Create standard API key entry content (Anthropic)."""
        # Description
        desc = "Enter your Anthropic API key to use Claude models directly."

        desc_label = self._create_message_label(desc)
        self._content_box.append(desc_label)

        # API Key label
        key_label = Gtk.Label(label="API Key")
        key_label.set_halign(Gtk.Align.START)
        key_label.add_css_class("nvim-popup-hint")
        key_label.set_margin_top(8)
        self._content_box.append(key_label)

        # API Key entry (password-style)
        self._key_entry = self._create_input_entry(self._key_placeholder, self._existing_key)
        self._key_entry.set_visibility(False)  # Mask the key
        self._key_entry.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self._content_box.append(self._key_entry)

        # Toggle visibility button
        vis_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        vis_box.set_halign(Gtk.Align.START)
        self._vis_check = Gtk.CheckButton(label="Show key")
        self._vis_check.connect("toggled", self._on_visibility_toggled)
        vis_box.append(self._vis_check)
        self._content_box.append(vis_box)

        # Env var hint
        env_hint = Gtk.Label(label=f"Or set {self._key_env_var} environment variable")
        env_hint.set_halign(Gtk.Align.START)
        env_hint.add_css_class("nvim-popup-hint")
        env_hint.set_margin_top(12)
        env_hint.set_opacity(0.6)
        self._content_box.append(env_hint)

        # Error label (hidden by default)
        self._error_label = Gtk.Label()
        self._error_label.set_halign(Gtk.Align.START)
        self._error_label.add_css_class("nvim-popup-hint")
        self._error_label.set_visible(False)
        self._error_label.set_margin_top(4)
        self._content_box.append(self._error_label)

        # Hint bar
        hint_bar = self._create_hint_bar([("Enter", "save"), ("Esc", "cancel")])
        hint_bar.set_halign(Gtk.Align.END)
        hint_bar.set_margin_top(8)
        self._content_box.append(hint_bar)

        # Connect Enter key on key entry
        self._key_entry.connect("activate", self._on_activate)

    # ------------------------------------------------------------------
    # OAuth device flow (Copilot)
    # ------------------------------------------------------------------

    def _on_start_oauth(self, button):
        """Start GitHub OAuth device flow."""
        from ai.copilot_http_provider import CopilotHTTPProvider

        self._oauth_flow_active = True
        self._signin_btn.set_sensitive(False)
        self._signin_btn.set_label("Starting...")
        # Show interim waiting text so blank screen is never visible
        self._oauth_status_box.set_visible(True)
        for child in list(self._oauth_status_box):
            self._oauth_status_box.remove(child)
        interim_label = Gtk.Label(label="Waiting for GitHub device code...")
        interim_label.set_halign(Gtk.Align.START)
        interim_label.add_css_class("nvim-popup-hint")
        self._oauth_status_box.append(interim_label)

        def start_flow():
            result = CopilotHTTPProvider.start_device_flow()
            GLib.idle_add(self._on_device_flow_started, result)

        threading.Thread(target=start_flow, daemon=True).start()

    def _on_device_flow_started(self, result):
        """Handle device flow start result (main thread)."""
        if not result:
            # Maintain OAuth status box visible with error message, do not close popup.
            self._oauth_flow_active = False
            for child in list(self._oauth_status_box):
                self._oauth_status_box.remove(child)
            error_label = Gtk.Label(label="✗ Failed to start OAuth flow. Check your network connection.")
            error_label.set_halign(Gtk.Align.START)
            error_label.add_css_class("nvim-popup-hint")
            self._oauth_status_box.append(error_label)
            self._signin_btn.set_sensitive(True)
            self._signin_btn.set_visible(True)
            self._signin_btn.set_label("Sign in with GitHub")
            self._error_label.set_text("")
            self._error_label.set_visible(False)
            return

        self._oauth_device_code = result["device_code"]
        user_code = result["user_code"]
        verification_uri = result["verification_uri"]
        interval = result.get("interval", 5)

        # Update UI to show the user code
        self._signin_btn.set_visible(False)
        self._oauth_status_box.set_visible(True)

        # Clear previous children
        child = self._oauth_status_box.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self._oauth_status_box.remove(child)
            child = next_child

        step1 = Gtk.Label(label=f"1. Open {verification_uri}")
        step1.set_halign(Gtk.Align.START)
        step1.add_css_class("nvim-popup-hint")
        self._oauth_status_box.append(step1)

        code_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        code_box.set_margin_top(8)
        code_label = Gtk.Label(label="2. Enter code:")
        code_label.add_css_class("nvim-popup-hint")
        code_box.append(code_label)

        code_value = Gtk.Label(label=user_code)
        code_value.add_css_class("nvim-popup-title")
        code_value.set_selectable(True)
        code_box.append(code_value)
        self._oauth_status_box.append(code_box)

        self._oauth_waiting_label = Gtk.Label(label="⏳ Waiting for authorization...")
        self._oauth_waiting_label.set_halign(Gtk.Align.START)
        self._oauth_waiting_label.add_css_class("nvim-popup-hint")
        self._oauth_waiting_label.set_margin_top(8)
        self._oauth_status_box.append(self._oauth_waiting_label)

        # Open browser (but DO NOT close or hide the popup!)
        try:
            webbrowser.open(verification_uri)
        except Exception:
            pass

        # Start polling — track how many polls for UX feedback and timeout
        self._oauth_polling = True
        self._oauth_poll_count = 0
        self._oauth_expires_in = result.get("expires_in", 900)
        # Use a safe interval: at least 8 seconds to avoid slow_down errors
        # GitHub returns interval=5 but recommends adding a buffer
        poll_interval = max(interval + 3, 8)
        poll_ms = poll_interval * 1000
        self._oauth_poll_interval_s = poll_interval
        self._oauth_poll_source = GLib.timeout_add(poll_ms, self._poll_oauth)

    def _poll_oauth(self):
        """Poll for OAuth token (called from GLib timeout).

        We guard against overlapping polls with ``_oauth_poll_inflight``.
        If a previous poll thread hasn't finished yet, we skip this tick
        and let the timer fire again on the next interval.
        """
        if not self._oauth_polling:
            return False

        # Guard: skip if a previous poll is still in-flight
        if getattr(self, "_oauth_poll_inflight", False):
            return True

        self._oauth_poll_inflight = True

        def poll():
            from ai.copilot_http_provider import CopilotHTTPProvider

            try:
                result = CopilotHTTPProvider.poll_device_flow(self._oauth_device_code)
                # Handle both old (2-tuple) and new (3-tuple) return format
                if len(result) == 3:
                    token, status, new_interval = result
                else:
                    token, status = result
                    new_interval = 5
            except Exception as exc:
                import traceback

                traceback.print_exc()
                token, status, new_interval = None, "error", 5
            GLib.idle_add(self._on_oauth_poll_result, token, status, new_interval)

        threading.Thread(target=poll, daemon=True).start()
        return True  # Keep timer alive

    def _stop_oauth_polling(self):
        """Centralised helper to tear down OAuth polling state."""
        self._oauth_polling = False
        self._oauth_flow_active = False
        self._oauth_poll_inflight = False
        if self._oauth_poll_source:
            GLib.source_remove(self._oauth_poll_source)
            self._oauth_poll_source = None

    def _on_oauth_poll_result(self, token, status, new_interval):
        """Handle OAuth poll result (main thread)."""
        # Clear in-flight flag so next timer tick can poll again
        self._oauth_poll_inflight = False
        self._oauth_poll_count = getattr(self, "_oauth_poll_count", 0) + 1

        if status == "complete" and token:
            self._stop_oauth_polling()
            self._oauth_waiting_label.set_text("✓ Signed in successfully!")
            self._result = token
            callback = self._on_complete
            provider = self._provider
            GLib.timeout_add(800, self._close_after_oauth, callback, provider)
            return
        elif status == "expired":
            self._stop_oauth_polling()
            self._oauth_waiting_label.set_text("✗ Code expired. Please try again.")
            self._signin_btn.set_visible(True)
            self._signin_btn.set_sensitive(True)
            self._signin_btn.set_label("Sign in with GitHub")
            return
        elif status == "error":
            self._stop_oauth_polling()
            self._oauth_waiting_label.set_text("✗ Authentication error. Please try again.")
            self._signin_btn.set_visible(True)
            self._signin_btn.set_sensitive(True)
            self._signin_btn.set_label("Sign in with GitHub")
            return
        elif status == "slow_down":
            # GitHub wants us to slow down — reschedule with new interval
            current_interval = getattr(self, "_oauth_poll_interval_s", 5)
            if new_interval > current_interval:
                self._oauth_poll_interval_s = new_interval
                # Cancel current timer and start a new one with the slower interval
                if self._oauth_poll_source:
                    GLib.source_remove(self._oauth_poll_source)
                self._oauth_poll_source = GLib.timeout_add(new_interval * 1000, self._poll_oauth)
            # Fall through to update UI as "pending"

        # status == "pending" or "slow_down" — still waiting
        # Show elapsed time and remaining time for user feedback
        elapsed_s = int(self._oauth_poll_count * getattr(self, "_oauth_poll_interval_s", 5))
        expires_in = getattr(self, "_oauth_expires_in", 900)
        remaining_s = max(0, expires_in - elapsed_s)
        remaining_min = remaining_s // 60
        remaining_sec = remaining_s % 60
        self._oauth_waiting_label.set_text(
            f"⏳ Waiting for authorization... ({remaining_min}:{remaining_sec:02d} remaining)"
        )

    def _close_after_oauth(self, callback, provider):
        """Close popup after successful OAuth (delayed for UX)."""
        self.close()
        if callback:
            callback(provider)
        return False

    # ------------------------------------------------------------------
    # Focus handling — prevent close during OAuth flow
    # ------------------------------------------------------------------

    def _on_focus_leave(self, controller):
        """Override: don't close the popup when focus leaves during OAuth.

        When the browser opens for the device flow, the popup loses focus.
        We must keep it open so the user can see the device code.
        """
        if self._oauth_flow_active:
            # OAuth in progress — ignore focus loss
            return
        super()._on_focus_leave(controller)

    def _dismiss_click_outside(self):
        """Override: don't dismiss on outside click during OAuth flow."""
        if self._oauth_flow_active:
            return False
        return super()._dismiss_click_outside()

    # ------------------------------------------------------------------
    # Common handlers
    # ------------------------------------------------------------------

    def _on_visibility_toggled(self, check_button):
        """Toggle API key visibility."""
        self._key_entry.set_visibility(check_button.get_active())

    def _on_activate(self, entry):
        """Handle Enter key."""
        self._save_key()

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        """Handle key press."""
        if keyval == Gdk.KEY_Escape:
            self._stop_oauth_polling()
            self._result = None
            self.close()
            return True
        return False

    def _validate_key(self, key: str) -> str | None:
        """Validate API key format. Returns error message or None."""
        if not key.strip():
            return "API key is required"
        if len(key.strip()) < 10:
            return "API key seems too short"
        return None

    def _save_key(self):
        """Save the API key to ~/.zen_ide/api_keys.json."""
        key = self._key_entry.get_text().strip()

        error = self._validate_key(key)
        if error:
            self._error_label.set_text(error)
            self._error_label.set_visible(True)
            return

        # Build data to save
        data = self._existing_keys.copy()
        data[self._key_field] = key

        try:
            _save_api_keys(data)
        except Exception as e:
            self._error_label.set_text(f"Failed to save: {e}")
            self._error_label.set_visible(True)
            return

        self._result = key
        callback = self._on_complete
        provider = self._provider
        self.close()
        if callback:
            callback(provider)

    def present(self):
        """Show the dialog and focus the key entry (or interim box for OAuth)."""
        super().present()
        if hasattr(self, "_key_entry"):
            self._key_entry.grab_focus()
            if self._existing_key:
                self._key_entry.select_region(0, -1)
        elif self._provider == "copilot_api" and hasattr(self, "_signin_btn"):
            self._signin_btn.grab_focus()


def show_api_key_setup(parent: Gtk.Window, provider: str, on_complete=None):
    """Show the API key setup popup.

    Args:
        parent: Parent window.
        provider: "anthropic_api" or "copilot_api".
        on_complete: Callback when key saved. Receives provider ID.
    """
    dialog = ApiKeySetupPopup(parent, provider, on_complete)
    dialog.present()
    return dialog
