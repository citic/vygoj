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
