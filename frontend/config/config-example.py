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
