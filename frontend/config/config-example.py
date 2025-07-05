# Database URI
DATABASE = "mongodb://user:pass@host/db?params"
# Frontend network port to listen on
PORT = 8080
# Backend server URIs. A random one will be selected for each code run request
BACKENDS = [ "http://ip.address:port" ]
# Check status of backend servers every this amount of milliseconds
BACKEND_STATUS_INTERVAL = 60000
# Secret encription key used by Flask-WTF extension to protect sessions against cross-site request
# forgery (CSRF) attacks
SECRET_KEY = 'A very large and random string that is hard to guess.'
