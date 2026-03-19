"""Regression tests for the Sketch Pad shape properties popup styling."""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "sketch_pad" / "shape_properties_popup.py"


class TestShapePropertiesPopupStyling:
    """Verify the Apply button uses the shared popup theming."""

    def test_uses_nvim_popup_button_factory(self):
        source = SRC.read_text()
        assert 'self._create_button("Apply", primary=True)' in source
        assert 'self._create_button("Cancel")' in source
        assert "suggested-action" not in source

    def test_inherits_nvim_popup(self):
        tree = ast.parse(SRC.read_text())
        shape_popup = next(node for node in tree.body if getattr(node, "name", None) == "ShapePropertiesPopup")
        assert any(getattr(base, "id", None) == "NvimPopup" for base in shape_popup.bases)
