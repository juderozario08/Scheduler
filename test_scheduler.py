import sys

sys.dont_write_bytecode = True

import unittest
from unittest.mock import MagicMock, patch

from calendar_sync import build_event_body, sync_shifts_to_calendar
from google_service import GoogleSheetsHelper, convert_to_RFC_datetime
from schedule_parser import (
    DAYS,
    MONTH_NAMES,
    Shift,
    check_change_for_month,
    extract_time,
    format_data,
    get_shifts_from_text,
)


class TestShiftClass(unittest.TestCase):
    def test_shift_initialization_and_getters(self):
        shift = Shift(
            year=2026,
            month=9,
            date=30,
            start_hour=13,
            start_minute=30,
            end_hour=20,
            end_minute=30,
            role='StockPutaway',
        )
        self.assertEqual(shift.get_year(), 2026)
        self.assertEqual(shift.get_month(), 9)
        self.assertEqual(shift.get_date(), 30)
        self.assertEqual(shift.get_start_hour(), 13)
        self.assertEqual(shift.get_start_minute(), 30)
        self.assertEqual(shift.get_end_hour(), 20)
        self.assertEqual(shift.get_end_minute(), 30)
        self.assertEqual(shift.get_role(), 'StockPutaway')

    def test_shift_dataclass_equality(self):
        s1 = Shift(2026, 9, 30, 10, 0, 18, 0, 'Cashier')
        s2 = Shift(2026, 9, 30, 10, 0, 18, 0, 'Cashier')
        self.assertEqual(s1, s2)


class TestExtractTime(unittest.TestCase):
    def test_extract_time_am_to_pm(self):
        result = extract_time('10:00AM-6:00PM')
        self.assertEqual(result, [10, 0, 18, 0])

    def test_extract_time_pm_to_pm(self):
        result = extract_time('1:30PM-8:30PM')
        self.assertEqual(result, [13, 30, 20, 30])

    def test_extract_time_12pm_noon(self):
        result = extract_time('12:00PM-5:00PM')
        self.assertEqual(result, [12, 0, 17, 0])


class TestCheckChangeForMonth(unittest.TestCase):
    def test_all_months(self):
        for month_name, month_num in MONTH_NAMES.items():
            self.assertEqual(check_change_for_month(f"Schedule for {month_name}"), month_num)

    def test_unknown_string(self):
        self.assertEqual(check_change_for_month("No month here"), -1)


class TestFormatData(unittest.TestCase):
    @patch('schedule_parser.CURRENT_DATE', 20)
    @patch('schedule_parser.CURRENT_MONTH', 9)
    @patch('schedule_parser.CURRENT_YEAR', 2026)
    def test_format_data_same_month(self):
        raw = [['25', '10:00AM-6:00PM', 'StockPutaway']]
        shifts = format_data(raw)
        self.assertEqual(len(shifts), 1)
        self.assertEqual(shifts[0].year, 2026)
        self.assertEqual(shifts[0].month, 9)
        self.assertEqual(shifts[0].date, 25)
        self.assertEqual(shifts[0].role, 'StockPutaway')

    @patch('schedule_parser.CURRENT_DATE', 25)
    @patch('schedule_parser.CURRENT_MONTH', 9)
    @patch('schedule_parser.CURRENT_YEAR', 2026)
    def test_format_data_next_month_rollover(self):
        raw = [['5', '1:30PM-8:30PM', 'StockPutaway']]
        shifts = format_data(raw)
        self.assertEqual(len(shifts), 1)
        self.assertEqual(shifts[0].year, 2026)
        self.assertEqual(shifts[0].month, 10)
        self.assertEqual(shifts[0].date, 5)

    @patch('schedule_parser.CURRENT_DATE', 25)
    @patch('schedule_parser.CURRENT_MONTH', 12)
    @patch('schedule_parser.CURRENT_YEAR', 2026)
    def test_format_data_year_rollover(self):
        raw = [['2', '1:30PM-8:30PM', 'StockPutaway']]
        shifts = format_data(raw)
        self.assertEqual(len(shifts), 1)
        self.assertEqual(shifts[0].year, 2027)
        self.assertEqual(shifts[0].month, 1)
        self.assertEqual(shifts[0].date, 2)


