import sys

sys.dont_write_bytecode = True

from dataclasses import dataclass
from datetime import date as dt
import os
from typing import Optional

try:
    from PIL import Image
    import pytesseract
except ImportError:
    Image = None
    pytesseract = None

PATH = '/Users/juderozario/Downloads/images/'
EXTRACTED_IMAGE = ''
EXTRACTED_TEXT = []
DAYS = [
    'Sunday',
    'Monday',
    'Tuesday',
    'Wednesday',
    'Thursday',
    'Friday',
    'Saturday',
]

_today = dt.today()
TODAY = str(_today)
CURRENT_DATE = _today.day
CURRENT_MONTH = _today.month
CURRENT_YEAR = _today.year

MONTH_NAMES = {
    'January': 1,
    'February': 2,
    'March': 3,
    'April': 4,
    'May': 5,
    'June': 6,
    'July': 7,
    'August': 8,
    'September': 9,
    'October': 10,
    'November': 11,
    'December': 12,
}


@dataclass
class Shift:
    """Represents a work shift extracted from schedule text or images."""
    year: int
    month: int
    date: int
    start_hour: int
    start_minute: int
    end_hour: int
    end_minute: int
    role: str

    def get_year(self) -> int:
        return self.year

    def get_month(self) -> int:
        return self.month

    def get_date(self) -> int:
        return self.date

    def get_start_hour(self) -> int:
        return self.start_hour

    def get_start_minute(self) -> int:
        return self.start_minute

    def get_end_hour(self) -> int:
        return self.end_hour

    def get_end_minute(self) -> int:
        return self.end_minute

    def get_role(self) -> str:
        return self.role


def get_text_from_picture(image_dir: str = PATH) -> list[str]:
    """Reads PNG images from image_dir, runs OCR, and populates extracted text lines."""
    global EXTRACTED_IMAGE, EXTRACTED_TEXT

    if Image is None or pytesseract is None:
        raise ImportError("Pillow and pytesseract are required for image OCR.")

    extracted_content = ""
    # Search image_dir if it exists; otherwise fall back to current directory
    target_dir = image_dir if os.path.isdir(image_dir) else '.'

    for image_name in sorted(os.listdir(target_dir)):
        if image_name.lower().endswith('.png'):
            image_path = os.path.join(target_dir, image_name)
            with Image.open(image_path) as img:
                ocr_text = pytesseract.image_to_string(img)
                extracted_content += ocr_text.replace('\r', '').replace(' ', '').replace('.', '')

    EXTRACTED_IMAGE = extracted_content
    EXTRACTED_TEXT = [line for line in EXTRACTED_IMAGE.splitlines() if line]
    return EXTRACTED_TEXT


def get_shifts_from_text(text_lines: Optional[list[str]] = None) -> list[Shift]:
    """Parses extracted schedule lines to construct Shift objects."""
    global EXTRACTED_TEXT

    if text_lines is None:
        get_text_from_picture()
        text_lines = EXTRACTED_TEXT

    data = []
    num_lines = len(text_lines)

    for i in range(num_lines):
        line = text_lines[i]
        for day in DAYS:
            if day in line:
                if i + 2 < num_lines and '/' in text_lines[i + 2]:
                    date_part = line.replace('.', '')[:line.find(day)]
                    date_digits = ''.join(ch for ch in date_part if ch.isdigit())
                    if date_digits:
                        next_line = text_lines[i + 1]
                        bracket_idx = next_line.find('[')
                        shift_time = next_line[:bracket_idx] if bracket_idx != -1 else next_line

                        role_line = text_lines[i + 2]
                        role = role_line[role_line.find('/') + 1:]
                        data.append([date_digits, shift_time, role])
                break

    return format_data(data)


def extract_time(time_str: str) -> list[int]:
    """Extracts [start_hour, start_minute, end_hour, end_minute] from a time range string."""
    time_parts = time_str.split('-')
    start_parts = time_parts[0].split(':')
    end_parts = time_parts[1].split(':')

    start_hour = int(start_parts[0])
    if 'PM' in start_parts[1] and start_hour < 12:
        start_hour += 12

    end_hour = int(end_parts[0])
    if 'PM' in end_parts[1] and end_hour < 12:
        end_hour += 12

    start_minute = int(start_parts[1][:2])
    end_minute = int(end_parts[1][:2])

    return [start_hour, start_minute, end_hour, end_minute]


def check_change_for_month(data: str) -> int:
    """Returns the month number (1-12) if found in data, or -1 if none match."""
    for month_name, month_num in MONTH_NAMES.items():
        if month_name in data:
            return month_num
    return -1


def format_data(data: list[list[str]]) -> list[Shift]:
    """Converts raw parsed rows into structured Shift objects with month/year resolution."""
    shifts = []
    for line in data:
        date = int(line[0])
        month = CURRENT_MONTH
        year = CURRENT_YEAR
        start_hour, start_minute, end_hour, end_minute = extract_time(line[1])
        role = line[2]

        if CURRENT_MONTH == 12 and date < CURRENT_DATE:
            year = CURRENT_YEAR + 1
            month = 1
        elif CURRENT_DATE > date:
            month = CURRENT_MONTH + 1

        shifts.append(
            Shift(
                year=year,
                month=month,
                date=date,
                start_hour=start_hour,
                start_minute=start_minute,
                end_hour=end_hour,
                end_minute=end_minute,
                role=role,
            )
        )
    return shifts
