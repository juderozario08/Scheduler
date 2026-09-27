import sys

sys.dont_write_bytecode = True

from collections import namedtuple
import datetime
import os
import pickle

try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
except ImportError:
    Request = None
    Credentials = None
    InstalledAppFlow = None
    build = None


from typing import Any, Optional


def _save_token(file_path: str, content: str) -> None:
    """Saves token content with secure file permissions (0600 - owner read/write only)."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    mode = 0o600
    fd = os.open(file_path, flags, mode)
    try:
        with open(fd, 'w') as token_file:
            token_file.write(content)
    except Exception:
        os.close(fd)
        raise


def create_service(
    client_secret_file: str,
    api_name: str,
    api_version: str,
    *scopes: Any,
    prefix: str = '',
    token_dir: Optional[str] = None,
) -> Any:
    """Creates and authenticates a Google API service instance."""
    if InstalledAppFlow is None or build is None:
        raise ImportError(
            "google-api-python-client, google-auth, and google-auth-oauthlib are required to create a Google API service."
        )

    api_service_name = api_name

    if scopes:
        if isinstance(scopes[0], (list, tuple, set)):
            effective_scopes = list(scopes[0])
        else:
            effective_scopes = list(scopes)
    else:
        effective_scopes = []

    creds = None
    if token_dir is None:
        token_dir = os.environ.get('GOOGLE_TOKEN_DIR')

    if token_dir is None:
        working_dir = os.getcwd()
        for candidate_name in ('token files', 'token_files', 'tokenfiles'):
            candidate_path = os.path.join(working_dir, candidate_name)
            if os.path.exists(candidate_path):
                token_dir = candidate_path
                break
        if token_dir is None:
            token_dir = os.path.join(working_dir, 'token files')

    os.makedirs(token_dir, mode=0o700, exist_ok=True)

    json_path = os.path.join(token_dir, f'token_{api_service_name}_{api_version}{prefix}.json')
    pickle_path = os.path.join(token_dir, f'token_{api_service_name}_{api_version}{prefix}.pickle')

    # Load existing credentials (JSON preferred; migrate legacy pickle if present)
    if os.path.exists(json_path) and Credentials is not None:
        try:
            creds = Credentials.from_authorized_user_file(json_path, effective_scopes)
        except Exception as e:
            print(f"Warning: Failed loading JSON token from {json_path}: {e}")
            creds = None

    if not creds and os.path.exists(pickle_path):
        try:
            with open(pickle_path, 'rb') as token_file:
                creds = pickle.load(token_file)
            # Safely migrate legacy pickle credentials to secure JSON format
            if creds and hasattr(creds, 'to_json'):
                _save_token(json_path, creds.to_json())
                try:
                    os.remove(pickle_path)
                except OSError:
                    pass
        except Exception as e:
            print(f"Warning: Failed loading legacy pickle token from {pickle_path}: {e}")
            creds = None

    # Refresh or run auth flow if invalid/missing
    if not creds or not creds.valid:
        refreshed = False
        if creds and creds.expired and creds.refresh_token and Request is not None:
            try:
                creds.refresh(Request())
                refreshed = True
            except Exception as e:
                print(f"Warning: Token refresh failed ({e}), requesting re-authentication.")
                creds = None

        if not refreshed or not creds:
            if not os.path.exists(client_secret_file):
                raise FileNotFoundError(
                    f"Client secrets file not found: '{client_secret_file}'. "
                    "Please provide a valid Google OAuth credentials.json file or set GOOGLE_CLIENT_SECRET_FILE."
                )
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, effective_scopes)
            creds = flow.run_local_server(port=0)

        # Save credentials with restrictive permissions
        if hasattr(creds, 'to_json'):
            _save_token(json_path, creds.to_json())
        else:
            with open(pickle_path, 'wb') as token_file:
                pickle.dump(creds, token_file)
            try:
                os.chmod(pickle_path, 0o600)
            except OSError:
                pass

    try:
        service = build(api_service_name, api_version, credentials=creds, static_discovery=False)
        print(api_service_name, api_version, 'service created successfully')
        return service
    except Exception as e:
        print(f"Error initializing {api_service_name} service: {e}")
        return None


# Alias for backwards compatibility
Create_Service = create_service


def convert_to_RFC_datetime(
    year: int = 1900,
    month: int = 1,
    day: int = 1,
    hour: int = 0,
    minute: int = 0,
    second: int = 0,
) -> str:
    """Formats datetime components into an RFC 3339 UTC timestamp string."""
    return datetime.datetime(year, month, day, hour, minute, second).isoformat() + 'Z'


class GoogleSheetsHelper:
    Paste_Type = namedtuple(
        '_Paste_Type',
        (
            'normal',
            'value',
            'format',
            'without_borders',
            'formula',
            'date_validation',
            'conditional_formatting',
        ),
    )(
        'PASTE_NORMAL',
        'PASTE_VALUES',
        'PASTE_FORMAT',
        'PASTE_NO_BORDERS',
        'PASTE_FORMULA',
        'PASTE_DATA_VALIDATION',
        'PASTE_CONDITIONAL_FORMATTING',
    )

    Paste_Orientation = namedtuple('_Paste_Orientation', ('normal', 'transpose'))('NORMAL', 'TRANSPOSE')

    Merge_Type = namedtuple(
        '_Merge_Type',
        ('merge_all', 'merge_columns', 'merge_rows'),
    )('MERGE_ALL', 'MERGE_COLUMNS', 'MERGE_ROWS')

    Delimiter_Type = namedtuple(
        '_Delimiter_Type',
        ('comma', 'semicolon', 'period', 'space', 'custom', 'auto_detect'),
    )('COMMA', 'SEMICOLON', 'PERIOD', 'SPACE', 'CUSTOM', 'AUTODETECT')

    Dimension = namedtuple('_Dimension', ('rows', 'columns'))('ROWS', 'COLUMNS')

    Value_Input_Option = namedtuple('_Value_Input_Option', ('raw', 'user_entered'))('RAW', 'USER_ENTERED')

    Value_Render_Option = namedtuple(
        '_Value_Render_Option',
        ['formatted', 'unformatted', 'formula'],
    )('FORMATTED_VALUE', 'UNFORMATTED_VALUE', 'FORMULA')

    @staticmethod
    def define_cell_range(
        sheet_id: int,
        start_row_number: int = 1,
        end_row_number: int = 0,
        start_column_number: int | None = None,
        end_column_number: int = 0,
    ) -> dict:
        """Returns a GridRange specification dictionary."""
        start_col = (start_column_number - 1) if start_column_number is not None else 0
        return {
            'sheetId': sheet_id,
            'startRowIndex': start_row_number - 1,
            'endRowIndex': end_row_number,
            'startColumnIndex': start_col,
            'endColumnIndex': end_column_number,
        }

    @staticmethod
    def define_dimension_range(sheet_id: int, dimension: str, start_index: int, end_index: int) -> dict:
        """Returns a DimensionRange specification dictionary."""
        return {
            'sheetId': sheet_id,
            'dimension': dimension,
            'startIndex': start_index,
            'endIndex': end_index,
        }


class GoogleCalendarHelper:
    pass


class GoogleDriverHelper:
    pass
