#!/usr/bin/env python3

"""
Usage:
    python find_duplicates.py <tsv_file> <dir1> [<dir2> ...] [-o <output_file>]

Description:
    Finds duplicate files across an initial TSV file and multiple directories,
    calculates missing MD5 checksums, classifies duplicate similarities, and
    outputs the formatted results to a file.

Arguments:
    tsv_file        Path to the initial TSV file containing size, MD5, and filePath.
    dir1, dir2...   One or more directories to scan recursively.
    -o, --output    Output file path (default: duplicates_result.csv).

Example:
    python find_duplicates.py initial_files.tsv /path/to/dir1 /path/to/dir2 -o duplicates_report.csv

    To remove duplicated files in dir1 (with same filename)
        awk -F',' '/duplicate/ {if($3==1 && $4==1) print $2}' duplicates_result.csv | tr '\n' '\0' | xargs -0 rm
    To remove duplicated files in dir2 (with same extension)
        awk -F',' '/duplicate/ {if($3==2 && $4==2) print $2}' duplicates_result.csv | tr '\n' '\0' | xargs -0 rm
"""

import argparse
import csv
import hashlib
import os
import sys
from collections import defaultdict
from pathlib import Path


def calculate_md5(file_path: Path, block_size: int = 65536) -> str:
    """Calculate the MD5 checksum of a file."""
    hasher = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(block_size), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except (PermissionError, OSError) as e:
        print(f"Warning: Failed to read '{file_path}': {e}", file=sys.stderr)
        return ""


EXCLUDED_DIRS = {".Spotlight-V100"}


def process_files(tsv_file: str, input_dirs: list[str], output_file: str) -> None:
    # Dictionary mapping size => list of {"md5": str, "filePath": str, "source_idx": int}
    files_by_size = defaultdict(list)

    # Step 1: Read the input TSV file
    with open(tsv_file, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if not row.get("size"):
                continue
            try:
                size = int(row["size"])
            except ValueError:
                continue

            file_path = row.get("filePath") or row.get("fileName") or ""
            if any(part in EXCLUDED_DIRS for part in Path(file_path).parts):
                continue

            files_by_size[size].append(
                {
                    "md5": row.get("MD5", ""),
                    "filePath": file_path,
                    "source_idx": 0,
                }
            )

    # Step 2: Recursively scan specified directories and append files
    for idx, dir_path in enumerate(input_dirs, start=1):
        target_dir = Path(dir_path)
        if not target_dir.is_dir():
            print(
                f"Warning: Directory '{dir_path}' not found or is not a directory.",
                file=sys.stderr,
            )
            continue

        if target_dir.name in EXCLUDED_DIRS:
            continue

        for root, dirs, files in os.walk(target_dir):
            dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
            for file_name in files:
                p = Path(root) / file_name
                try:
                    size = p.stat().st_size
                    files_by_size[size].append(
                        {
                            "md5": "",
                            "filePath": str(p),
                            "source_idx": idx,
                        }
                    )
                except (PermissionError, OSError):
                    continue

    # Step 3: Remove entries where the file list size is 1
    sizes_to_delete = [
        size for size, files in files_by_size.items() if len(files) < 2
    ]
    for size in sizes_to_delete:
        del files_by_size[size]

    # Step 4: Calculate MD5s, group duplicates, and write results to file
    with open(output_file, "w", encoding="utf-8") as out:
        for size, files in files_by_size.items():
            # 4.1 Compute MD5 for files missing an MD5 hash
            for item in files:
                if not item["md5"]:
                    item["md5"] = calculate_md5(Path(item["filePath"]))

            # Group files by MD5 hash within the same size group
            md5_groups = defaultdict(list)
            for item in files:
                if item["md5"]:  # Exclude files whose MD5 calculation failed
                    md5_groups[item["md5"]].append(item)

            # 4.2 Output groups with duplicate MD5 hashes (2 or more files)
            for md5, dup_files in md5_groups.items():
                if len(dup_files) < 2:
                    continue

                # Output header line: filesize: {size}, md5: {md5}
                out.write(f"filesize: {size}, md5: {md5}\n")

                # 4.3 Set the first item as 'original', the remaining items as 'duplicate'
                original = dup_files[0]
                duplicates = dup_files[1:]

                orig_path = Path(original["filePath"])
                orig_name = orig_path.name
                orig_suffix = orig_path.suffix

                # Output original line: original,{filePath},0,0
                out.write(f"original,{original['filePath']},0,0\n")

                # 4.4 Determine similarity and output duplicate lines
                # similarity=1: exact filename match
                # similarity=2: exact file extension match
                # similarity=3: otherwise
                for dup in duplicates:
                    dup_path = Path(dup["filePath"])

                    if dup_path.name == orig_name:
                        similarity = 1
                    elif dup_path.suffix and dup_path.suffix == orig_suffix:
                        similarity = 2
                    else:
                        similarity = 3

                    category = dup["source_idx"]
                    out.write(
                        f"duplicate,{dup['filePath']},{category},{similarity}\n"
                    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Find duplicate files across an initial TSV file and multiple directories."
    )
    parser.add_argument("tsv_file", help="Path to input TSV file")
    parser.add_argument(
        "dirs", nargs="+", help="Directories to scan recursively"
    )
    parser.add_argument(
        "-o",
        "--output",
        default="duplicates_result.csv",
        help="Output file path (default: duplicates_result.csv)",
    )

    args = parser.parse_args()
    process_files(args.tsv_file, args.dirs, args.output)