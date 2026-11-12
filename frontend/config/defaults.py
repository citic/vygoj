# Default configuration of the frontend. The frontend loads this file, and then config/config.py
# (git-ignored), which only needs the settings of each server that differ from these: at least
# SECRET_KEY, and usually DATA_FOLDER and BACKENDS. A setting in config.py replaces the whole value
# of this file, e.g. a dictionary of defaults per language is not merged. Keep this file complete
# and valid: the code reads every setting from it without fallback values

# Data folder to store course repos, student code submissions
DATA_FOLDER = "/home/user/vygdata"
# TSV file in DATA_FOLDER with the users to add to the database (username and password columns)
USERS_FILE = "users-passwords.tsv"
# Name of the bare git repo with the solutions of each user, in their folder DATA_FOLDER/u<user_id>
PERSONAL_REPO_NAME = "personal_repo"
# Database URI for SQLAlchemy. Without user and password, PostgreSQL uses the system user
SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg:///vygoj'
# Frontend network port to listen on
PORT = 8080
# Backend server URIs, at least one. A random one will be selected for each code run request
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
# Secret key that signs the session cookies and the CSRF tokens. Anyone who knows it can log in as
# any user, so it must be set in config.py: the frontend refuses to start without it or with fewer
# than 32 characters. Generate one with: python3 -c 'import secrets; print(secrets.token_hex(32))'
SECRET_KEY = ''
# Number of reverse proxies (e.g. Apache, see readme.adoc) between clients and this server. Login
# limits and logs use the address of the client, which proxies send in X-Forwarded-For. Use 0 if
# clients connect directly, otherwise they could fake that header to avoid the limits
TRUSTED_PROXIES = 0
# Public address of this site, as users type it, e.g. 'https://vygoj.ucr.ac.cr', without a final
# slash. Single sign-on (SSO) providers send users back to its callback URLs, which must match the
# ones registered in the provider exactly. Empty takes the address of each request, which is enough
# for development, but behind a reverse proxy it may be http:// instead of https://
SITE_URL = ''
# Client secrets of the SSO providers, by the alias of each provider (the alias is chosen when an
# administrator adds the provider in /admin/users), e.g. {'ucr': 'the secret given by the SSO
# team'}. Secrets are credentials, so they are written here in the server, never in the database
# or in the web forms. A provider without secret is used as a public client, with PKCE only
SSO_CLIENT_SECRETS = {}
