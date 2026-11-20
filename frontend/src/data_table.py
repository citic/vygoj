""" Tables of data that are searched, filtered, sorted, and split in pages in the server, with the
parameters of the URL of the page (GET), so links and reloads keep them, and the page works
without JavaScript:

    q       words of the search: free text, which any column may contain, and column:value
            filters, e.g. 'role:professor ann'. Case and accents are ignored
    sort    the column that sorts the rows, with a '-' before it to sort them in descending order
    pin     columns pinned as the first sort keys, in the order they were pinned, e.g. 'roles,-id'
    page    the number of the page, from 1
    size    rows per page, from 1 to MAX_PAGE_SIZE

Columns are found by their key or their header in the language of the interface, and only the
columns of the table are searched or sorted, so the query is always made by SQLAlchemy with bound
parameters. Templates show the controls with the macros of macros.html """

import math

import flask

from db import db

# Rows per page by default, and most rows per page that users may ask for, so a page is not slow
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 500
# Longest search and most words that a search may have, so a long query cannot make a slow one
MAX_QUERY_LENGTH = 200
MAX_WORDS = 10
# Letters with accents and their letters without them, to compare texts ignoring the accents in
# Python and in PostgreSQL (translate()), which needs no extension
ACCENTED = 'áàâäãéèêëíìîïóòôöõúùûüñç'
PLAIN = 'aaaaaeeeeiiiiooooouuuunc'
FOLD_TABLE = str.maketrans(ACCENTED, PLAIN)
# Parameters of the URL of a data table
PARAMS = ('q', 'sort', 'pin', 'page', 'size')

def request_params() -> dict:
    """ Return the parameters of a data table in the URL of the request, so the pages that its
    rows open (e.g. the actions on a user) go back to the same rows. Only these names are taken,
    so url_for() gets no other arguments """
    return { name: value for name in PARAMS if (value := flask.request.args.get(name)) }

def fold(text: str) -> str:
    """ Return the text in lowercase and without accents, to compare it with fold_sql() """
    return text.lower().translate(FOLD_TABLE)

def fold_sql(expression):
    """ Return the SQL expression of a text in lowercase and without accents """
    return db.func.translate(db.func.lower(expression), ACCENTED, PLAIN)

def text_match(expression):
    """ Return the match function of a column of text: its value contains the text """
    return lambda text: fold_sql(expression).contains(text, autoescape=True)

def choice_match(choices: dict, condition):
    """ Return the match function of a column with a fixed set of values, as {value: name}: the
    values whose stored value or name contains the text are given to condition(), which returns
    the SQL condition of the rows that have any of them """
    def match(text: str):
        values = [value for value, name in choices.items()
            if text in fold(value) or text in fold(str(name))]
        return condition(values) if values else db.false()
    return match

class Column:
    """ A column of a data table """

    def __init__(self, key: str, label, sort=None, match=None):
        # Name of the column in the URL and in filters, e.g. 'username'
        self.key = key
        # Header of the column, translated (a lazy string)
        self.label = label
        # SQL expression that sorts the rows by this column, or None if it is not sorted
        self.sort = sort
        # Function that returns the SQL condition of the rows whose value contains a folded text,
        # or None if the column is not searched
        self.match = match

    def is_named(self, name: str) -> bool:
        """ True if the folded name starts its key or its header without spaces, so 'rol' and
        'role' find the column roles, whose header is Roles """
        return any(fold(text).replace(' ', '').startswith(name)
            for text in (self.key, str(self.label)))

