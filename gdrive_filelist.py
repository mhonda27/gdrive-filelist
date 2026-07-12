#!/usr/bin/env python3

# This script retrieves the names and MD5 checksums of all files in a Google
# Drive account using the Google Drive API and saves them to a TSV file.
# Please install the required libraries before running the script:
#   python3 -m pip install google-api-python-client
import csv
from googleapiclient.discovery import build
from google.oauth2 import service_account

import argparse

parser = argparse.ArgumentParser(
    description="Retrieve names and MD5 checksums of all files in a Google Drive account and save them to a TSV file."
)
parser.add_argument(
    "--test",
    action="store_true",
    help="Test mode: only retrieve a small number of files for testing purposes.",
)

args = parser.parse_args()

# You need to create a service account in your Google Cloud project and download the JSON key file.
# Make sure to share the Google Drive folder with the service account email to give it access.
SERVICE_ACCOUNT_FILE = "service-account.json"
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def get_drive_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES
    )

    service = build("drive", "v3", credentials=creds)
    return service


service = get_drive_service()

folder_map = {}
page_token = None

while True:
    results = (
        service.files()
        .list(
            q="mimeType = 'application/vnd.google-apps.folder'",
            fields="nextPageToken, files(id, name, parents)",
            pageToken=page_token,
        )
        .execute()
    )
    for f in results.get("files", []):
        folder_map[f["id"]] = {"name": f["name"], "parents": f.get("parents", [])}
    page_token = results.get("nextPageToken")
    if not page_token:
        break


def get_file_path(id, folder_map):
    folder_info = folder_map.get(id, {})
    parents = folder_info.get("parents", [])
    if not parents:
        return folder_info.get("name", "")
    return get_file_path(parents[0], folder_map) + "/" + folder_info["name"]


print(f"Got {len(folder_map)} folders.")

all_files = []
page_token = None

while True:
    # Retrieve a page of files from Google Drive
    results = (
        service.files()
        .list(
            pageSize=100 if args.test else 1000,
            q="mimeType != 'application/vnd.google-apps.folder' and trashed = false",
            fields="nextPageToken, files(name, md5Checksum, parents)",
            pageToken=page_token,
        )
        .execute()
    )

    files = results.get("files", [])
    all_files.extend(files)

    # Check if there is a next page of results
    page_token = results.get("nextPageToken")

    if (
        not page_token or args.test
    ):  # Stop if there are no more pages or if test mode is enabled
        break

print(f"Got {len(all_files)} files.")

with open("all_files.tsv", "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.writer(f, delimiter="\t")
    writer.writerow(["fileName", "MD5"])
    for file in all_files:
        checksum = file.get("md5Checksum", "")
        if not checksum:
            # Skip files without an MD5 checksum (e.g., Google Docs, Sheets, Slides)
            continue
        parents = file.get("parents", [])
        if parents:
            folder_path = get_file_path(parents[0], folder_map)
            full_file_name = f"{folder_path}/{file.get('name')}"
        else:
            full_file_name = file.get("name")
        writer.writerow([full_file_name, checksum])
