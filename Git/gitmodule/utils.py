# coding: utf-8

from pathlib import Path
from shutil import copyfileobj


def copytree(srcpath: Path, dstpath: Path):
    """
    Copy the source to the destination

    :param Path srcpath: The Path of the source
    :param Path dstpath: The Path of the destination
    """
    # iter over children of the directory to copy
    for src in srcpath.iterdir():
        # get the destination path of the copy
        dst = dstpath / src.name

        # if the source is a directory
        if src.is_dir():
            # create the destination directory
            dst.mkdir(parents=True, exist_ok=True)
            # copy the content of the source directory into the destination directory
            copytree(src, dst)
        # if the source is a file
        elif src.is_file():
            # ensure the parent directories exists
            dst.parent.mkdir(parents=True, exist_ok=True)
            # create the destination
            dst.touch()
            # copy the content of the source file into the destination file
            with src.open("rb") as srcf, dst.open("wb") as dstf:
                copyfileobj(srcf, dstf)
