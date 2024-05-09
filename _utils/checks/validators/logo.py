import argparse
import os
from pathlib import Path
from functools import partial

from PIL import Image

from .base import Validator
from .helpers import square_canvas, transparent_background, resize_canvas, lighten_image
from .models import CheckError, CheckResult


class LogoValidator(Validator):
    @classmethod
    def validate(cls, result: CheckResult, args: argparse.Namespace) -> None:
        if not result.options.get("path"):
            return

        module_dir: Path = result.options["path"]
        logo_path = module_dir / "logo.png"

        check_logo_image(image_path=logo_path, result=result)


def check_logo_image(image_path: Path, result: CheckResult) -> None:
    from PIL import Image

    def has_transparency(img: Image):
        if img.info.get("transparency", None) is not None:
            return True

        elif img.mode == "P":
            transparent = img.info.get("transparency", -1)
            for _, index in img.getcolors():
                if index == transparent:
                    return True

        elif img.mode == "RGBA":
            extrema = img.getextrema()
            if extrema[3][0] < 255:
                return True

        return False

    if not image_path.is_file():
        result.errors.append(
            CheckError(filepath=image_path, error=f"logo.png is missing")
        )
        return

    image = Image.open(image_path)
    if image.format != "PNG":
        result.errors.append(
            CheckError(filepath=image_path, error="Logo is not in PNG format")
        )

    if image.width != image.height:
        result.errors.append(
            CheckError(
                filepath=image_path,
                error=f"Logo is not square - {image.width}x{image.height}px",
                fix_label="Resize canvas",
                fix=partial(
                    fix_square_canvas, source=image_path, destination=image_path
                ),
            )
        )

    if not has_transparency(image):
        result.errors.append(
            CheckError(
                filepath=image_path,
                error="Logo background is not transparent",
                fix_label="Make logo background transparent",
                fix=partial(
                    fix_transparent_background,
                    source=image_path,
                    destination=image_path,
                ),
            )
        )

    if os.path.getsize(image_path) > 50 * 1024:
        result.errors.append(
            CheckError(
                filepath=image_path,
                error="Logo file weights more than 50 KiB",
                fix_label="Lighten image",
                fix=partial(
                    fix_lighten_image, source=image_path, destination=image_path
                ),
            )
        )

    image.close()

    result.options["logo_path"] = image_path


def fix_transparent_background(source: Path, destination: Path, fuzz: int = 0):
    """
    Transform the white background into transparent one
    """
    transparent_background(Image.open(source), fuzz).save(destination)


def fix_resize_canvas(
    source: Path, destination: Path, canvas_width: int = 500, canvas_height: int = 500
):
    """
    Resize the canvas of the image
    """
    resize_canvas(
        Image.open(source), canvas_width=canvas_width, canvas_height=canvas_height
    ).save(destination)


def fix_square_canvas(source: Path, destination: Path):
    """
    Square the canvas of the image
    """
    square_canvas(Image.open(source)).save(destination)


def fix_lighten_image(source: Path, destination: Path, size: int = 50000):
    """
    Downsize the image until its weight is lesser than the supplied parameter
    """
    lighten_image(Image.open(source), size).save(destination)
