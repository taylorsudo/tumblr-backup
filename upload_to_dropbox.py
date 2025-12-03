import os
import sys
import dropbox
from pathlib import Path

def upload_folder_to_dropbox(local_folder, dropbox_path, access_token):
    """
    Upload all files from a local folder to Dropbox.

    Args:
        local_folder: Path to local folder to upload
        dropbox_path: Destination path in Dropbox (e.g., '/Tumblr')
        access_token: Dropbox access token
    """
    dbx = dropbox.Dropbox(access_token)

    # Verify the token works
    try:
        dbx.users_get_current_account()
        print("Successfully connected to Dropbox")
    except dropbox.exceptions.AuthError as e:
        print(f"ERROR: Invalid access token: {e}")
        sys.exit(1)

    local_path = Path(local_folder)

    if not local_path.exists():
        print(f"ERROR: Local folder '{local_folder}' does not exist")
        sys.exit(1)

    # Upload all files in the folder
    uploaded_count = 0
    for file_path in local_path.rglob('*'):
        if file_path.is_file():
            # Calculate relative path for Dropbox
            relative_path = file_path.relative_to(local_path)
            dropbox_file_path = f"{dropbox_path}/{relative_path}".replace('\\', '/')

            try:
                with open(file_path, 'rb') as f:
                    file_size = file_path.stat().st_size

                    # For files larger than 150MB, use upload session
                    if file_size > 150 * 1024 * 1024:
                        print(f"Large file detected ({file_size} bytes), using upload session...")
                        upload_large_file(dbx, f, dropbox_file_path, file_size)
                    else:
                        # Regular upload for smaller files
                        dbx.files_upload(
                            f.read(),
                            dropbox_file_path,
                            mode=dropbox.files.WriteMode.overwrite
                        )

            except Exception as e:
                print(f"✗ Failed to upload {file_path}: {e}")

    print(f"\nUpload complete! {uploaded_count} file(s) uploaded to Dropbox.")

def upload_large_file(dbx, file_obj, dropbox_path, file_size):
    """Upload large files using upload session."""
    CHUNK_SIZE = 4 * 1024 * 1024  # 4MB chunks

    session_start = dbx.files_upload_session_start(file_obj.read(CHUNK_SIZE))
    cursor = dropbox.files.UploadSessionCursor(
        session_id=session_start.session_id,
        offset=file_obj.tell()
    )
    commit = dropbox.files.CommitInfo(path=dropbox_path, mode=dropbox.files.WriteMode.overwrite)

    while file_obj.tell() < file_size:
        if (file_size - file_obj.tell()) <= CHUNK_SIZE:
            # Last chunk
            dbx.files_upload_session_finish(
                file_obj.read(CHUNK_SIZE),
                cursor,
                commit
            )
        else:
            dbx.files_upload_session_append_v2(
                file_obj.read(CHUNK_SIZE),
                cursor
            )
            cursor.offset = file_obj.tell()

if __name__ == "__main__":
    # Get configuration from environment variables
    access_token = os.environ.get('DROPBOX_ACCESS_TOKEN')
    local_folder = os.environ.get('LOCAL_FOLDER', 'backup')
    dropbox_path = os.environ.get('DROPBOX_PATH', '')

    if not access_token:
        print("ERROR: DROPBOX_ACCESS_TOKEN environment variable not set")
        sys.exit(1)

    upload_folder_to_dropbox(local_folder, dropbox_path, access_token)
