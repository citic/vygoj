""" Start backend execution """
from flask import Flask #, request, Response, redirect
app = Flask(__name__)

@app.route('/')
def index():
    """ Homepage provide help """
    return '<p>Help</p>'
