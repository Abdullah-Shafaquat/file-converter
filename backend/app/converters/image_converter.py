"""Image conversions backed by Pillow (raster) and optionally svglib (vector)."""

from __future__ import annotations

import logging
from pathlib import Path

from PIL import Image, ImageOps

from app.converters.base import BaseConverter, ConversionContext
from app.converters.formats import canonical_extension
from app.models.schemas import Category
from app.utils.errors import ConversionFailedError, DependencyMissingError

logger = logging.getLogger(__name__)

Image.MAX_IMAGE_PIXELS = 400_000_000


def svg_raster_support() -> bool:
    """True when svglib and reportlab can rasterise an SVG.

    svglib pulls in pyppmd, which has no prebuilt wheel on Windows and would
    require a C toolchain. SVG rasterisation is therefore optional: when it
    is unavailable, SVG pairs are hidden from the matrix instead of failing
    mid-conversion.
    """
    try:
        from reportlab.graphics import renderPM  # noqa: F401
        from svglib.svglib import svg2rlg  # noqa: F401
    except ImportError:
        return False
    return True

# Pillow cannot write AVIF/HEIC without the optional AVIF plugin.
PILLOW_FORMAT_MAP: dict[str, str] = {
    "jpg": "JPEG",
    "jpeg": "JPEG",
    "png": "PNG",
    "webp": "WEBP",
    "gif": "GIF",
    "bmp": "BMP",
    "tiff": "TIFF",
    "ico": "ICO",
    "avif": "AVIF",
    "heic": "HEIF",
}

# Formats that cannot represent an alpha channel or animation.
MUST_FLATTEN_ALPHA: frozenset[str] = frozenset({"jpg", "jpeg", "bmp"})

# Sources that need alpha dropped before being written to these targets.
ALPHA_HOSTILE_TARGETS: frozenset[str] = frozenset({"jpg", "jpeg", "bmp"})

MAX_ICON_SIZES: tuple[tuple[int, int], ...] = (
    (16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256),
)


