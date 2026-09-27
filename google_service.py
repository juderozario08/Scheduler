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


def create_service(client_secret_file: str, api_name: str, api_version: str, *scopes, prefix: str = ''):
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
    working_dir = os.getcwd()
    token_dir = os.path.join(working_dir, 'token files')
    if not os.path.exists(token_dir):
        if os.path.exists(os.path.join(working_dir, 'token_files')):
            token_dir = os.path.join(working_dir, 'token_files')
        elif os.path.exists(os.path.join(working_dir, 'tokenfiles')):
            token_dir = os.path.join(working_dir, 'tokenfiles')

    os.makedirs(token_dir, exist_ok=True)

    json_path = os.path.join(token_dir, f'token_{api_service_name}_{api_version}{prefix}.json')
    pickle_path = os.path.join(token_dir, f'token_{api_service_name}_{api_version}{prefix}.pickle')

    # Load existing credentials (JSON preferred, fallback to pickle)
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
        except Exception as e:
            print(f"Warning: Failed loading pickle token from {pickle_path}: {e}")
            creds = None

    # Refresh or run auth flow if invalid/missing
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token and Request is not None:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, effective_scopes)
            creds = flow.run_local_server(port=0)

        # Save credentials
        if hasattr(creds, 'to_json'):
            with open(json_path, 'w') as token_file:
                token_file.write(creds.to_json())
        else:
            with open(pickle_path, 'wb') as token_file:
                pickle.dump(creds, token_file)

    try:
        service = build(api_service_name, api_version, credentials=creds, static_discovery=False)
        print(api_service_name, api_version, 'service created successfully')
        return service
    except Exception as e:
        print(e)
        print(f'Failed to create service instance for {api_service_name}')
        if os.path.exists(json_path):
            os.remove(json_path)
        if os.path.exists(pickle_path):
            os.remove(pickle_path)
        return None


# Alias for backwards compatibility
Create_Service = create_service


def convert_to_RFC_datetime(year: int = 1900, month: int = 1, day: int = 1, hour: int = 0, minute: int = 0) -> str:
    """Formats datetime components into an RFC 3339 UTC timestamp string."""
    return datetime.datetime(year, month, day, hour, minute, 0).isoformat() + 'Z'


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
