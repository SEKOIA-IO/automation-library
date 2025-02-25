import argparse
import os
from functools import partial
from pathlib import Path

from PIL import Image

from .base import Validator
from .helpers import lighten_image, resize_canvas, square_canvas, transparent_background
from .models import CheckError, CheckResult


class LogoValidator(Validator):
    @classmethod
    def validate(cls, result: CheckResult, args: argparse.Namespace) -> None:
        if not result.options.get("path"):
            return

        check_logo_image(result=result)


def check_logo_image(result: CheckResult) -> None:
    module_dir: Path = result.options["path"]

    # Check whether SVG logo exists. If so, no need for other checks
    svg_path = module_dir / "logo.svg"
    if svg_path.is_file():
        return

    image_path = module_dir / "logo.png"

    if not image_path.is_file():
        result.errors.append(CheckError(filepath=image_path, error=f"Logo is missing"))
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
