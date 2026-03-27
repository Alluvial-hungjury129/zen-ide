"""
CustomTreePanel selection mixin — selection management logic.
"""

from typing import List, Optional

from treeview.tree_item import TreeItem


class TreePanelSelectionMixin:
    """Mixin providing selection management methods for CustomTreePanel."""

    def _is_item_selected(self, item: Optional[TreeItem]) -> bool:
        """Return whether an item is part of the current selection."""
        return item is not None and item in self.selected_items

    def get_selected_items(self) -> List[TreeItem]:
        """Return selected items in visible tree order."""
        if not self.selected_items:
            return []
        return [item for item in self.items if item in self.selected_items]

    def _set_selection(
        self,
        items: List[TreeItem],
        primary_item: Optional[TreeItem] = None,
        anchor_item: Optional[TreeItem] = None,
    ):
        """Replace the current selection."""
        visible_items = [item for item in items if item in self.items]
        self.selected_items = set(visible_items)

        if not visible_items:
            self.selected_item = None
            self._selection_anchor_item = None
            return

        if primary_item not in self.selected_items:
            primary_item = visible_items[-1]
        self.selected_item = primary_item

        if anchor_item not in self.selected_items:
            anchor_item = primary_item
        self._selection_anchor_item = anchor_item

    def _clear_selection(self):
        """Clear the current selection."""
        self.selected_items.clear()
        self.selected_item = None
        self._selection_anchor_item = None

    def _select_single_item(self, item: Optional[TreeItem]):
        """Select a single tree item."""
        if item is None:
            self._clear_selection()
            return
        self._set_selection([item], primary_item=item, anchor_item=item)

    def _toggle_item_selection(self, item: TreeItem):
        """Toggle an item inside the current selection."""
        if item in self.selected_items:
            remaining_items = [selected for selected in self.get_selected_items() if selected != item]
            if remaining_items:
                new_primary = self.selected_item if self.selected_item != item else remaining_items[-1]
                new_anchor = self._selection_anchor_item if self._selection_anchor_item != item else new_primary
                self._set_selection(remaining_items, primary_item=new_primary, anchor_item=new_anchor)
            else:
                self._clear_selection()
            return

        items = self.get_selected_items()
        items.append(item)
        self._set_selection(items, primary_item=item, anchor_item=item)

    def _select_range_to(self, item: TreeItem):
        """Select an inclusive range from the anchor item to the target item."""
        anchor = self._selection_anchor_item or self.selected_item
        if anchor not in self.items:
            self._select_single_item(item)
            return

        start = self.items.index(anchor)
        end = self.items.index(item)
        if start <= end:
            range_items = self.items[start : end + 1]
        else:
            range_items = self.items[end : start + 1]
        self._set_selection(range_items, primary_item=item, anchor_item=anchor)

    def _prune_selection_to_visible_items(self):
        """Drop any selected items that are no longer visible."""
        if not self.selected_items:
            self.selected_item = None
            if self._selection_anchor_item not in self.items:
                self._selection_anchor_item = None
            return

        visible = set(self.items)
        self.selected_items = {item for item in self.selected_items if item in visible}

        if not self.selected_items:
            self.selected_item = None
            self._selection_anchor_item = None
            return

        if self.selected_item not in self.selected_items:
            self.selected_item = self.get_selected_items()[-1]

        if self._selection_anchor_item not in self.selected_items:
            self._selection_anchor_item = self.selected_item