class ImageConverter(BaseConverter):
    name = "image"
    category = Category.IMAGE
    source_formats = frozenset(
        {"jpg", "jpeg", "png", "webp", "gif", "bmp", "tiff", "ico", "avif", "heic", "svg"}
    )
    target_formats = frozenset(
        {"jpg", "png", "webp", "bmp", "tiff", "ico", "avif", "gif", "svg"}
    )

    def can_convert(self, source_format: str, target_format: str) -> bool:
        source = canonical_extension(source_format)
        target = canonical_extension(target_format)
        if source not in self.source_formats or target not in self.target_formats:
            return False
        if source == target:
            return False
        # SVG is a vector input only; rasterising a raster image "to SVG"
        # would be tracing, which we deliberately do not fake.
        if target == "svg" and source != "svg":
            return False
        if source == "svg" and target == "ico":
            return False
        if source == "svg" and not svg_raster_support():
            # Without svglib there is no rasteriser; hide the pair rather than
            # failing after the user has already uploaded the file.
            return False
        return True

    def convert(
        self,
        input_path: Path,
        output_path: Path,
        context: ConversionContext | None = None,
    ) -> Path:
        ctx = self._context(context)
        source_ext = canonical_extension(input_path.suffix)
        target_ext = canonical_extension(output_path.suffix)
        self._require(source_ext, target_ext)

        ctx.update(5, f"Reading {source_ext.upper()} image")
        if source_ext == "svg":
            return self._convert_svg(input_path, output_path, target_ext, ctx)

        try:
            with Image.open(input_path) as image:
                image.load()
                ctx.update(30, "Decoding image")
                prepared = self._prepare(image, target_ext)
                ctx.update(70, f"Encoding {target_ext.upper()}")
                self._save(prepared, output_path, target_ext)
        except DependencyMissingError:
            raise
        except ConversionFailedError:
            raise
        except Exception as exc:  # noqa: BLE001 - re-raised as a user-safe error
            logger.exception("Image conversion failed: %s -> %s", source_ext, target_ext)
            raise ConversionFailedError(f"Could not process this image: {exc}") from exc

        ctx.update(100, "Complete")
        return output_path

    def _prepare(self, image: Image.Image, target_ext: str) -> Image.Image:
        working = ImageOps.exif_transpose(image) or image

        if target_ext in ALPHA_HOSTILE_TARGETS:
            if working.mode in ("RGBA", "LA", "P"):
                working = working.convert("RGBA")
                background = Image.new("RGB", working.size, (255, 255, 255))
                background.paste(working, mask=working.split()[-1])
                working = background
            elif working.mode != "RGB":
                working = working.convert("RGB")
        elif working.mode == "P":
            working = working.convert("RGBA")
        elif working.mode not in ("RGB", "RGBA", "L", "LA", "1"):
            working = working.convert("RGBA")

        if target_ext in ("jpg", "jpeg"):
            working = working.convert("RGB")

        if target_ext in ("bmp",) and working.mode == "RGBA":
            working = working.convert("RGB")

        return working

    def _save(self, image: Image.Image, output_path: Path, target_ext: str) -> None:
        if target_ext == "ico":
            self._save_ico(image, output_path)
            return

        pil_format = PILLOW_FORMAT_MAP.get(target_ext)
        if pil_format is None:
            raise ConversionFailedError(f"Cannot write {target_ext.upper()} images.")

        options: dict[str, object] = {}
        if target_ext in ("jpg", "jpeg"):
            options = {"quality": 90, "optimize": True, "progressive": True}
        elif target_ext == "png":
            options = {"optimize": True}
        elif target_ext == "webp":
            options = {"quality": 90, "method": 6}
        elif target_ext == "tiff":
            options = {"compression": "tiff_deflate"}

        try:
            image.save(output_path, format=pil_format, **options)
        except (KeyError, ValueError) as exc:
            if target_ext in ("avif", "heic"):
                raise DependencyMissingError(
                    "AVIF/HEIC support requires the 'pillow-avif-plugin' package."
                ) from exc
            raise

    def _save_ico(self, image: Image.Image, output_path: Path) -> None:
        source = image if image.mode in ("RGBA", "RGB") else image.convert("RGBA")
        if max(source.size) < 256:
            source.save(output_path, format="ICO", sizes=[(w, h) for w, h in MAX_ICON_SIZES])
            return
        images = []
        for size in MAX_ICON_SIZES:
            resized = source.copy()
            resized.thumbnail(size, Image.LANCZOS)
            images.append(resized)
        images[0].save(output_path, format="ICO", sizes=images)

    def _convert_svg(
        self,
        input_path: Path,
        output_path: Path,
        target_ext: str,
        ctx: ConversionContext,
    ) -> Path:
        """Rasterise SVG via svglib + reportlab (no native Cairo needed)."""
        if target_ext == "svg":
            raise ConversionFailedError("SVG to SVG is not a meaningful conversion.")

        try:
            from reportlab.graphics import renderPM
            from svglib.svglib import svg2rlg
        except ImportError as exc:
            raise DependencyMissingError(
                "SVG rasterisation needs the 'svglib' package, which requires a C "
                "toolchain on Windows. Convert the SVG in a vector editor instead."
            ) from exc

        ctx.update(25, "Parsing SVG")
        try:
            drawing = svg2rlg(str(input_path))
        except Exception as exc:  # noqa: BLE001
            raise ConversionFailedError(f"Could not parse this SVG file: {exc}") from exc

        if drawing is None or drawing.width == 0 or drawing.height == 0:
            raise ConversionFailedError("This SVG file has no drawable content.")

        if drawing.width > 10000 or drawing.height > 10000:
            raise ConversionFailedError("This SVG is too large to rasterise safely.")

        ctx.update(55, f"Rendering {target_ext.upper()}")
        pil_format = PILLOW_FORMAT_MAP.get(target_ext)
        if pil_format is None:
            raise ConversionFailedError(f"Cannot write {target_ext.upper()} from SVG.")

        try:
            rendered = renderPM.drawToPIL(
                drawing, fmt="PNG", bg=0xFFFFFF, dpi=96
            )
        except Exception as exc:  # noqa: BLE001
            raise ConversionFailedError(f"Could not render this SVG file: {exc}") from exc

        ctx.update(80, f"Encoding {target_ext.upper()}")
        try:
            self._save(self._prepare(rendered, target_ext), output_path, target_ext)
        finally:
            rendered.close()

        ctx.update(100, "Complete")
        return output_path
