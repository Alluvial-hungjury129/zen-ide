"""Tests for MarkdownBlockRenderer — including HTML block parsing."""

import pytest


@pytest.fixture
def renderer():
    from editor.preview.markdown_block_renderer import MarkdownBlockRenderer
    return MarkdownBlockRenderer()


class TestHtmlTableWithImages:
    """HTML <table> containing <img> tags should produce image/image_row blocks."""

    def test_basic_image_table(self, renderer):
        md = """<table>
<tr>
<td><img src="screenshots/splash1.png"/></td>
<td><img src="screenshots/splash2.png"/></td>
</tr>
<tr>
<td colspan="2" align="center"><img src="screenshots/splash3.png" width="50%"/></td>
</tr>
</table>"""
        blocks = renderer.render(md)
        # Row 1 has 2 images → image_row; Row 2 has 1 image → image
        image_row_blocks = [b for b in blocks if b.kind == "image_row"]
        image_blocks = [b for b in blocks if b.kind == "image"]
        assert len(image_row_blocks) == 1
        assert len(image_row_blocks[0].images) == 2
        assert image_row_blocks[0].images[0]["url"] == "screenshots/splash1.png"
        assert image_row_blocks[0].images[1]["url"] == "screenshots/splash2.png"
        assert len(image_blocks) == 1
        assert image_blocks[0].image_url == "screenshots/splash3.png"
        # 50% width should be stored as percentage, not pixel width
        assert image_blocks[0].image_width is None
        assert image_blocks[0].image_width_pct == 50.0
        # align="center" from <td> should be propagated
        assert image_blocks[0].image_align == "center"

    def test_image_table_with_alt_text(self, renderer):
        md = """<table>
<tr>
<td><img src="img/a.png" alt="First"/></td>
<td><img src="img/b.png" alt="Second"/></td>
</tr>
</table>"""
        blocks = renderer.render(md)
        image_row_blocks = [b for b in blocks if b.kind == "image_row"]
        assert len(image_row_blocks) == 1
        assert image_row_blocks[0].images[0]["alt"] == "First"
        assert image_row_blocks[0].images[1]["alt"] == "Second"

    def test_image_table_with_pixel_dimensions(self, renderer):
        md = '<table><tr><td><img src="x.png" width="200" height="100"/></td></tr></table>'
        blocks = renderer.render(md)
        image_blocks = [b for b in blocks if b.kind == "image"]
        assert len(image_blocks) == 1
        assert image_blocks[0].image_width == 200
        assert image_blocks[0].image_height == 100

    def test_single_row_multiple_images_is_image_row(self, renderer):
        """A single <tr> with 3 images should produce one image_row block."""
        md = """<table><tr>
<td><img src="a.png"/></td>
<td><img src="b.png"/></td>
<td><img src="c.png"/></td>
</tr></table>"""
        blocks = renderer.render(md)
        image_row_blocks = [b for b in blocks if b.kind == "image_row"]
        assert len(image_row_blocks) == 1
        assert len(image_row_blocks[0].images) == 3
        assert [img["url"] for img in image_row_blocks[0].images] == ["a.png", "b.png", "c.png"]

    def test_each_row_single_image_produces_image_blocks(self, renderer):
        """Each <tr> with only 1 image should produce a plain image block."""
        md = """<table>
<tr><td><img src="a.png"/></td></tr>
<tr><td><img src="b.png"/></td></tr>
</table>"""
        blocks = renderer.render(md)
        image_blocks = [b for b in blocks if b.kind == "image"]
        image_row_blocks = [b for b in blocks if b.kind == "image_row"]
        assert len(image_blocks) == 2
        assert len(image_row_blocks) == 0

    def test_percentage_width_parsed(self, renderer):
        """width="75%" on <img> should set image_width_pct=75, not image_width."""
        md = '<table><tr><td><img src="x.png" width="75%"/></td></tr></table>'
        blocks = renderer.render(md)
        image_blocks = [b for b in blocks if b.kind == "image"]
        assert len(image_blocks) == 1
        assert image_blocks[0].image_width is None
        assert image_blocks[0].image_width_pct == 75.0

    def test_align_center_from_td(self, renderer):
        """align='center' on <td> should propagate to image block."""
        md = '<table><tr><td align="center"><img src="x.png"/></td></tr></table>'
        blocks = renderer.render(md)
        image_blocks = [b for b in blocks if b.kind == "image"]
        assert len(image_blocks) == 1
        assert image_blocks[0].image_align == "center"

    def test_align_right_from_td(self, renderer):
        """align='right' on <td> should propagate to image block."""
        md = '<table><tr><td align="right"><img src="x.png" width="30%"/></td></tr></table>'
        blocks = renderer.render(md)
        image_blocks = [b for b in blocks if b.kind == "image"]
        assert len(image_blocks) == 1
        assert image_blocks[0].image_align == "right"
        assert image_blocks[0].image_width_pct == 30.0

    def test_no_align_defaults_empty(self, renderer):
        """When no align attr on <td>, image_align should be empty string."""
        md = '<table><tr><td><img src="x.png"/></td></tr></table>'
        blocks = renderer.render(md)
        image_blocks = [b for b in blocks if b.kind == "image"]
        assert len(image_blocks) == 1
        assert image_blocks[0].image_align == ""

    def test_pixel_width_not_confused_with_percent(self, renderer):
        """Integer width like width='200' should set image_width, not pct."""
        md = '<table><tr><td><img src="x.png" width="200"/></td></tr></table>'
        blocks = renderer.render(md)
        image_blocks = [b for b in blocks if b.kind == "image"]
        assert len(image_blocks) == 1
        assert image_blocks[0].image_width == 200
        assert image_blocks[0].image_width_pct is None


