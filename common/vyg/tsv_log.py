""" Logs of events written as TSV files, which statistical software reads as tables """
import datetime
import glob
import json
import logging
import os
import secrets
import tempfile

from vyg.constants import EXTENSION_LANGUAGES

logger = logging.getLogger(__name__)

# Text cells longer than this are truncated, so a client cannot write large rows (e.g. a long URL)
MAX_CELL_LENGTH = 256
# The data of an event is made by the server, but a problem with many test cases makes it long. A
# longer data is replaced by an error, so a row is always written with a single system call
MAX_DATA_LENGTH = 2**16
# Spreadsheets run the cells that start with these characters as formulas. A username typed in the
# login could be a formula, so these cells start with an apostrophe, as spreadsheets expect
FORMULA_STARTS = ('=', '+', '-', '@')
# Subfolder of the log with the code of the runs
CODE_FOLDER = 'code'

class TsvLog:
    """ A log of events in a folder: a TSV file per month (<prefix>-2026-11.tsv, UTC) whose first
    row names the columns, and a subfolder with code files named by their hash. Rows have fixed
    columns, and a data column with the other fields of each event as JSON, so new kinds of events
    add fields, not columns. Cells never contain tabs or new lines, so each event is one row.
    Several processes (e.g. gunicorn workers) may write the same log: each row is appended in a
    single system call, and the file of a new month is created with its columns atomically. Files
    are readable only by the user of the server, because they have personal data """

    def __init__(self, folder: str, columns: tuple, prefix: str = 'events'):
        """ A log in the given folder, with the given columns, and files named by the prefix """
        self.folder = folder
        self.columns = columns
        self.prefix = prefix

    # Writing --------------------------------------------------------------------------------------

    def write(self, row: dict):
        """ Append the row, a dictionary of cells named by the columns. The time and id are filled
        unless given, and the data dictionary is written as JSON. A failure to write is logged, it
        never stops the server """
        row = { **row, 'data': TsvLog.format_data(row.get('data')) }
        row['time'] = row.get('time') or TsvLog.now()
        row['id'] = row.get('id') or TsvLog.new_id()
        line = '\t'.join(TsvLog.format_cell(row.get(column), column)
            for column in self.columns) + '\n'
        try:
            self._append_line(self._month_path(), line)
        except OSError:
            logger.exception('could not write the %s event in the log %s', row.get('event'),
                self.folder)

    def save_code(self, code_hash: str, language: str, code: str):
        """ Save the code in the file named by its hash in the code folder, unless it was saved
        before (the same submission). The hash must be hexadecimal, made by the server. A failure
        to write is logged, it never stops the run """
        path = self.code_path(code_hash, language)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            # O_EXCL fails if the file exists: two users may send the same code at the same time
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
                file.write(code)
        except FileExistsError:
            pass
        except OSError:
            logger.exception('could not save the code %s in the log %s', code_hash, self.folder)

    def code_path(self, code_hash: str, language: str) -> str:
        """ Return the path of the code file of the given hash, with the extension of the
        language. The hash is hexadecimal, made by the server, so it is a safe file name """
        extension = EXTENSION_LANGUAGES.get(language, 'txt')
        return os.path.join(self.folder, CODE_FOLDER, f'{code_hash}.{extension}')

    def _month_path(self) -> str:
        """ Return the file of the current month, created with the row of columns if it does not
        exist. Each month has its own file, so no file grows forever, and analyses may load only
        the months they need """
        month = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m')
        path = os.path.join(self.folder, f'{self.prefix}-{month}.tsv')
        if not os.path.exists(path):
            self._create_file(path, '\t'.join(self.columns) + '\n')
        return path

    def _create_file(self, path: str, header: str):
        """ Create the file with the header, unless it exists. Several processes may create it at
        the same time, so the header is written in a temporary file (made by mkstemp, readable
        only by its user) and linked to the path, which fails if another process linked it first.
        The file never has two headers or rows before it """
        os.makedirs(self.folder, exist_ok=True)
        descriptor, temporary_path = tempfile.mkstemp(dir=self.folder, prefix=f'.{self.prefix}-')
        try:
            with os.fdopen(descriptor, 'w', encoding='utf-8') as file:
                file.write(header)
            os.link(temporary_path, path)
        except FileExistsError:
            pass
        finally:
            os.remove(temporary_path)

    @staticmethod
    def _append_line(path: str, line: str):
        """ Append the line to the file in a single system call. The file is opened in append mode,
        so the lines of several processes do not overwrite or split each other """
        descriptor = os.open(path, os.O_WRONLY | os.O_APPEND)
        try:
            os.write(descriptor, line.encode('utf-8'))
        finally:
            os.close(descriptor)

    # Reading --------------------------------------------------------------------------------------

    def read(self):
        """ Yield each event of the log as a dictionary of its cells, in order of time, with its
        data parsed. Rows that do not have the columns of the log are skipped """
        for path in sorted(glob.glob(os.path.join(self.folder, f'{self.prefix}-*.tsv'))):
            with open(path, encoding='utf-8') as file:
                next(file, None)
                for line in file:
                    cells = line.rstrip('\n').split('\t')
                    if len(cells) != len(self.columns):
                        continue
                    event = dict(zip(self.columns, map(TsvLog.parse_cell, cells)))
                    event['data'] = TsvLog.parse_data(event.get('data'))
                    yield event

    # Cells ----------------------------------------------------------------------------------------

    @staticmethod
    def now() -> str:
        """ Return the current time in UTC, ISO 8601 with milliseconds, as the time column """
        return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds')

    @staticmethod
    def new_id() -> str:
        """ Return a random identifier for an event, to join the tables of the logs """
        return secrets.token_hex(6)

    @staticmethod
    def format_cell(value, column: str = '') -> str:
        """ Return the value as a TSV cell: tabs, new lines, and other control characters become
        spaces, so each event is one row even if a client sent them, and long texts are truncated,
        except the data column, which is JSON made by format_data() """
        if value is None:
            return ''
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        text = ''.join(' ' if ord(char) < 32 or ord(char) == 127 else char for char in str(value))
        if column != 'data':
            text = text[:MAX_CELL_LENGTH]
        return "'" + text if text.startswith(FORMULA_STARTS) else text

    @staticmethod
    def parse_cell(cell: str) -> str:
        """ Return the text of a cell written by format_cell(), without the apostrophe that
        protects formulas """
        return cell[1:] if cell.startswith("'") and cell[1:].startswith(FORMULA_STARTS) else cell

    @staticmethod
    def format_data(data: dict):
        """ Return the data of an event as compact JSON, or None if there is no data. JSON escapes
        tabs and new lines, so the data fits in a cell """
        if not data:
            return None
        text = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        if len(text) > MAX_DATA_LENGTH:
            logger.warning('data of an event too long for the log: %d characters', len(text))
            return json.dumps({ 'error': 'data too long' })
        return text

    @staticmethod
    def parse_data(cell: str) -> dict:
        """ Return the JSON object of a data cell, or an empty one if it is empty or not valid """
        try:
            data = json.loads(cell) if cell else {}
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}
