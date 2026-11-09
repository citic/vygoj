# Data folder to store course repos, student code submissions
DATA_FOLDER = "/home/user/vygdata"
# TSV file in DATA_FOLDER with the users to add to the database (username and password columns)
USERS_FILE = "users-passwords.tsv"
# Database URI for SQLAlchemy. Without user and password, PostgreSQL uses the system user
SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg:///vygoj'
# Frontend network port to listen on
PORT = 8080
# Backend server URIs. A random one will be selected for each code run request
BACKENDS = [ "http://localhost:9090" ]
# Limits of the code runs. Each one has an absolute range [ABS_MIN_*, ABS_MAX_*] for this judge, and
# a default DEF_* used when a problem does not choose a value. Professors may choose values in the
# range in vygoj.json (minDuration, maxDuration, maxTotalDuration, maxOutputSize); values out of
# the range are clamped. Defaults may be a number, or a dictionary with a number for each language
# (a language without entry gets the absolute bound). The backend receives the effective values
# Wall time in seconds of each test case (minDuration and maxDuration of problems and test cases).
# Interpreted and JVM languages start slower than compiled ones. A minDuration of 0 means no
# minimum. The wall time is measured in hundredths of a second, so use minimums of tenths
ABS_MIN_RUN_DURATION = 0
ABS_MAX_RUN_DURATION = 10
DEF_MIN_RUN_DURATION = 0
DEF_MAX_RUN_DURATION = {
    'C': 2, 'C++': 2,
    'Java': 4, 'JavaScript': 4, 'Kotlin': 4,
    'Alecci': 6, 'Python': 6,
}
# Seconds of a whole submission: compiling and running all its test cases one after the other
# (maxTotalDuration). Test cases that do not fit are not run. Students wait for the answer up to
# ABS_MAX_TOTAL_DURATION plus about 45 seconds, and a backend worker is busy meanwhile
ABS_MIN_TOTAL_DURATION = 0
ABS_MAX_TOTAL_DURATION = 60
DEF_MAX_TOTAL_DURATION = 30
# Bytes of the standard output and error of each visible test case, and of the compiler output,
# shown to students (maxOutputSize). Longer outputs end with "(truncated)". Outputs are compared
# complete, and the output of hidden test cases is never sent
ABS_MIN_OUTPUT_SIZE = 0
ABS_MAX_OUTPUT_SIZE = 10 * 1024
DEF_MAX_OUTPUT_SIZE = 10 * 1024
# Check status of backend servers every this amount of milliseconds
BACKEND_STATUS_INTERVAL = 60000
# Secret key that signs the session cookies and the CSRF tokens. Anyone who knows it can log in as
# any user, so the frontend refuses to start with this example value or with fewer than 32
# characters. Generate one with: python3 -c 'import secrets; print(secrets.token_hex(32))'
SECRET_KEY = 'A very large and random string that is hard to guess.'
# Number of reverse proxies (e.g. Apache, see readme.adoc) between clients and this server. Login
# limits and logs use the address of the client, which proxies send in X-Forwarded-For. Use 0 if
# clients connect directly, otherwise they could fake that header to avoid the limits
TRUSTED_PROXIES = 0
