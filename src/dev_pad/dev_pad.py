"""
Dev Pad - Activity tracking panel for Zen IDE.

Shows a chronological list of user activities (file edits, AI chats, git operations)
with clickable links to quickly resume work.
"""

import json
import os
import subprocess
import threading
import webbrowser
from typing import Callable, Optional

from gi.repository import GLib, Gtk

from dev_pad.activity_renderer import ActivityRendererMixin

# Re-export all public helpers so that existing imports from dev_pad.dev_pad
# continue to work unchanged.
from dev_pad.activity_store import (  # noqa: F401
    _abbreviate_path,
    _get_activity_icon,
    _get_sketch_preview,
    log_ai_activity,
    log_custom_activity,
    log_file_activity,
    log_git_activity,
    log_github_pr_activity,
    log_new_file_activity,
    log_search_activity,
    log_sketch_activity,
    remove_new_file_activity,
)
from dev_pad.dev_pad_storage import NOTES_DIR, DevPadActivity, get_dev_pad_storage
from icons import Icons
from shared.main_thread import main_thread_call
from themes import ThemeAwareMixin


class DevPad(ActivityRendererMixin, ThemeAwareMixin, Gtk.Box):
    """
    Activity tracking panel that shows recent user activities.
    Uses a scrolled window with native GTK widgets.
    """

    def __init__(
        self,
        open_file_callback: Optional[Callable[[str], None]] = None,
        open_ai_chat_callback: Optional[Callable[[str], None]] = None,
        open_repo_callback: Optional[Callable[[str], None]] = None,
        focus_tab_callback: Optional[Callable[[int], None]] = None,
        get_workspace_folders_callback: Optional[Callable[[], list[str]]] = None,
        new_ai_chat_callback: Optional[Callable[[], None]] = None,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self.open_file_callback = open_file_callback
        self.open_ai_chat_callback = open_ai_chat_callback
        self.open_repo_callback = open_repo_callback
        self.focus_tab_callback = focus_tab_callback
        self.get_workspace_folders_callback = get_workspace_folders_callback
        self.new_ai_chat_callback = new_ai_chat_callback

        self._storage = get_dev_pad_storage()
        self._storage.add_listener(self._on_storage_change)

        # Track activities for click handling
        self._activity_links: dict[str, DevPadActivity] = {}
        self._link_tag_counter = 0

        # Search and filter state
        self._search_query = ""
        self._type_filter: set[str] | None = None

        self._setup_ui()
        self._apply_styles()

        self._subscribe_theme()

    def refresh(self):
        """Public method to refresh the activity list."""
        self._refresh()

    def _on_link_click(self, activity: DevPadActivity):
        """Handle click on an activity link."""

        # Sketch activities: open the .zen_sketch file
        if activity.activity_type == "sketch" and activity.link_type == "file" and self.open_file_callback:
            self.open_file_callback(activity.link_target)
            return

        if activity.link_type == "file" and self.open_file_callback:
            self.open_file_callback(activity.link_target)
        elif activity.link_type == "ai_chat" and self.open_ai_chat_callback:
            self.open_ai_chat_callback(activity.link_target)
        elif activity.link_type == "repo" and self.open_repo_callback:
            self.open_repo_callback(activity.link_target)
        elif activity.link_type == "tab" and self.focus_tab_callback:
            try:
                tab_id = int(activity.link_target)
                self.focus_tab_callback(tab_id)
            except (ValueError, TypeError):
                pass
        elif activity.link_type == "url":
            webbrowser.open(activity.link_target)
        elif activity.link_type == "note":
            # Open note for editing
            self._edit_note(activity)

    def _on_delete_activity(self, activity: DevPadActivity):
        """Delete a single activity."""
        self._storage.delete_activity(activity.id)

    def _edit_note(self, activity: DevPadActivity):
        """Open note as a markdown file in the editor."""
        # Create notes directory if needed
        NOTES_DIR.mkdir(parents=True, exist_ok=True)

        # Create .md file for legacy notes that don't have one yet
        safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in activity.title)
        safe_name = safe_name.replace(" ", "_").lower()[:60]
        if not safe_name:
            safe_name = "note"

        note_path = NOTES_DIR / f"{safe_name}.md"
        counter = 1
        while note_path.exists():
            note_path = NOTES_DIR / f"{safe_name}_{counter}.md"
            counter += 1

        icon = _get_activity_icon(activity.activity_type)
        note_path.write_text(f"# {icon} {activity.title}\n\n", encoding="utf-8")

        # Update activity to point to the file
        self._storage.update_activity(activity.id, link_type="file", link_target=str(note_path))

        # Open in editor
        if self.open_file_callback:
            self.open_file_callback(str(note_path))

    def _on_clear_all(self, button):
        """Clear all activities after confirmation."""
        from popups.confirm_dialog import show_confirm

        if self._type_filter is None and not self._search_query:
            msg = "Are you sure you want to clear all activities?"
        else:
            msg = "Are you sure you want to clear the currently visible activities?"

        parent = self.get_root()
        show_confirm(
            parent,
            title="Clear Dev Pad",
            message=msg,
            danger=True,
            on_confirm=lambda: self._storage.clear_all(type_filter=self._type_filter, filter_query=self._search_query),
        )

    def _on_refresh_prs(self, button):
        """Fetch open PRs from workspace repos using gh CLI."""
        if not self.get_workspace_folders_callback:
            return

        workspace_folders = self.get_workspace_folders_callback()
        if not workspace_folders:
            return

        # Update button to show loading
        self.refresh_prs_btn.set_label(f"{Icons.COG} Loading...")

        def fetch_prs_from_folder(folder):
            """Fetch PRs from a single folder."""
            if not os.path.isdir(folder):
                return []
            git_dir = os.path.join(folder, ".git")
            if not os.path.exists(git_dir):
                return []

            try:
                result = subprocess.run(
                    ["gh", "pr", "list", "--state=open", "--json=number,title,author,url,createdAt"],
                    cwd=folder,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0 and result.stdout.strip():
                    pr_list = json.loads(result.stdout)
                    repo_name = os.path.basename(folder)
                    results = []
                    for pr in pr_list:
                        author = pr.get("author", {}).get("login", "unknown")
                        title = pr.get("title", "")
                        url = pr.get("url", "")
                        created_at = pr.get("createdAt", "")
                        if author and title and url:
                            results.append((author, title, url, repo_name, created_at))
                    return results
            except Exception:
                pass
            return []

        def fetch_prs():
            from concurrent.futures import ThreadPoolExecutor, as_completed

            prs_found = []
            with ThreadPoolExecutor(max_workers=len(workspace_folders)) as executor:
                futures = {executor.submit(fetch_prs_from_folder, folder): folder for folder in workspace_folders}
                for future in as_completed(futures):
                    prs_found.extend(future.result())

            # Update UI on main thread
            main_thread_call(self._finish_refresh_prs, prs_found)

        threading.Thread(target=fetch_prs, daemon=True).start()

    def _finish_refresh_prs(self, prs_found: list):
        """Called when PR fetch completes."""
        self.refresh_prs_btn.set_label(f"{Icons.GIT_MERGE} Refresh PRs")

        if not prs_found:
            return

        for author, title, url, repo_name, created_at in prs_found:
            log_github_pr_activity(author, title, url, repo_name, created_at)

    def _on_storage_change(self):
        """Called when storage changes."""
        GLib.idle_add(lambda: self._refresh() or False)

    def _on_search_change(self, entry):
        """Called when search query changes."""
        self._search_query = entry.get_text()
        self._refresh()

    def _on_filter_click(self, filter_types: set[str] | None):
        """Handle click on a filter button."""
        self._type_filter = filter_types
        self._update_filter_button_styles()
        self._refresh()

    def _update_filter_button_styles(self):
        """Update filter button styles based on current selection."""
        for key, btn in self._filter_buttons.items():
            if key == "all":
                is_selected = self._type_filter is None
            else:
                is_selected = str(self._type_filter) == key

            if is_selected:
                btn.add_css_class("dev-pad-filter-active")
            else:
                btn.remove_css_class("dev-pad-filter-active")

    def _on_add_note(self, button):
        """Show dialog to add a new note."""
        from popups.input_dialog import show_input

        parent = self.get_root()
        show_input(
            parent,
            title="Add Note",
            message="Enter a title:",
            placeholder="What's on your mind?",
            on_submit=lambda title: self._add_note_with_title("note", title),
        )

    def _add_note_with_title(self, note_type: str, title: str):
        """Add a note with the given type and title, creating an .md file."""
        if not title.strip():
            return

        # Create notes directory if needed
        NOTES_DIR.mkdir(parents=True, exist_ok=True)

        # Create a sanitized filename from the title
        safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in title.strip())
        safe_name = safe_name.replace(" ", "_").lower()[:60]
        if not safe_name:
            safe_name = "note"

        # Ensure unique filename
        note_path = NOTES_DIR / f"{safe_name}.md"
        counter = 1
        while note_path.exists():
            note_path = NOTES_DIR / f"{safe_name}_{counter}.md"
            counter += 1

        # Create the .md file with the title as header
        icon = _get_activity_icon(note_type)
        note_path.write_text(f"# {icon} {title.strip()}\n\n", encoding="utf-8")

        self._storage.add_activity(
            activity_type=note_type,
            title=title.strip(),
            description="",
            link_type="file",
            link_target=str(note_path),
        )

    def _on_add_sketch(self, button):
        """Show dialog to add a new sketch."""
        from popups.input_dialog import show_input

        parent = self.get_root()
        show_input(
            parent,
            title="Add Sketch",
            message="Enter a name:",
            placeholder="My diagram",
            on_submit=self._add_sketch_with_name,
        )

    def _add_sketch_with_name(self, name: str):
        """Create a .zen_sketch file and open it in the sketch pad."""

        if not name.strip():
            return

        NOTES_DIR.mkdir(parents=True, exist_ok=True)

        safe_name = "".join(c if c.isalnum() or c in " -_" else "" for c in name.strip())
        safe_name = safe_name.replace(" ", "_").lower()[:60]
        if not safe_name:
            safe_name = "sketch"

        sketch_path = NOTES_DIR / f"{safe_name}.zen_sketch"
        counter = 1
        while sketch_path.exists():
            sketch_path = NOTES_DIR / f"{safe_name}_{counter}.zen_sketch"
            counter += 1

        empty_content = '{"version":3,"format":"sketch_pad","shapes":[]}'
        sketch_path.write_text(empty_content, encoding="utf-8")

        log_sketch_activity(content=empty_content, file_path=str(sketch_path))

        if self.open_file_callback:
            self.open_file_callback(str(sketch_path))

    def _on_theme_change(self, theme):
        """Handle theme change."""
        GLib.idle_add(lambda: self._apply_styles() or False)
        GLib.idle_add(lambda: self._refresh() or False)

    def show_panel(self):
        """Show the Dev Pad panel."""
        self.set_visible(True)
        self._refresh()

    def hide_panel(self):
        """Hide the Dev Pad panel."""
        self.set_visible(False)

    def destroy(self):
        """Clean up resources."""
        self._storage.remove_listener(self._on_storage_change)
