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
    # Dictionary mapping (size, ext) => list of {"md5": str, "filePath": str, "source_idx": int}
    files_by_size = defaultdict(list)

    # Step 1: Read the input TSV file
    with open(tsv_file, "r", encoding="utf-8-sig") as f:
        total_rows = sum(1 for _ in f) - 1
    total_rows = max(total_rows, 0)

    with open(tsv_file, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for idx, row in enumerate(reader, start=1):
            if idx % 500 == 0 or idx == total_rows:
                pct = (idx / total_rows) * 100 if total_rows else 100.0
                print(
                    f"\r[Step 1/4] Reading TSV: {pct:.1f}% ({idx:,}/{total_rows:,})\033[K",
                    end="",
                    flush=True,
                )

            if not row.get("size"):
                continue
            try:
                size = int(row["size"])
            except ValueError:
                continue

            file_path = row.get("filePath") or row.get("fileName") or ""
            path_obj = Path(file_path)
            if any(part in EXCLUDED_DIRS for part in path_obj.parts):
                continue

            ext = path_obj.suffix.lower()
            files_by_size[(size, ext)].append(
                {
                    "md5": row.get("MD5", ""),
                    "filePath": file_path,
                    "source_idx": 0,
                }
            )
    print(
        f"\r[Step 1/4] Reading TSV: 100.0% ({total_rows:,}/{total_rows:,}) - Done\033[K"
    )

    # Step 2: Recursively scan specified directories and append files
    scan_tasks = []
    for src_idx, dir_path in enumerate(input_dirs, start=1):
        target_dir = Path(dir_path)
        if not target_dir.is_dir():
            print(
                f"\nWarning: Directory '{dir_path}' not found or is not a directory.",
                file=sys.stderr,
            )
            continue
        if target_dir.name in EXCLUDED_DIRS:
            continue

        try:
            top_entries = [
                p for p in target_dir.iterdir() if p.name not in EXCLUDED_DIRS
            ]
        except (PermissionError, OSError) as e:
            print(
                f"\nWarning: Failed to access '{target_dir}': {e}",
                file=sys.stderr,
            )
            continue

        units = []
        for entry in top_entries:
            if entry.is_dir() and len(top_entries) < 10:
                try:
                    sub_entries = [
                        p for p in entry.iterdir() if p.name not in EXCLUDED_DIRS
                    ]
                    if sub_entries:
                        units.extend(sub_entries)
                    else:
                        units.append(entry)
                except (PermissionError, OSError):
                    units.append(entry)
            else:
                units.append(entry)

        if not units:
            units = [target_dir]

        for u in units:
            scan_tasks.append((u, src_idx))

    total_tasks = len(scan_tasks)
    total_scanned_files = 0

    for task_idx, (unit, src_idx) in enumerate(scan_tasks, start=1):
        if unit.is_file():
            try:
                size = unit.stat().st_size
                ext = unit.suffix.lower()
                files_by_size[(size, ext)].append(
                    {
                        "md5": "",
                        "filePath": str(unit),
                        "source_idx": src_idx,
                    }
                )
                total_scanned_files += 1
            except (PermissionError, OSError):
                pass
        elif unit.is_dir():
            for root, dirs, files in os.walk(unit):
                dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]
                for file_name in files:
                    p = Path(root) / file_name
                    try:
                        size = p.stat().st_size
                        ext = p.suffix.lower()
                        files_by_size[(size, ext)].append(
                            {
                                "md5": "",
                                "filePath": str(p),
                                "source_idx": src_idx,
                            }
                        )
                        total_scanned_files += 1
                        if total_scanned_files % 200 == 0:
                            pct = (
                                ((task_idx - 1) / total_tasks) * 100
                                if total_tasks
                                else 0.0
                            )
                            print(
                                f"\r[Step 2/4] Scanning directories: {pct:.1f}% ({task_idx - 1}/{total_tasks} units, {total_scanned_files:,} files)\033[K",
                                end="",
                                flush=True,
                            )
                    except (PermissionError, OSError):
                        continue

        pct = (task_idx / total_tasks) * 100 if total_tasks else 100.0
        print(
            f"\r[Step 2/4] Scanning directories: {pct:.1f}% ({task_idx}/{total_tasks} units, {total_scanned_files:,} files)\033[K",
            end="",
            flush=True,
        )

    print(
        f"\r[Step 2/4] Scanning directories: 100.0% ({total_tasks}/{total_tasks} units, {total_scanned_files:,} files) - Done\033[K"
    )

    # Step 3: Remove entries where the file list size is 1
    total_sizes = len(files_by_size)
    sizes_to_delete = []
    for idx, (key, files) in enumerate(files_by_size.items(), start=1):
        if len(files) < 2:
            sizes_to_delete.append(key)
        if idx % 1000 == 0 or idx == total_sizes:
            pct = (idx / total_sizes) * 100 if total_sizes else 100.0
            print(
                f"\r[Step 3/4] Filtering unique size+ext: {pct:.1f}% ({idx:,}/{total_sizes:,})\033[K",
                end="",
                flush=True,
            )

    for key in sizes_to_delete:
        del files_by_size[key]

    print(
        f"\r[Step 3/4] Filtering unique size+ext: 100.0% ({total_sizes:,}/{total_sizes:,}) - Done ({len(files_by_size):,} candidate groups)\033[K"
    )

    # Step 4: Calculate MD5s, group duplicates, and write results to file
    total_step4_files = sum(len(files) for files in files_by_size.values())
    processed_files = 0
    duplicate_groups_count = 0

    with open(output_file, "w", encoding="utf-8") as out:
        for (size, ext), files in files_by_size.items():
            # 4.1 Compute MD5 for files missing an MD5 hash
            for item in files:
                if not item["md5"]:
                    item["md5"] = calculate_md5(Path(item["filePath"]))
                processed_files += 1
                if processed_files % 5 == 0 or processed_files == total_step4_files:
                    pct = (
                        (processed_files / total_step4_files) * 100
                        if total_step4_files
                        else 100.0
                    )
                    print(
                        f"\r[Step 4/4] Computing MD5 & finding duplicates: {pct:.1f}% ({processed_files:,}/{total_step4_files:,})\033[K",
                        end="",
                        flush=True,
                    )

            # Group files by MD5 hash within the same size group
            md5_groups = defaultdict(list)
            for item in files:
                if item["md5"]:  # Exclude files whose MD5 calculation failed
                    md5_groups[item["md5"]].append(item)

            # 4.2 Output groups with duplicate MD5 hashes (2 or more files)
            for md5, dup_files in md5_groups.items():
                if len(dup_files) < 2:
                    continue

                duplicate_groups_count += 1
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

    print(
        f"\r[Step 4/4] Computing MD5 & finding duplicates: 100.0% ({total_step4_files:,}/{total_step4_files:,}) - Done ({duplicate_groups_count:,} duplicate groups found)\033[K"
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