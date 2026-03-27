"""
Python symbol lookup logic for Zen IDE.
Handles module resolution, init file scanning, and virtualenv site-packages discovery.
"""

import glob as glob_module
import os
import sys
from typing import Optional


class PySymbolLookupMixin:
    """Module resolution and symbol lookup methods mixed into PythonNavigationMixin."""

    def _open_module(self, module_path: str, current_file: str, navigate_to: str = None) -> bool:
        """Try to open a Python module file."""
        if not current_file:
            return False

        current_dir = os.path.dirname(current_file)

        # Handle relative imports
        if module_path.startswith("."):
            dots = len(module_path) - len(module_path.lstrip("."))
            rest = module_path.lstrip(".")

            target_dir = current_dir
            for _ in range(dots - 1):
                target_dir = os.path.dirname(target_dir)

            if rest:
                rel_path = rest.replace(".", os.sep)
                target = os.path.join(target_dir, rel_path)
            else:
                target = target_dir

            for candidate in [target + ".py", os.path.join(target, "__init__.py")]:
                if os.path.exists(candidate):
                    self._pending_navigate_symbol = navigate_to
                    self._pending_file_path = candidate
                    self.open_file_callback(candidate, None)
                    if navigate_to:
                        self._schedule_pending_navigation()
                    return True
            return False

        rel_path = module_path.replace(".", os.sep)
        first_part = module_path.split(".")[0]

        search_dirs = [current_dir]

        check_dir = current_dir
        while check_dir and len(check_dir) > 1:
            if os.path.basename(check_dir) == first_part:
                parent = os.path.dirname(check_dir)
                if parent not in search_dirs:
                    search_dirs.insert(0, parent)
                break
            candidate = os.path.join(check_dir, first_part)
            if os.path.isdir(candidate) and check_dir not in search_dirs:
                search_dirs.insert(0, check_dir)
                break
            check_dir = os.path.dirname(check_dir)

        if self.get_workspace_folders:
            try:
                for ws_folder in self.get_workspace_folders() or []:
                    if ws_folder and ws_folder not in search_dirs:
                        search_dirs.append(ws_folder)
                        module_dir = os.path.join(ws_folder, first_part)
                        if os.path.isdir(module_dir):
                            parent = os.path.dirname(module_dir)
                            if parent not in search_dirs:
                                search_dirs.append(parent)
            except Exception:
                pass

        for sp in self._find_venv_site_packages(current_file):
            if sp not in search_dirs:
                search_dirs.append(sp)

        for path in sys.path:
            if path and os.path.isdir(path) and path not in search_dirs:
                search_dirs.append(path)

        for base_dir in search_dirs:
            target = os.path.join(base_dir, rel_path)

            for ext in (".py", ".pyi"):
                candidate = target + ext
                if os.path.exists(candidate):
                    self._pending_navigate_symbol = navigate_to
                    self._pending_file_path = candidate
                    self.open_file_callback(candidate, None)
                    if navigate_to:
                        self._schedule_pending_navigation()
                    return True

            for init_name in ("__init__.py", "__init__.pyi"):
                init_file = os.path.join(target, init_name)
                if os.path.exists(init_file):
                    self._pending_navigate_symbol = navigate_to
                    self._pending_file_path = init_file
                    self.open_file_callback(init_file, None)
                    if navigate_to:
                        self._schedule_pending_navigation()
                    return True

        return False

    def _find_module_init(self, module_path: str, current_file: str) -> Optional[str]:
        """Find the __init__.py file for a module path."""
        if not current_file:
            return None

        current_dir = os.path.dirname(current_file)
        rel_path = module_path.replace(".", os.sep)
        first_part = module_path.split(".")[0]

        search_dirs = [current_dir]

        check_dir = current_dir
        while check_dir and len(check_dir) > 1:
            candidate = os.path.join(check_dir, first_part)
            if os.path.isdir(candidate) and check_dir not in search_dirs:
                search_dirs.insert(0, check_dir)
                break
            check_dir = os.path.dirname(check_dir)

        if self.get_workspace_folders:
            try:
                for ws_folder in self.get_workspace_folders() or []:
                    if ws_folder:
                        search_dirs.append(ws_folder)
                        module_dir = os.path.join(ws_folder, first_part)
                        if os.path.isdir(module_dir):
                            search_dirs.append(os.path.dirname(module_dir))
            except Exception:
                pass

        for sp in self._find_venv_site_packages(current_file):
            if sp not in search_dirs:
                search_dirs.append(sp)

        for search_dir in search_dirs:
            for init_name in ("__init__.py", "__init__.pyi"):
                init_file = os.path.join(search_dir, rel_path, init_name)
                if os.path.exists(init_file):
                    return init_file

        return None

    def _resolve_reexport_in_init(self, init_file: str, symbol: str, current_file: str) -> Optional[str]:
        """Check if a symbol in __init__.py is re-exported from another module."""
        try:
            with open(init_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
        except (OSError, IOError):
            return None

        init_dir = os.path.dirname(init_file)

        module_ref = self._ts_py.find_import_source(content, symbol)
        if not module_ref:
            return None

        if module_ref.startswith("."):
            dots = len(module_ref) - len(module_ref.lstrip("."))
            module_path = module_ref.lstrip(".")

            target_dir = init_dir
            for _ in range(dots - 1):
                target_dir = os.path.dirname(target_dir)

            if module_path:
                rel_path = module_path.replace(".", os.sep)
                target_base = os.path.join(target_dir, rel_path)
            else:
                target_base = target_dir
        else:
            package_name = os.path.basename(init_dir)
            module_parts = module_ref.split(".")
            if module_parts[0] == package_name and len(module_parts) > 1:
                rest = os.sep.join(module_parts[1:])
                target_base = os.path.join(init_dir, rest)
            else:
                parent_dir = os.path.dirname(init_dir)
                target_base = os.path.join(parent_dir, module_ref.replace(".", os.sep))

        if os.path.exists(target_base + ".py"):
            return target_base + ".py"

        if os.path.exists(os.path.join(target_base, "__init__.py")):
            return os.path.join(target_base, "__init__.py")

        # Fallback for absolute imports: walk up ancestor directories
        if not module_ref.startswith("."):
            rel = module_ref.replace(".", os.sep)
            ancestor = init_dir
            while ancestor and len(ancestor) > 1:
                ancestor = os.path.dirname(ancestor)
                candidate = os.path.join(ancestor, rel)
                if os.path.exists(candidate + ".py"):
                    return candidate + ".py"
                if os.path.exists(os.path.join(candidate, "__init__.py")):
                    return os.path.join(candidate, "__init__.py")

        return None

    def _find_venv_site_packages(self, current_file: str) -> list:
        """Find virtualenv site-packages directories for the project."""
        venv_names = [".venv", "venv"]
        site_packages = []
        checked = set()

        check_dir = os.path.dirname(current_file)
        while check_dir and len(check_dir) > 1:
            if check_dir in checked:
                break
            checked.add(check_dir)
            for venv_name in venv_names:
                venv_path = os.path.join(check_dir, venv_name)
                if os.path.isdir(venv_path):
                    for sp in glob_module.glob(os.path.join(venv_path, "lib", "python*", "site-packages")):
                        if os.path.isdir(sp):
                            site_packages.append(sp)
                    if site_packages:
                        return site_packages
            check_dir = os.path.dirname(check_dir)

        if self.get_workspace_folders:
            try:
                for ws_folder in self.get_workspace_folders() or []:
                    if ws_folder and ws_folder not in checked:
                        for venv_name in venv_names:
                            venv_path = os.path.join(ws_folder, venv_name)
                            if os.path.isdir(venv_path):
                                for sp in glob_module.glob(os.path.join(venv_path, "lib", "python*", "site-packages")):
                                    if os.path.isdir(sp):
                                        site_packages.append(sp)
            except Exception:
                pass

        return site_packages
