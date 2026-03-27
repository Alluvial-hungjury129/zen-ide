"""
TreeView actions mixin — context menu, new/rename/delete/discard operations.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from gi.repository import GLib

from icons import IconsManager
from treeview.tree_clipboard_mixin import TreeClipboardMixin
from treeview.tree_item import TreeItem


class TreeViewActionsMixin(TreeClipboardMixin):
    """Mixin providing file actions for TreeView."""

    def _show_context_menu(self, item, x, y):
        """Show context menu for a tree item using NvimContextMenu."""
        from popups.nvim_context_menu import show_context_menu

        items = []
        selection = self._get_action_items(item)
        single_item = selection[0] if len(selection) == 1 else None
        file_selection = [selected for selected in selection if not selected.is_dir]
        all_tests = bool(selection) and all(not selected.is_dir and self._is_test_file(selected) for selected in selection)
        can_discard = bool(selection) and all(
            not selected.is_dir and selected.git_status in ("M", "A", "D") for selected in selection
        )

        if single_item and single_item.is_dir:
            items.append({"label": "New File", "action": "new_file", "icon": IconsManager.FILE})
            items.append({"label": "New Folder", "action": "new_folder", "icon": IconsManager.FOLDER_CLOSED})
            items.append({"label": "---"})
        if file_selection:
            open_label = "Open" if len(file_selection) == 1 else f"Open {len(file_selection)} Files"
            items.append({"label": open_label, "action": "open", "icon": IconsManager.FILE})
            # Show "Open in Browser" for HTML files
            if single_item and single_item.name.lower().endswith((".html", ".htm", ".xhtml")):
                items.append({"label": "Open in Browser", "action": "open_in_browser", "icon": IconsManager.GLOBE})
            items.append({"label": "---"})

        show_label = "Show in Folder" if len(selection) == 1 else "Show Selected in Folder"
        items.append({"label": show_label, "action": "show_in_folder", "icon": IconsManager.FOLDER_OPEN})
        copy_label = "Copy" if len(selection) == 1 else f"Copy {len(selection)} Items"
        items.append({"label": copy_label, "action": "copy_item", "icon": IconsManager.COPY})
        if len(selection) == 1 and self._copied_item_paths and any(path.exists() for path in self._copied_item_paths):
            items.append({"label": "Paste", "action": "paste_item", "icon": IconsManager.PASTE})
        copy_path_label = "Copy Path" if len(selection) == 1 else "Copy Selected Paths"
        items.append({"label": copy_path_label, "action": "copy_path", "icon": IconsManager.COPY})
        if single_item:
            items.append({"label": "Rename", "action": "rename", "icon": IconsManager.EDIT})
        items.append({"label": "---"})
        delete_label = "Delete" if len(selection) == 1 else f"Delete {len(selection)} Items"
        items.append({"label": delete_label, "action": "delete", "icon": IconsManager.TRASH})

        # Run test - only show for test files
        if all_tests:
            items.append({"label": "---"})
            test_label = "Run Test" if len(selection) == 1 else f"Run {len(selection)} Tests"
            items.append({"label": test_label, "action": "run_test", "icon": IconsManager.WRENCH})

        # Git actions - only show for modified files
        if can_discard:
            items.append({"label": "---"})
            discard_label = "Discard Local Changes" if len(selection) == 1 else "Discard Selected Changes"
            items.append({"label": discard_label, "action": "discard_changes", "icon": IconsManager.UNDO})

        def on_select(action):
            if action == "open":
                self._action_open(item)
            elif action == "new_file":
                self._action_new_file(item)
            elif action == "new_folder":
                self._action_new_folder(item)
            elif action == "show_in_folder":
                self._action_show_in_folder(item)
            elif action == "copy_path":
                self._action_copy_path(item)
            elif action == "copy_item":
                self._action_copy_item(item)
            elif action == "paste_item":
                self._action_paste_item(item)
            elif action == "rename":
                self._action_rename(item)
            elif action == "delete":
                self._action_delete(item)
            elif action == "discard_changes":
                self._action_discard_changes(item)
            elif action == "open_in_browser":
                self._action_open_in_browser(item)
            elif action == "run_test":
                self._action_run_test(item)

        parent = self.get_root()
        show_context_menu(parent, items, on_select, x, y, source_widget=self.tree.drawing_area)

    def _get_action_items(self, item):
        """Return the current selection for an action, falling back to the clicked item."""
        if self.tree._is_item_selected(item):
            selection = self.tree.get_selected_items()
        else:
            selection = [item]
        return self._get_effective_selection(selection)

    def _get_effective_selection(self, items):
        """Drop descendants of selected directories so bulk actions only act once."""
        ordered_items = [item for item in self.tree.items if item in set(items)]
        selected_paths = {candidate.path for candidate in ordered_items}
        effective_items = []
        for candidate in ordered_items:
            if any(parent in selected_paths for parent in candidate.path.parents):
                continue
            effective_items.append(candidate)
        return effective_items

    def _action_open(self, item):
        """Open a file."""
        if not self.on_file_selected:
            return
        for selected in self._get_action_items(item):
            if not selected.is_dir:
                self.on_file_selected(str(selected.path))

    def _action_new_file(self, item):
        """Create a new file using inline editing."""
        self._start_new_item_inline(item, is_file=True)

    def _action_new_folder(self, item):
        """Create a new folder using inline editing."""
        self._start_new_item_inline(item, is_file=False)

    def _start_new_item_inline(self, parent_item, is_file=True):
        """Start inline editing for creating a new file or folder."""
        if not parent_item.expanded:
            parent_item.expanded = True
            self.tree._load_children(parent_item)
            self.tree._flatten_items()
            self.tree.drawing_area.queue_draw()

        # Create a temporary placeholder item
        placeholder = TreeItem(
            name="",
            path=parent_item.path / "",
            is_dir=not is_file,
            depth=parent_item.depth + 1,
            parent=parent_item,
            is_last=False,
        )

        parent_item.children.insert(0, placeholder)

        self.tree._flatten_items()
        self.tree._select_single_item(placeholder)
        self.tree._ensure_visible(placeholder)
        self.tree.drawing_area.queue_draw()

        GLib.idle_add(lambda: self._do_start_inline(parent_item, placeholder, is_file) or False)

    def _do_start_inline(self, parent_item, placeholder, is_file):
        """Actually start the inline editor after layout is updated."""
        parent_path = str(parent_item.path)

        def on_confirm(new_name):
            if placeholder in parent_item.children:
                parent_item.children.remove(placeholder)

            if not new_name:
                self.refresh()
                return

            try:
                new_path = os.path.join(parent_path, new_name)
                if os.path.exists(new_path):
                    self.refresh()
                    return

                if is_file:
                    with open(new_path, "w"):
                        pass
                    self.refresh()
                    if self.on_file_selected:
                        self.on_file_selected(new_path)
                else:
                    os.makedirs(new_path)
                    self.refresh()
            except Exception:
                self.refresh()

        def on_cancel():
            if placeholder in parent_item.children:
                parent_item.children.remove(placeholder)
            self.refresh()

        self.tree.start_inline_edit(
            placeholder,
            initial_text="",
            on_confirm=on_confirm,
            on_cancel=on_cancel,
            select_without_extension=False,
        )

    def _action_open_in_browser(self, item):
        """Open an HTML file in the default browser."""
        import webbrowser

        path = str(item.path)
        if os.path.exists(path):
            webbrowser.open(f"file://{path}")

    def _action_show_in_folder(self, item):
        """Show file in system file manager."""
        for selected in self._get_action_items(item):
            path = str(selected.path)
            if not os.path.exists(path):
                continue
            if sys.platform == "darwin":
                subprocess.run(["open", "-R", path], check=False)
            elif sys.platform == "linux":
                parent = os.path.dirname(path) if os.path.isfile(path) else path
                subprocess.run(["xdg-open", parent], check=False)

    def _action_rename(self, item):
        """Rename file/folder using inline editing."""
        old_name = item.name
        path = item.path
        parent_dir = path.parent

        def on_confirm(new_name):
            if not new_name or new_name == old_name:
                self.tree._request_redraw()
                return

            new_path = parent_dir / new_name
            if new_path.exists() and new_path != path:
                try:
                    is_same_file = os.path.samefile(path, new_path)
                except OSError:
                    is_same_file = False
                if not is_same_file:
                    self.tree._request_redraw()
                    return

            try:
                try:
                    same_file = path != new_path and os.path.samefile(path, new_path)
                except OSError:
                    same_file = False
                if same_file:
                    import tempfile

                    tmp = Path(tempfile.mktemp(dir=parent_dir))
                    os.rename(path, tmp)
                    os.rename(tmp, new_path)
                else:
                    os.rename(path, new_path)
                self._rename_item_in_place(item, new_name, new_path)
            except Exception:
                self.tree._request_redraw()

        def on_cancel():
            self.tree._request_redraw()

        self.tree.start_inline_edit(
            item,
            initial_text=old_name,
            on_confirm=on_confirm,
            on_cancel=on_cancel,
            select_without_extension=not item.is_dir,
        )

    def _rename_item_in_place(self, item, new_name, new_path):
        """Update a tree item after rename without full tree rebuild."""
        import time

        self._suppress_watcher_until = time.monotonic() + 2.0

        old_path = item.path
        item.name = new_name
        item.path = new_path

        if item.is_dir and item.children:
            self._update_children_paths(item, old_path, new_path)

        if item.parent and item.parent.children:
            item.parent.children.sort(key=lambda x: (not x.is_dir, x.name.lower()))

        self.tree._flatten_and_redraw()

    def _update_children_paths(self, parent, old_parent_path, new_parent_path):
        """Recursively update children paths after parent rename."""
        for child in parent.children:
            relative = child.path.relative_to(old_parent_path)
            child.path = new_parent_path / relative
            if child.is_dir and child.children:
                old_child = old_parent_path / child.name
                self._update_children_paths(child, old_child, child.path)

    def _action_delete(self, item):
        """Delete file/folder after confirmation."""
        from popups.confirm_dialog import show_confirm

        items_to_delete = [selected for selected in self._get_action_items(item) if selected.path.exists()]
        if not items_to_delete:
            return

        if len(items_to_delete) == 1:
            target = items_to_delete[0]
            detail = f'Delete "{target.name}"?'
        else:
            preview = "\n".join(f"• {selected.name}" for selected in items_to_delete[:5])
            if len(items_to_delete) > 5:
                preview += f"\n... and {len(items_to_delete) - 5} more"
            detail = f"Delete {len(items_to_delete)} selected items?\n\n{preview}"

        show_confirm(
            self.get_root(),
            title="Delete Selected Items" if len(items_to_delete) > 1 else "Delete Item",
            message=detail,
            confirm_text="Delete",
            cancel_text="Cancel",
            danger=True,
            on_confirm=lambda: self._delete_items(items_to_delete),
        )

    def _delete_items(self, items):
        """Delete a batch of items and refresh once."""
        deleted_count = 0
        for target in sorted(items, key=lambda selected: (len(selected.path.parts), str(selected.path)), reverse=True):
            path = target.path
            try:
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
                deleted_count += 1
            except Exception:
                pass

        if deleted_count:
            self.refresh()
            if deleted_count == 1:
                pass
            else:
                pass

    def _action_discard_changes(self, item):
        """Discard local git changes for a file."""
        from shared.git_manager import get_git_manager

        git = get_git_manager()
        results = []
        for selected in self._get_action_items(item):
            success, message = git.discard_changes(str(selected.path))
            results.append((success, message))
            if success:
                pass
            else:
                pass

        if any(success for success, _ in results):
            if self.on_git_refresh:
                self.on_git_refresh()
            self.refresh()

    def _is_test_file(self, item):
        """Check if a file is a test file based on naming conventions."""
        name = item.name.lower()
        # Python: test_*.py, *_test.py
        if name.endswith(".py"):
            return name.startswith("test_") or name.endswith("_test.py")
        # JavaScript/TypeScript: *.test.js, *.spec.js, *.cy.js, etc.
        for ext in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".mts"):
            if name.endswith(f".test{ext}") or name.endswith(f".spec{ext}") or name.endswith(f".cy{ext}"):
                return True
        # Go: *_test.go
        if name.endswith("_test.go"):
            return True
        # Ruby: *_spec.rb
        if name.endswith("_spec.rb"):
            return True
        # Rust: *.rs in tests/ directory
        if name.endswith(".rs") and "tests" in str(item.path).split(os.sep):
            return True
        return False

    def _find_venv_python(self, file_path):
        """Walk up from file_path to find a virtual environment's python."""
        directory = os.path.dirname(file_path)
        while directory and directory != os.path.dirname(directory):
            for venv_name in (".venv", "venv", ".env", "env"):
                candidate = os.path.join(directory, venv_name, "bin", "python")
                if os.path.isfile(candidate):
                    return candidate
            directory = os.path.dirname(directory)
        return "python3"

    def _find_package_json(self, file_path):
        """Walk up from file_path to find the nearest package.json."""
        directory = os.path.dirname(file_path)
        while directory and directory != os.path.dirname(directory):
            candidate = os.path.join(directory, "package.json")
            if os.path.isfile(candidate):
                return candidate
            directory = os.path.dirname(directory)
        return None

    def _get_js_test_command(self, file_path):
        """Detect the JS/TS test runner from package.json and build the command."""
        pkg_path = self._find_package_json(file_path)
        if pkg_path:
            try:
                with open(pkg_path) as f:
                    pkg = json.load(f)
                test_script = pkg.get("scripts", {}).get("test", "")
                if "react-scripts" in test_script:
                    return f"npx react-scripts test --watchAll=false {file_path}"
                if "vitest" in test_script:
                    return f"npx vitest run {file_path}"
            except (json.JSONDecodeError, OSError):
                pass
        return f"npx jest {file_path}"

    def _get_cypress_test_command(self, file_path):
        """Detect the Cypress test runner from package.json and build the command."""
        pkg_path = self._find_package_json(file_path)
        if pkg_path:
            try:
                with open(pkg_path) as f:
                    pkg = json.load(f)
                scripts = pkg.get("scripts", {})
                # Prefer a script that starts the server + runs cypress (e.g. "cy:test")
                for script_name, script_val in scripts.items():
                    if "start-server-and-test" in script_val and "cypress" in script_val.lower():
                        return f"npm run {script_name} -- --spec {file_path}"
                # Fall back to a plain cypress run script (e.g. "cy:run")
                for script_name, script_val in scripts.items():
                    if "cypress run" in script_val and "start-server-and-test" not in script_val:
                        return f"npm run {script_name} -- --spec {file_path}"
            except (json.JSONDecodeError, OSError):
                pass
        return f"npx cypress run --spec {file_path}"

    def _get_test_command(self, item):
        """Build the appropriate test command for a test file."""
        name = item.name.lower()
        file_path = str(item.path)

        if name.endswith(".py"):
            python = self._find_venv_python(file_path)
            return f"{python} -m pytest {file_path}"
        if any(name.endswith(f".cy{e}") for e in (".js", ".jsx", ".mjs", ".ts", ".tsx", ".mts")):
            return self._get_cypress_test_command(file_path)
        if any(
            name.endswith(f".test{e}") or name.endswith(f".spec{e}") for e in (".js", ".jsx", ".mjs", ".ts", ".tsx", ".mts")
        ):
            return self._get_js_test_command(file_path)
        if name.endswith("_test.go"):
            return f"go test {os.path.dirname(file_path)}/..."
        if name.endswith("_spec.rb"):
            return f"bundle exec rspec {file_path}"
        if name.endswith(".rs"):
            return "cargo test"
        return f"echo 'No test runner configured for {name}'"

    def _action_run_test(self, item):
        """Run test file in the terminal."""
        if self.write_to_terminal:
            commands = [self._get_test_command(selected) for selected in self._get_action_items(item)]
            self.write_to_terminal("\n".join(commands))