class TestGetShiftsFromText(unittest.TestCase):
    def test_parsing_ocr_schedule_lines(self):
        ocr_lines = [
            'Monday',
            '10:00AM-6:00PM[800]',
            '10:00AM-2:30PM[450]/StockPutaway',
            '2:30PM-3:00PM[050]Break',
            '3:00PM-6:00PM[300]/StockPutaway',
            '30Wednesday',
            '1:30PM-8:30PM[700]',
            '1:30PM-6:30PM[500]/StockPutaway',
            '6:30PM-7:00PM[050]Break',
            '7:00PM-8:30PM[150]/StockPutaway',
            '31Thursday',
            '1:30PM-8:30PM[700]',
            '1:30PM-6:30PM[500]/StockPutaway',
            '6:30PM-7:00PM[050]Break',
            '7:00PM-8:30PM[150]/StockPutaway',
        ]
        shifts = get_shifts_from_text(ocr_lines)
        self.assertEqual(len(shifts), 2)
        self.assertEqual(shifts[0].date, 30)
        self.assertEqual(shifts[0].start_hour, 13)
        self.assertEqual(shifts[0].start_minute, 30)
        self.assertEqual(shifts[0].end_hour, 20)
        self.assertEqual(shifts[0].end_minute, 30)
        self.assertEqual(shifts[0].role, 'StockPutaway')

        self.assertEqual(shifts[1].date, 31)
        self.assertEqual(shifts[1].role, 'StockPutaway')

    def test_bounds_safety_near_end_of_list(self):
        # A day appearing at the very end of list must not crash with IndexError
        ocr_lines = ['Friday']
        shifts = get_shifts_from_text(ocr_lines)
        self.assertEqual(shifts, [])


class TestGoogleHelpers(unittest.TestCase):
    def test_convert_to_rfc_datetime_custom(self):
        rfc = convert_to_RFC_datetime(2026, 9, 30, 13, 30)
        self.assertEqual(rfc, '2026-09-30T13:30:00Z')

    def test_convert_to_rfc_datetime_default(self):
        rfc = convert_to_RFC_datetime()
        self.assertEqual(rfc, '1900-01-01T00:00:00Z')

    def test_define_cell_range(self):
        cell_range = GoogleSheetsHelper.define_cell_range(
            sheet_id=0,
            start_row_number=1,
            end_row_number=10,
            start_column_number=1,
            end_column_number=5,
        )
        self.assertEqual(
            cell_range,
            {
                'sheetId': 0,
                'startRowIndex': 0,
                'endRowIndex': 10,
                'startColumnIndex': 0,
                'endColumnIndex': 5,
            },
        )

    def test_define_dimension_range(self):
        dim_range = GoogleSheetsHelper.define_dimension_range(
            sheet_id=0,
            dimension='ROWS',
            start_index=0,
            end_index=5,
        )
        self.assertEqual(
            dim_range,
            {
                'sheetId': 0,
                'dimension': 'ROWS',
                'startIndex': 0,
                'endIndex': 5,
            },
        )


class TestCalendarSync(unittest.TestCase):
    def test_build_event_body(self):
        shift = Shift(
            year=2026,
            month=9,
            date=30,
            start_hour=13,
            start_minute=30,
            end_hour=20,
            end_minute=30,
            role='StockPutaway',
        )
        body = build_event_body(shift, location='Test Location', timezone_offset='-04:00')
        self.assertEqual(body['summary'], 'Work')
        self.assertEqual(body['description'], 'StockPutaway')
        self.assertEqual(body['location'], 'Test Location')
        self.assertEqual(body['colorId'], 11)
        self.assertEqual(body['start']['dateTime'], '2026-09-30T13:30:00-04:00')
        self.assertEqual(body['end']['dateTime'], '2026-09-30T20:30:00-04:00')

    @patch('calendar_sync.get_shifts_from_text')
    def test_sync_shifts_to_calendar(self, mock_get_shifts):
        mock_shift = Shift(2026, 9, 30, 13, 30, 20, 30, 'StockPutaway')
        mock_get_shifts.return_value = [mock_shift]

        mock_service = MagicMock()
        mock_events = MagicMock()
        mock_insert = MagicMock()
        mock_service.events.return_value = mock_events
        mock_events.insert.return_value = mock_insert
        mock_insert.execute.return_value = {'id': 'evt_123', 'status': 'confirmed'}

        created = sync_shifts_to_calendar(calendar_service=mock_service, calendar_id='test_cal_id')
        self.assertEqual(len(created), 1)
        self.assertEqual(created[0]['id'], 'evt_123')
        mock_events.insert.assert_called_once()


if __name__ == '__main__':
    unittest.main()
