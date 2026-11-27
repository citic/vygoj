""" Constants and enumerations shared by the VygOJ data model """
import enum


class Status(str, enum.Enum):
    """ Status of the execution of a programming solution.
    The str inheritance eases the translation to and from JSON """
    PENDING = 'pending'
    PASSED = 'passed'
    WRONG = 'wrong'
    TIMEOUT = 'timeout'
    COMPILER_ERROR = 'compilerError'
    RUNTIME_ERROR = 'runtimeError'
    INTERNAL_ERROR = 'internalError'

# Maximum number of allowed execution threads to be created by a user solution
MAX_THREADS = 2**15

# Map file extensions to supported programming languages
LANGUAGE_EXTENSIONS = {
    'ale': 'Alecci',
    'c': 'C',
    'cpp': 'C++',
    'java': 'Java',
    'js': 'JavaScript',
    'kt': 'Kotlin',
    'py': 'Python',
}

# Create the inverse dictionary mapping languages to their extensions
EXTENSION_LANGUAGES = {value: key for key, value in LANGUAGE_EXTENSIONS.items()}

# Extensions of the files that students may add to the main file of a solution in each language,
# which the backend names (e.g. solution.c). The compiler of Alecci takes one file only. Languages
# do not share extensions, so the student repo tells apart the files of each language in a folder
SOLUTION_EXTENSIONS = {
    'Alecci': (),
    'C': ('c', 'h'),
    'C++': ('cpp', 'hpp'),
    'Java': ('java',),
    'Python': ('py',),
}
# Most files of a solution, and most bytes of all of them in UTF-8
MAX_SOLUTION_FILES = 32
MAX_SOLUTION_BYTES = 256 * 1024

# Map the extension or the lowercase name of each language to its name, e.g. 'cpp' and 'c++' to
# 'C++', because vygoj.json files are written by hand
LANGUAGE_NAMES = {key: name for extension, name in LANGUAGE_EXTENSIONS.items()
    for key in (extension, name.lower())}