class DataTable:
    """ The page of rows of a SELECT that the parameters of the request ask for """
    # Most rows per page that the controls accept
    max_size = MAX_PAGE_SIZE

    def __init__(self, select, columns: list, endpoint: str, default_sort: str):
        """ Run the select with the search, sort, and page of the request. endpoint is the route
        of the page, which the links of the controls go to. default_sort sorts the rows that the
        other keys leave tied, e.g. '-id', the newest first """
        args = flask.request.args
        self.columns = { column.key: column for column in columns }
        self.endpoint = endpoint
        self.query = args.get('q', '')[:MAX_QUERY_LENGTH].strip()
        # Numbers that are not valid, or too long for int(), are None. Others are kept in range,
        # also 0, which shows one row
        size = args.get('size', type=int)
        self.size = min(max(size, 1), MAX_PAGE_SIZE) if size is not None else DEFAULT_PAGE_SIZE
        self.pins = self.parse_keys(args.get('pin', ''))
        self.default_sort = self.parse_keys(default_sort)[0]
        self.sort = (self.parse_keys(args.get('sort', '')) or [self.default_sort])[0]
        select = select.where(*self.conditions())
        self.total = db.session.scalar(db.select(db.func.count()).select_from(select.subquery()))
        self.pages = max(1, math.ceil(self.total / self.size))
        self.page = max(1, min(args.get('page', 1, type=int), self.pages))
        self.rows = db.session.scalars(select.order_by(*self.order())
            .limit(self.size).offset((self.page - 1) * self.size)).all()

    def parse_keys(self, text: str) -> list:
        """ Return the sort keys of a parameter, as [(key, descending)], without the keys of
        columns that are not sorted, nor repeated ones """
        keys = []
        for part in text.split(',')[:len(self.columns)]:
            key = part.removeprefix('-')
            column = self.columns.get(key)
            if column and column.sort is not None and key not in dict(keys):
                keys.append((key, part.startswith('-')))
        return keys

    def conditions(self) -> list:
        """ Return the SQL conditions of the words of the search: a column:value filter matches
        that column, and other words match any column """
        conditions = []
        for word in fold(self.query).split()[:MAX_WORDS]:
            name, colon, value = word.partition(':')
            column = next((column for column in self.columns.values()
                if name and colon and column.match and column.is_named(name)), None)
            if column:
                if value:
                    conditions.append(column.match(value))
            else:
                conditions.append(db.or_(*(column.match(word)
                    for column in self.columns.values() if column.match)))
        return conditions

    def keys(self) -> list:
        """ Return the keys that sort the rows: the pinned ones, then the sort key, then the
        default one """
        keys = list(self.pins)
        for key in (self.sort, self.default_sort):
            if key[0] not in dict(keys):
                keys.append(key)
        return keys

    def order(self) -> list:
        """ Return the SQL expressions of the order of the rows """
        return [self.columns[key].sort.desc() if descending else self.columns[key].sort.asc()
            for key, descending in self.keys()]

    def direction(self, key: str) -> str | None:
        """ Return 'ascending' or 'descending' if the column sorts the rows, or None """
        keys = dict(self.keys()[:len(self.pins) + 1])
        if key not in keys:
            return None
        return 'descending' if keys[key] else 'ascending'

    def pin_number(self, key: str) -> int | None:
        """ Return the position of the column among the pinned ones, from 1, or None """
        return next((number for number, (pinned, _) in enumerate(self.pins, 1)
            if pinned == key), None)

    def url(self, **changes) -> str:
        """ Return the URL of the page with the parameters of the request and the changes. Empty
        and default values are left out, and the page is kept only if it is a change, so other
        changes go back to the first page """
        params = { 'q': self.query, **self.kept_params(), 'size': self.size, **changes }
        if params['size'] == DEFAULT_PAGE_SIZE:
            params['size'] = ''
        if params.get('page') == 1:
            params['page'] = ''
        return flask.url_for(self.endpoint, **{ name: value for name, value in params.items()
            if value })

    def kept_params(self) -> dict:
        """ Return the sort and pins of the URL that are not the default ones, which the search
        form sends again """
        params = { 'sort': join_keys([self.sort]), 'pin': join_keys(self.pins) }
        if params['sort'] == join_keys([self.default_sort]):
            params['sort'] = ''
        return { name: value for name, value in params.items() if value }

    def sort_url(self, key: str) -> str:
        """ Return the URL that sorts by the column, or reverses it if it sorts the rows. A
        pinned column reverses its direction among the pins """
        if self.pin_number(key):
            return self.url(pin=join_keys([(pinned, descending != (pinned == key))
                for pinned, descending in self.pins]))
        descending = self.sort == (key, False)
        return self.url(sort=join_keys([(key, descending)]))

    def pin_url(self, key: str) -> str:
        """ Return the URL that pins the column, in the direction that it sorts the rows, or
        unpins it """
        if self.pin_number(key):
            return self.url(pin=join_keys([pin for pin in self.pins if pin[0] != key]))
        return self.url(pin=join_keys([*self.pins, (key, self.direction(key) == 'descending')]))

def join_keys(keys: list) -> str:
    """ Return the parameter of the sort keys, e.g. 'roles,-id' """
    return ','.join(('-' if descending else '') + key for key, descending in keys)
