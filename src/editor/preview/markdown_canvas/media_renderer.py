"""Image and emoji rendering mixin for MarkdownCanvas."""

from __future__ import annotations

import hashlib
import os
import threading

from gi.repository import Gdk, GdkPixbuf, GLib, Graphene, Pango

from editor.preview.content_block import ContentBlock


class MediaRendererMixin:
    """Mixin for image loading, caching, and rendering."""

    def _draw_image(self, snapshot, pango_ctx, block: ContentBlock, width: float):
        texture = self._load_texture(block.image_url)
        content_width = width - self.PAD_LEFT - self.PAD_RIGHT

        # Apply percentage width constraint if specified (e.g. width="50%")
        effective_max_width = content_width
        if block.image_width_pct is not None and 0 < block.image_width_pct < 100:
            effective_max_width = content_width * (block.image_width_pct / 100.0)

        if texture is None:
            # Fallback: draw alt text placeholder
            desc = self._scaled_font_desc()
            desc.set_style(Pango.Style.ITALIC)
            layout = Pango.Layout.new(pango_ctx)
            layout.set_font_description(desc)
            layout.set_width(int(content_width * Pango.SCALE))
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            label = f"[image: {block.image_alt}]" if block.image_alt else "[image]"
            layout.set_text(label, -1)

            point = Graphene.Point()
            point.init(self.PAD_LEFT, block._y_offset)
            snapshot.save()
            snapshot.translate(point)
            snapshot.append_layout(layout, self._dim_rgba)
            snapshot.restore()
            return

        img_w = texture.get_width()
        img_h = texture.get_height()
        display_w, display_h = self._fit_image_size(
            img_w,
            img_h,
            effective_max_width,
            explicit_w=block.image_width,
            explicit_h=block.image_height,
        )

        # Compute X offset for alignment
        img_x = float(self.PAD_LEFT)
        if block.image_align == "center" and display_w < content_width:
            img_x = self.PAD_LEFT + (content_width - display_w) / 2
        elif block.image_align == "right" and display_w < content_width:
            img_x = self.PAD_LEFT + content_width - display_w

        rect = Graphene.Rect()
        rect.init(img_x, block._y_offset, display_w, display_h)
        snapshot.append_texture(texture, rect)

        # Draw alt text caption below image if present
        if block.image_alt:
            desc = self._scaled_font_desc()
            cap_size = max(int((self._base_font_size - 2) * self._zoom_level), 8)
            desc.set_size(cap_size * Pango.SCALE)
            desc.set_style(Pango.Style.ITALIC)
            layout = Pango.Layout.new(pango_ctx)
            layout.set_font_description(desc)
            layout.set_width(int(content_width * Pango.SCALE))
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            layout.set_text(block.image_alt, -1)

            # Center caption under image if image is centered
            cap_x = float(self.PAD_LEFT)
            if block.image_align == "center":
                _, cap_logical = layout.get_pixel_extents()
                cap_x = self.PAD_LEFT + (content_width - cap_logical.width) / 2

            point = Graphene.Point()
            point.init(cap_x, block._y_offset + display_h + 4)
            snapshot.save()
            snapshot.translate(point)
            snapshot.append_layout(layout, self._dim_rgba)
            snapshot.restore()

    def _draw_image_row(self, snapshot, pango_ctx, block: ContentBlock, width: float):
        """Draw multiple images side-by-side in a single row.

        Each image gets an equal share of the available content width (minus
        gaps). Images are scaled proportionally to fit their slot and
        vertically centred within the row height.
        """
        _IMAGE_ROW_GAP = 8
        content_width = width - self.PAD_LEFT - self.PAD_RIGHT
        images = block.images
        n = len(images)
        if n == 0:
            return

        total_gap = _IMAGE_ROW_GAP * (n - 1)
        slot_w = max((content_width - total_gap) / n, 20)

        x = float(self.PAD_LEFT)
        row_h = block._height

        for img in images:
            texture = self._load_texture(img["url"])
            if texture is None:
                # Fallback: draw placeholder text
                desc = self._scaled_font_desc()
                desc.set_style(Pango.Style.ITALIC)
                layout = Pango.Layout.new(pango_ctx)
                layout.set_font_description(desc)
                layout.set_width(int(slot_w * Pango.SCALE))
                layout.set_wrap(Pango.WrapMode.WORD_CHAR)
                label = f"[image: {img.get('alt', '')}]" if img.get("alt") else "[image]"
                layout.set_text(label, -1)

                point = Graphene.Point()
                point.init(x, block._y_offset)
                snapshot.save()
                snapshot.translate(point)
                snapshot.append_layout(layout, self._dim_rgba)
                snapshot.restore()

                x += slot_w + _IMAGE_ROW_GAP
                continue

            iw = texture.get_width()
            ih = texture.get_height()
            dw, dh = self._fit_image_size(
                iw,
                ih,
                slot_w,
                explicit_w=img.get("width"),
                explicit_h=img.get("height"),
            )

            # Vertically centre within the row
            y_off = block._y_offset + max(0, (row_h - dh) / 2)

            rect = Graphene.Rect()
            rect.init(x, y_off, dw, dh)
            snapshot.append_texture(texture, rect)

            x += slot_w + _IMAGE_ROW_GAP

    def _load_texture(self, url: str) -> Gdk.Texture | None:
        """Load an image URL into a Gdk.Texture, with caching.

        For remote URLs (http/https), checks a local download cache. If not
        cached, starts an async download and returns None (the canvas will
        re-render when the download completes).
        """
        if url in self._image_cache:
            return self._image_cache[url]

        resolved = self._resolve_image_path(url)
        if resolved is None:
            # Might be a remote URL -- kick off async fetch
            if url.startswith(("http://", "https://")) and url not in self._fetching_urls:
                self._fetch_remote_image(url)
            return None

        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(resolved)
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            self._image_cache[url] = texture
            return texture
        except Exception:
            self._image_cache[url] = None
            return None

    def _resolve_image_path(self, url: str) -> str | None:
        """Resolve an image URL to a local file path."""
        # Already an absolute path
        if os.path.isabs(url) and os.path.isfile(url):
            return url

        # Remote URL -- check local download cache
        if url.startswith(("http://", "https://")):
            cache_path = self._get_remote_cache_path(url)
            if cache_path and os.path.isfile(cache_path):
                return cache_path
            return None

        # Relative path -- resolve from base_path
        if self._base_path and not url.startswith(("http://", "https://", "data:")):
            candidate = os.path.join(self._base_path, url)
            candidate = os.path.normpath(candidate)
            if os.path.isfile(candidate):
                return candidate

        return None

    def _get_remote_cache_path(self, url: str) -> str | None:
        """Get the local cache file path for a remote URL.

        For SVG URLs the downloaded file is converted to PNG, so this method
        returns the ``.png`` path when the URL extension is ``.svg``.
        """
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
        # Derive extension from URL path (strip query params)
        from urllib.parse import urlparse

        parsed = urlparse(url)
        path = parsed.path
        ext = os.path.splitext(path)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico"):
            ext = ".png"  # default fallback
        # SVG files are converted to PNG during download -- use .png extension
        if ext == ".svg":
            ext = ".png"
        return os.path.join(self._remote_cache_dir, f"{url_hash}{ext}")

    def _fetch_remote_image(self, url: str):
        """Download a remote image in a background thread, then refresh."""
        self._fetching_urls.add(url)
        cache_path = self._get_remote_cache_path(url)
        if not cache_path:
            return

        def _download():
            import urllib.request

            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Zen-IDE/1.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    data = resp.read()
                    content_type = resp.headers.get("Content-Type", "")

                    # SVG images need conversion to PNG for GdkPixbuf
                    # Check URL path (without query params) for .svg extension
                    from urllib.parse import urlparse as _urlparse

                    _url_path = _urlparse(url).path
                    if "svg" in content_type or _url_path.endswith(".svg"):
                        png_path = self._convert_svg_to_png(data, cache_path)
                        if png_path:
                            GLib.idle_add(self._on_remote_image_ready, url, png_path)
                        else:
                            GLib.idle_add(self._on_remote_image_failed, url)
                    else:
                        with open(cache_path, "wb") as f:
                            f.write(data)
                        GLib.idle_add(self._on_remote_image_ready, url, cache_path)
            except Exception:
                GLib.idle_add(self._on_remote_image_failed, url)

        thread = threading.Thread(target=_download, daemon=True)
        thread.start()

    def _convert_svg_to_png(self, svg_data: bytes, base_cache_path: str) -> str | None:
        """Convert SVG data to PNG using GdkPixbuf (requires librsvg).

        Falls back to writing raw SVG and hoping GdkPixbuf can handle it.
        Returns the path to the resulting image file, or None on failure.
        """
        # Try loading SVG directly via GdkPixbuf (works if librsvg is installed)
        png_path = os.path.splitext(base_cache_path)[0] + ".png"
        try:
            loader = GdkPixbuf.PixbufLoader.new()
            loader.write(svg_data)
            loader.close()
            pixbuf = loader.get_pixbuf()
            if pixbuf:
                pixbuf.savev(png_path, "png", [], [])
                return png_path
        except Exception:
            pass

        # Fallback: save raw SVG and hope GdkPixbuf can load it
        try:
            with open(base_cache_path, "wb") as f:
                f.write(svg_data)
            # Test if GdkPixbuf can load it
            GdkPixbuf.Pixbuf.new_from_file(base_cache_path)
            return base_cache_path
        except Exception:
            pass

        return None

    def _on_remote_image_ready(self, url: str, local_path: str):
        """Called on main thread when a remote image download completes."""
        self._fetching_urls.discard(url)
        # Clear the cache entry so _load_texture will re-resolve it
        self._image_cache.pop(url, None)
        # Force re-layout and redraw
        self._needs_layout = True
        self._schedule_redraw()
        return False

    def _on_remote_image_failed(self, url: str):
        """Called on main thread when a remote image download fails."""
        self._fetching_urls.discard(url)
        # Cache as None to avoid re-fetching
        self._image_cache[url] = None
        return False

    def _fit_image_size(
        self,
        img_w: int,
        img_h: int,
        max_width: float,
        explicit_w: int | None = None,
        explicit_h: int | None = None,
    ) -> tuple[float, float]:
        """Scale image to fit within max_width, maintaining aspect ratio.

        If explicit_w / explicit_h are given (from HTML attributes), use them
        as the *desired* size but still clamp to max_width and _IMAGE_MAX_HEIGHT.
        """
        if img_w <= 0 or img_h <= 0:
            return max_width, self._IMAGE_MAX_HEIGHT

        # Start from explicit or natural dimensions
        if explicit_w and explicit_h:
            display_w = float(explicit_w)
            display_h = float(explicit_h)
        elif explicit_w:
            aspect = img_w / img_h
            display_w = float(explicit_w)
            display_h = display_w / aspect
        elif explicit_h:
            aspect = img_w / img_h
            display_h = float(explicit_h)
            display_w = display_h * aspect
        else:
            display_w = float(img_w)
            display_h = float(img_h)

        # Clamp to available width
        if display_w > max_width:
            aspect = display_w / display_h
            display_w = max_width
            display_h = display_w / aspect

        # Clamp to max height
        if display_h > self._IMAGE_MAX_HEIGHT:
            aspect = display_w / display_h
            display_h = self._IMAGE_MAX_HEIGHT
            display_w = display_h * aspect

        return display_w, display_h

    def _measure_image(self, pango_ctx, block: ContentBlock, content_width: float) -> float:
        texture = self._load_texture(block.image_url)
        if texture is None:
            # Fallback placeholder height
            return self._line_height + 4

        # Apply percentage width constraint if specified (e.g. width="50%")
        effective_max_width = content_width
        if block.image_width_pct is not None and 0 < block.image_width_pct < 100:
            effective_max_width = content_width * (block.image_width_pct / 100.0)

        img_w = texture.get_width()
        img_h = texture.get_height()
        _, display_h = self._fit_image_size(
            img_w,
            img_h,
            effective_max_width,
            explicit_w=block.image_width,
            explicit_h=block.image_height,
        )

        # Add space for caption if alt text present
        caption_h = 0.0
        if block.image_alt:
            desc = self._scaled_font_desc()
            cap_size = max(int((self._base_font_size - 2) * self._zoom_level), 8)
            desc.set_size(cap_size * Pango.SCALE)
            layout = Pango.Layout.new(pango_ctx)
            layout.set_font_description(desc)
            layout.set_width(int(content_width * Pango.SCALE))
            layout.set_wrap(Pango.WrapMode.WORD_CHAR)
            layout.set_text(block.image_alt, -1)
            _, logical = layout.get_pixel_extents()
            caption_h = logical.height + 4

        return display_h + caption_h

    def _measure_image_row(self, pango_ctx, block: ContentBlock, content_width: float) -> float:
        """Measure a row of images laid out side-by-side.

        Images share the available width equally (minus gaps). Each image is
        scaled proportionally to fit its column, and the row height is the
        tallest image. Falls back to a vertical stack if any image texture is
        missing.
        """
        _IMAGE_ROW_GAP = 8  # horizontal gap between images

        images = block.images
        n = len(images)
        if n == 0:
            return self._line_height

        # Load all textures; if any fail we fall back to placeholder height
        textures = [self._load_texture(img["url"]) for img in images]

        max_h = 0.0
        # Compute the slot width for each image
        total_gap = _IMAGE_ROW_GAP * (n - 1)
        slot_w = max((content_width - total_gap) / n, 20)

        for i, (img, tex) in enumerate(zip(images, textures)):
            if tex is None:
                max_h = max(max_h, self._line_height + 4)
                continue
            iw = tex.get_width()
            ih = tex.get_height()
            _, dh = self._fit_image_size(iw, ih, slot_w, explicit_w=img.get("width"), explicit_h=img.get("height"))
            max_h = max(max_h, dh)

        return max_h
