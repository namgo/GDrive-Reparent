import os
import argparse
import shutil
from pathlib import Path
from textwrap import wrap, dedent
import queue

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import xdg.BaseDirectory

SCOPES = ["https://www.googleapis.com/auth/drive"]

parser = argparse.ArgumentParser()
parser.add_argument(
    "--app-credentials",
    help=dedent(
        """
    client_secret.json file downloaded from https://console.cloud.google.com
    which identifies this instance of the application.

    This will be cached, so it only needs to be provided once.

    See https://developers.google.com/identity/protocols/oauth2/web-server#creatingcred.
    You should make sure to create a "Desktop App" credential in the developer console.
    """
    ),
    type=argparse.FileType("r"),
)
parser.add_argument(
    "--delete", help="delete extraneous files from dest dirs", action="store_true"
)
parser.add_argument(
    "source",
    help="Folder or file to copy from, e.g. https://drive.google.com/drive/folders/ 1DCwcbejwdN-Clc5bgk5CJfjo3FQaGTaQ or 1DCwcbejwdN-Clc5bgk5CJfjo3FQaGTaQ",
)
parser.add_argument(
    "dest",
    help="To team drive, e.g. https://drive.google.com/drive/folders/13R6I-wx4e4Axw5SiIaF7VjhpKXByA_Qz or 13R6I-wx4e4Axw5SiIaF7VjhpKXByA_Qz",
)


def authenticate(filename_token, filename_credentials):
    if not Path(filename_credentials).exists():
        raise PermissionError(
            "You must provide a Google API client_secret.json file via --app-credentials. See --help for guidance."
        )

    creds = None
    if Path(filename_token).exists():
        creds = Credentials.from_authorized_user_file(filename_token, SCOPES)
    if not creds or not creds.valid:
        if creds and not creds.expired and creds.refresh_token:
            creds.Refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                filename_credentials, scopes=SCOPES
            )
            creds = flow.run_local_server(open_browser=False)
            with open(filename_token, "w") as token:
                token.write(creds.to_json())
    return creds


args = parser.parse_args()


def list_contents_of_folder(drive, folder_id):
    return (
        drive.files().list(q=f'"{folder_id}" in parents and trashed = false').execute()
    )


def recurse_folders(drive, folder_id_top):
    q = queue.Queue()

    q.put((folder_id_top, "./"))
    while True:
        if q.empty():
            print("done")
            return
        else:
            (folder_id, folder_name) = q.get()
            response = list_contents_of_folder(drive, folder_id)
            if getattr(response, "nextPageToken", None):
                next_page_token = response["nextPageToken"]
            for r in response["files"]:
                if r["mimeType"] == "application/vnd.google-apps.folder":
                    q.put((r["id"], os.path.join(folder_name, r["name"])))
                print(os.path.join(folder_name, r["name"]))


from_id = os.path.basename(args.source)  # TODO: input validation
to_id = os.path.basename(args.dest)

app_credentials = os.path.join(
    xdg.BaseDirectory.save_cache_path("gdrive-rync"), "client_secret.json"
)
user_credentials = os.path.join(
    xdg.BaseDirectory.save_cache_path("gdrive-rync"), "token.json"
)

# if args.app_credentials:
#    shutil.copy(args.app_credentials, app_credentials)

if args.app_credentials:
    with open(app_credentials, "w") as app_credentials_:
        shutil.copyfileobj(args.app_credentials, app_credentials_)

        # user creds are invalid if the app creds they are contained in change, so toss them
        # TODO: check if the credentials are equal before overwriting; if so, don't invalidate?
        if Path(user_credentials).exists():
            os.unlink(user_credentials)

creds = authenticate(user_credentials, app_credentials)

with build("drive", "v3", credentials=creds) as service:
    # list directory for now
    # r = list_contents_of_folder(from_id, service)
    recurse_folders(service, from_id)