class TestHtmlTextTable:
    """HTML <table> with text content should produce a table block."""

    def test_basic_text_table(self, renderer):
        md = """<table>
<tr><th>Name</th><th>Value</th></tr>
<tr><td>Foo</td><td>Bar</td></tr>
<tr><td>Baz</td><td>Qux</td></tr>
</table>"""
        blocks = renderer.render(md)
        table_blocks = [b for b in blocks if b.kind == "table"]
        assert len(table_blocks) == 1
        tb = table_blocks[0]
        assert tb.headers == ["Name", "Value"]
        assert len(tb.rows) == 2
        assert tb.rows[0] == ["Foo", "Bar"]
        assert tb.rows[1] == ["Baz", "Qux"]

    def test_table_without_thead(self, renderer):
        md = """<table>
<tr><td>A</td><td>B</td></tr>
<tr><td>C</td><td>D</td></tr>
</table>"""
        blocks = renderer.render(md)
        table_blocks = [b for b in blocks if b.kind == "table"]
        assert len(table_blocks) == 1
        tb = table_blocks[0]
        # No th → no headers, all rows are data
        assert tb.headers == []
        assert len(tb.rows) == 2


class TestHtmlBlockDoesNotBreakExisting:
    """Ensure existing markdown features still work after adding HTML block support."""

    def test_markdown_table_still_works(self, renderer):
        md = """| Name | Age |
| --- | --- |
| Alice | 30 |
| Bob | 25 |"""
        blocks = renderer.render(md)
        table_blocks = [b for b in blocks if b.kind == "table"]
        assert len(table_blocks) == 1
        assert table_blocks[0].headers == ["Name", "Age"]

    def test_standalone_html_img_still_works(self, renderer):
        md = '<img src="test.png" alt="test"/>'
        blocks = renderer.render(md)
        image_blocks = [b for b in blocks if b.kind == "image"]
        assert len(image_blocks) == 1
        assert image_blocks[0].image_url == "test.png"

    def test_markdown_image_still_works(self, renderer):
        md = "![alt text](image.png)"
        blocks = renderer.render(md)
        image_blocks = [b for b in blocks if b.kind == "image"]
        assert len(image_blocks) == 1
        assert image_blocks[0].image_url == "image.png"

    def test_heading_still_works(self, renderer):
        md = "# Hello World"
        blocks = renderer.render(md)
        assert len(blocks) == 1
        assert blocks[0].kind == "heading"
        assert blocks[0].level == 1

    def test_hr_still_works(self, renderer):
        md = "---"
        blocks = renderer.render(md)
        assert len(blocks) == 1
        assert blocks[0].kind == "hr"

    def test_paragraph_before_html_table(self, renderer):
        md = """Some text before.

<table>
<tr><td>Cell</td></tr>
</table>

Some text after."""
        blocks = renderer.render(md)
        kinds = [b.kind for b in blocks]
        assert "paragraph" in kinds
        assert "table" in kinds or "image" in kinds

    def test_code_fence_not_broken(self, renderer):
        md = """```python
print("hello")
```"""
        blocks = renderer.render(md)
        assert len(blocks) == 1
        assert blocks[0].kind == "code"
        assert blocks[0].language == "python"


class TestHtmlBlockNesting:
    """Nested HTML tags should be handled correctly."""

    def test_nested_table_depth_tracking(self, renderer):
        # Even though nested tables are unusual, ensure the parser doesn't break
        md = """<table>
<tr><td>
<table><tr><td>inner</td></tr></table>
</td></tr>
</table>"""
        blocks = renderer.render(md)
        # Should produce some blocks without crashing
        assert len(blocks) >= 1

    def test_div_wrapper(self, renderer):
        md = """<div align="center">
<img src="logo.png" alt="Logo"/>
</div>"""
        blocks = renderer.render(md)
        image_blocks = [b for b in blocks if b.kind == "image"]
        assert len(image_blocks) == 1
        assert image_blocks[0].image_url == "logo.png"
