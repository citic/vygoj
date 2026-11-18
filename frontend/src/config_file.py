""" Configuration files of course repos: the file in the root of a repo that lists its courses
(courses/course_config.py), and the file of each problem folder (problems/problem_config.py),
later of questions too. Each one may be written in JSON or YAML, with any of the names of
CONFIG_FILES. ConfigFile finds, reads, and parses them, and each subclass interprets the object of
its kind of file.

Repos are written by professors, so the files are untrusted: they are read only inside the repo
and up to MAX_SIZE, YAML is read without aliases nor custom tags, and both formats give only JSON
values (dicts, lists, strings, numbers, booleans, and None). Errors that skip a value are kept as
warnings, so the professor can be told """

import json
import os
import re
from abc import ABC as abstract, abstractmethod

import yaml

# Names of a configuration file, in the order they are searched. Only the first one found is read
CONFIG_FILES = ('vygoj.json', 'vygoj.yaml', 'info.json', 'info.yaml')

# Largest size of a configuration file in bytes. YAML is parsed in Python, so larger files would
# keep a server busy, and configuration is written by hand
MAX_SIZE = 1024 * 1024

# Integers that YAML 1.1 reads as octal (010) or base 60 (1:30), but people write as text, e.g.
# the number of a test case (004), which must match its file (input004.txt)
TEXT_INTEGER = re.compile(r'[-+]?(0[0-9_]+|[0-9][0-9_]*(:[0-5]?[0-9])+)')

class ConfigError(Exception):
    """ A configuration file that cannot be used, with the code of its message and its parameters,
    e.g. ('too_big', {'file': 'vygoj.yaml', 'size': 1048576}) """

    def __init__(self, code: str, **params):
        super().__init__(code)
        self.code = code
        self.params = params

class _SafeYamlLoader(yaml.SafeLoader): # pylint: disable=too-many-ancestors
    """ SafeLoader without aliases, whose nested references could expand a small file into a huge
    tree (billion laughs), with dates as plain strings, as JSON writes them, and integers of
    TEXT_INTEGER as strings, as YAML 1.2 reads them """

    def compose_node(self, parent, index):
        """ Reject aliases (*name) before composing their node """
        if self.check_event(yaml.AliasEvent):
            raise yaml.YAMLError('aliases are not allowed')
        return super().compose_node(parent, index)

    def construct_integer(self, node):
        """ Return the integer of the node, or its text if it matches TEXT_INTEGER """
        text = self.construct_scalar(node)
        if TEXT_INTEGER.fullmatch(text):
            return text
        return self.construct_yaml_int(node)

_SafeYamlLoader.add_constructor('tag:yaml.org,2002:timestamp',
    yaml.SafeLoader.construct_yaml_str)
_SafeYamlLoader.add_constructor('tag:yaml.org,2002:int', _SafeYamlLoader.construct_integer)

def is_inside(folder: str, path: str) -> bool:
    """ True if the path is the folder or is inside it. Symbolic links are resolved before
    comparing, so a link inside the folder that points out of it is out of it """
    root = os.path.realpath(folder)
    return os.path.commonpath([root, os.path.realpath(path)]) == root

def find(folder: str) -> str | None:
    """ Return the path of the first configuration file of the folder, or None if it has none.
    Symbolic links are not configuration files """
    for name in CONFIG_FILES:
        path = os.path.join(folder, name)
        if os.path.isfile(path) and not os.path.islink(path):
            return path
    return None

def parse(text: str, filename: str) -> dict:
    """ Return the JSON object of the text of a configuration file, in the format of the extension
    of its name. Raise ConfigError if it is not a valid object """
    try:
        if filename.endswith('.yaml'):
            value = yaml.load(text, Loader=_SafeYamlLoader)
            # Only JSON values: keys become strings, and other types (e.g. !!binary or !!set)
            # raise TypeError
            value = json.loads(json.dumps(value))
        else:
            value = json.loads(text)
    except (yaml.YAMLError, TypeError, ValueError, RecursionError) as error:
        # The error tells the line and column, but never a path of the server: it parsed a text
        raise ConfigError('invalid_file', file=filename, error=str(error)) from error
    if not isinstance(value, dict):
        raise ConfigError('not_object', file=filename)
    return value

class ConfigFile(abstract):
    """ A configuration file of a folder of a course repo. load() finds and reads the file, and
    gives its object to interpret(), which subclasses implement for their kind of file. Values that
    interpret() skips are kept in warnings """

    def __init__(self, root: str):
        """ root is the folder of the repo: files whose real path is out of it are not read """
        self.root = root
        # Name of the file found by load(), e.g. 'info.yaml', or '' if none
        self.filename = ''
        # Values skipped by interpret(), as (code, parameters), e.g.
        # ('invalid_field', {'file': 'info.yaml', 'field': 'maxDuration', 'kind': 'number'})
        self.warnings = []

    def load(self, folder: str):
        """ Return what interpret() makes of the configuration file of the folder, or None if the
        folder has none. Raise ConfigError if the file cannot be read or is not an object """
        path = find(folder)
        if path is None:
            return None
        self.filename = os.path.basename(path)
        return self.interpret(self.read(path))

    def read(self, path: str) -> dict:
        """ Return the object of the configuration file. Raise ConfigError if it is out of the
        repo, too big, or not a valid object """
        if not is_inside(self.root, path):
            raise ConfigError('outside_repo', file=self.filename)
        if os.path.getsize(path) > MAX_SIZE:
            raise ConfigError('too_big', file=self.filename, size=MAX_SIZE)
        try:
            with open(path, encoding='utf-8') as file:
                text = file.read()
        # The messages of OSError have the path of the file, which users must not see
        except OSError as error:
            raise ConfigError('invalid_file', file=self.filename, error=error.strerror) from error
        except UnicodeDecodeError as error:
            raise ConfigError('invalid_file', file=self.filename, error=str(error)) from error
        return parse(text, self.filename)

    def warn(self, code: str, **params):
        """ Keep a warning about a value of the file that was skipped """
        self.warnings.append((code, {'file': self.filename, **params}))

    @abstractmethod
    def interpret(self, data: dict):
        """ Return what this kind of configuration file means, made of its object """
