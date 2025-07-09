import time
import flask
import os
import vyg

LOG_FILE = os.path.join(vyg.get_app_path(), 'data', 'vyg.tsv')

def log_event2(fields):
    '''' Log an entry '''
    timestamp = time.strftime('%y%m%d\t%H%M%S')
    user_obj = flask.session.get('user')
    username = user_obj.get('email', '') if user_obj else ''
    request = flask.request
    # date time ip scheme url status_code user body fields
    with open(LOG_FILE, 'a', encoding='utf8') as log_file:
        log_file.write(f'{timestamp}\t{request.remote_addr}\t{request.method}\t'
            f'{request.url}\t{username}\t{fields}\n')

def vyg_log(action, value=None):
    """ Log an info event with the given fields """
    text = ''
    if value is not None:
        if isinstance(value, str):
            text = value.replace('\n', '\\n').replace('\t', '\\t')
        elif isinstance(value, dict):
            text = vyg.to_json(value).replace('\n', '\\n').replace('\t', '\\t')
    info = action
    if text:
        info += '\t' + text
    log_event2(info)
