#!/usr/bin/env python3

import os
import hashlib
from pathlib import Path
import argparse

parser = argparse.ArgumentParser(
    description="Search for files with '(1)' in their name and delete them if they match the MD5 hash of the original file."
)
parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Perform a dry run without deleting any files. Only print the files that would be deleted.",
)

args = parser.parse_args()

def get_md5(file_path):
    """Calculate the MD5 hash of a file."""
    hash_md5 = hashlib.md5()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception:
        return None

# Google Docs extensions to skip (since they are metadata/shortcut files and MD5 comparisons don't apply)
GOOGLE_DOC_EXTENSIONS = {
    ".gdoc",
    ".gsheet",
    ".gslides",
    ".gform",
    ".gdraw",
    ".gtable",
    ".glink",
    ".gmap",
}

def clean_duplicate_files(root_dir=".", dry_run=True):
    """
    Search for files with '(1)' in their name and delete them 
    if they match the MD5 hash of the original file.
    """
    root = Path(root_dir)
    
    # Recursively find all files containing ' (1)'
    for path in root.rglob("* (2).*"):
        if not path.is_file():
            continue
            
        # Skip Google Docs files
        if path.suffix.lower() in GOOGLE_DOC_EXTENSIONS:
            continue
            
        # Construct the potential original filename
        # e.g., "image (1).jpg" -> "image.jpg"
        name = path.stem
        parent = path.parent
        suffix = path.suffix
        
        clean_name = name.replace(" (2)", "")
        original_path = parent / f"{clean_name}{suffix}"
        
        if original_path.exists():
            print(f"Comparing: {path.name} <-> {original_path.name}")
            
            # Compare MD5 hashes
            if get_md5(path) == get_md5(original_path):
                if dry_run:
                    print(f"[Dry Run] Match found. Target for deletion: {path}")
                else:
                    path.unlink()
                    print(f"[Deleted] {path}")
            else:
                print(f"[Skipped] Hashes do not match: {path.name}")

if __name__ == "__main__":
    clean_duplicate_files(dry_run=args.dry_run)
