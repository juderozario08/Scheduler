import calendar
import os
import re
import sys
from dataclasses import dataclass
from datetime import date as dt

import pytesseract
from PIL import Image

sys.dont_write_bytecode = True

PATH = os.environ.get('SCHEDULER_IMAGES_DIR',
                      '/Users/juderozario/Downloads/images/')
EXTRACTED_IMAGE = ''
EXTRACTED_TEXT: list[str] = []
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


def extract_time(time_str: str) -> list[int]:
    """Extracts [start_hour, start_minute, end_hour, end_minute] from a time range string."""
    cleaned = re.sub(r'\[.*?\]', '', time_str).strip()
    match = re.search(
        r'(\d{1,2}):(\d{2})\s*([APap][Mm])\s*-\s*(\d{1,2}):(\d{2})\s*([APap][Mm])',
        cleaned,
    )
    if match:
        sh, sm, s_ampm, eh, em, e_ampm = match.groups()
        start_hour, start_minute = int(sh), int(sm)
        end_hour, end_minute = int(eh), int(em)
        s_ampm, e_ampm = s_ampm.upper(), e_ampm.upper()

        if s_ampm == 'AM' and start_hour == 12:
            start_hour = 0
        elif s_ampm == 'PM' and start_hour < 12:
            start_hour += 12

        if e_ampm == 'AM' and end_hour == 12:
            end_hour = 0
        elif e_ampm == 'PM' and end_hour < 12:
            end_hour += 12

        return [start_hour, start_minute, end_hour, end_minute]

    # Fallback to manual split
    time_parts = cleaned.split('-')
    if len(time_parts) != 2 or ':' not in time_parts[0] or ':' not in time_parts[1]:
        raise ValueError(f"Invalid time format: '{time_str}'")

    start_parts = time_parts[0].strip().split(':')
    end_parts = time_parts[1].strip().split(':')

    start_hour = int(start_parts[0])
    s_upper = start_parts[1].upper()
    if 'AM' in s_upper and start_hour == 12:
        start_hour = 0
    elif 'PM' in s_upper and start_hour < 12:
        start_hour += 12

    end_hour = int(end_parts[0])
    e_upper = end_parts[1].upper()
    if 'AM' in e_upper and end_hour == 12:
        end_hour = 0
    elif 'PM' in e_upper and end_hour < 12:
        end_hour += 12

    m_start = re.search(r'\d+', start_parts[1])
    m_end = re.search(r'\d+', end_parts[1])
    start_minute = int(m_start.group()) if m_start else 0
    end_minute = int(m_end.group()) if m_end else 0

    return [start_hour, start_minute, end_hour, end_minute]


def check_change_for_month(data: str) -> int:
    """Returns the month number (1-12) if found in data, or -1 if none match."""
    for month_name, month_num in MONTH_NAMES.items():
        if month_name.lower() in data.lower():
            return month_num
    return -1


def format_data(
    data: list[list[str]],
    base_date: int | None = None,
    base_month: int | None = None,
    base_year: int | None = None,
) -> list[Shift]:
    """Converts raw parsed rows into structured Shift objects with month/year resolution."""
    cur_date = base_date if base_date is not None else CURRENT_DATE
    cur_month = base_month if base_month is not None else CURRENT_MONTH
    cur_year = base_year if base_year is not None else CURRENT_YEAR

    # If base_month was not specified and any date exceeds days in cur_month (e.g. day 31 in September),
    # advance to the next month where such date is valid
    if base_month is None and data:
        max_days = calendar.monthrange(cur_year, cur_month)[1]
        if any(int(row[0]) > max_days for row in data):
            cur_month += 1
            if cur_month > 12:
                cur_month = 1
                cur_year += 1

    shifts = []
    for line in data:
        date = int(line[0])
        month = cur_month
        year = cur_year
        start_hour, start_minute, end_hour, end_minute = extract_time(line[1])
        role = line[2]

        if cur_month == 12 and date < cur_date:
            year = cur_year + 1
            month = 1
        elif cur_date > date:
            month = cur_month + 1
            if month > 12:
                month = 1
                year = cur_year + 1

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


def get_text_from_picture(image_dir: str = PATH) -> list[str]:
    """Reads schedule images from image_dir, runs OCR, and populates extracted text lines."""
    global EXTRACTED_IMAGE, EXTRACTED_TEXT

    extracted_content = ""
    # Search image_dir if it exists; otherwise fall back to current directory
    target_dir = image_dir if os.path.isdir(image_dir) else '.'

    valid_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff')
    for image_name in sorted(os.listdir(target_dir)):
        if image_name.lower().endswith(valid_extensions):
            image_path = os.path.join(target_dir, image_name)
            with Image.open(image_path) as img:
                ocr_text = pytesseract.image_to_string(img)
                cleaned = ocr_text.replace('\r', '').replace(
                    ' ', '').replace('.', '')
                if cleaned:
                    extracted_content += cleaned + '\n'

    EXTRACTED_IMAGE = extracted_content
    EXTRACTED_TEXT = [line for line in EXTRACTED_IMAGE.splitlines() if line]
    return EXTRACTED_TEXT


def get_shifts_from_text(
    text_lines: list[str] | None = None,
    month: int | None = None,
    year: int | None = None,
) -> list[Shift]:
    """Parses extracted schedule lines to construct Shift objects."""
    if text_lines is None:
        text_lines = get_text_from_picture()

    # Check for month mentions in text lines if month not explicitly passed
    detected_month = month
    if detected_month is None and text_lines:
        for line in text_lines:
            m = check_change_for_month(line)
            if m != -1:
                detected_month = m
                break

    data = []
    num_lines = len(text_lines)

    for i in range(num_lines):
        line = text_lines[i]
        for day in DAYS:
            if day in line:
                # Search up to next 3 lines for the role identifier '/'
                role = None
                for offset in range(2, min(5, num_lines - i)):
                    candidate = text_lines[i + offset]
                    if any(d in candidate for d in DAYS):
                        break
                    if '/' in candidate:
                        role = candidate[candidate.find('/') + 1:].strip()
                        break

                if role is not None and i + 1 < num_lines:
                    # Date digits could appear before or after day name
                    date_part = line.replace('.', '')[:line.find(day)]
                    date_digits = ''.join(
                        ch for ch in date_part if ch.isdigit())
                    if not date_digits:
                        after_day = line.replace(
                            '.', '')[line.find(day) + len(day):]
                        date_digits = ''.join(
                            ch for ch in after_day if ch.isdigit())

                    if date_digits:
                        next_line = text_lines[i + 1]
                        bracket_idx = next_line.find('[')
                        shift_time = next_line[:bracket_idx] if bracket_idx != - \
                            1 else next_line
                        data.append([date_digits, shift_time, role])
                break

    return format_data(data, base_month=detected_month, base_year=year)


def main() -> None:
    parsed_shifts = get_shifts_from_text()
    print(f"Extracted {len(parsed_shifts)} shift(s):")
    for s in parsed_shifts:
        print(
            f"  {s.year}-{s.month:02d}-{s.date:02d}: "
            f"{s.start_hour:02d}:{
                s.start_minute:02d} - {s.end_hour:02d}:{s.end_minute:02d} ({s.role})"
        )


if __name__ == '__main__':
    main()
