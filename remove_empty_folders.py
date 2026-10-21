#!/usr/bin/env python3

"""
Usage:
    python remove_empty_folders.py <target_directory> [<target_directory2> ...]

Description:
    Recursively scans target directories from the deepest subfolders up
    and removes any empty directories.

Arguments:
    target_directory    One or more directory paths to scan and clean up.

Example:
    python remove_empty_folders.py /Volumes/iPhone/Storage
    python remove_empty_folders.py /path/to/dir1 /path/to/dir2
"""

import argparse
import os
import sys


def remove_empty_folders(path: str) -> None:
    # Traverse bottom-up (topdown=False) so deepest subdirectories are processed first
    for root, dirs, files in os.walk(path, topdown=False):
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            # Check if directory is empty (no files and no subdirectories)
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    print(f"Removed: {dir_path}")
            except OSError as e:
                print(f"Failed to remove: {dir_path} ({e})", file=sys.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Recursively find and remove empty folders from target directories."
    )
    parser.add_argument(
        "target_directories",
        nargs="+",
        metavar="target_directory",
        help="One or more directory paths to clean up",
    )

    args = parser.parse_args()

    for target_directory in args.target_directories:
        if os.path.isdir(target_directory):
            remove_empty_folders(target_directory)
            print(f"Completed processing: {target_directory}")
        else:
            print(
                f"Error: Specified path is not a directory or does not exist: {target_directory}",
                file=sys.stderr,
            )