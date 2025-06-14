from flask_sqlalchemy import SQLAlchemy

# The database object maps Python objects to DB's tuples (ORM, object-relational mapping)
# This is a global object available to all sources. It is initialized in main.py
db = SQLAlchemy()
