""" Repositories section of the home page: the logged user manages their student repo. The page
asks for its state (GET /user/repo), starts the background jobs of repo_jobs.py
(POST /user/repo/<kind>), downloads their zips (GET /user/repo/<kind>.zip), and sets the remote
of the repo (POST /user/repo/origin). Every route answers only the logged user, from their own
folder """

import urllib.parse

import flask
from flask import current_app as app

from activity_log import log_event
from repos.git_repo import GitError
from repos.repo_jobs import BUSY, JOB_KINDS, ZIP_KINDS, RepoJob, RepoJobError
from repos.ssh_key import UserKey
from repos.student_repo import StudentRepo

# Names of the zips that the user downloads, by kind of job
ZIP_NAMES = { 'solutions': 'solutions.zip', 'history': '{repo}.zip' }

class RepoController:
    """ Routes of the student repo of the logged user """

    @staticmethod
    def get_state():
        """ Answer the state of the student repo of the logged user: its info, origin, public key,
        and the state of each job """
        username = RepoController.logged_user()
        repo = StudentRepo(username)
        try:
            info, origin = repo.info(), repo.origin()
        except (GitError, OSError, ValueError):
            app.logger.exception('could not read the student repo of %s', username)
            info, origin = None, ''
        try:
            public_key = UserKey(username).public_key()
        except OSError:
            app.logger.exception('could not make the SSH key of %s', username)
            public_key = ''
        return flask.jsonify({
            'info': info,
            'origin': origin,
            'publicKey': public_key,
            'originHosts': app.config['REPO_ORIGIN_HOSTS'],
            'retention': app.config['REPO_ZIP_RETENTION'],
            'jobs': { kind: RepoJob(username, kind).state() for kind in JOB_KINDS },
        }), 200, { 'Cache-Control': 'no-store' }

    @staticmethod
    def start_job(kind: str):
        """ Start the job of the kind for the logged user, and answer its state """
        username = RepoController.logged_user()
        if kind not in JOB_KINDS:
            flask.abort(404)
        job = RepoJob(username, kind)
        try:
            job.start()
        except RepoJobError as error:
            return flask.jsonify({ 'error': error.code }), 503 if error.code == BUSY else 409
        except OSError:
            app.logger.exception('could not start the repo job %s of %s', kind, username)
            return flask.jsonify({ 'error': 'failed' }), 500
        log_event('repo_job', { 'kind': kind })
        return flask.jsonify(job.state()), 202

    @staticmethod
    def download(kind: str):
        """ Send the zip made by the job of the kind for the logged user """
        username = RepoController.logged_user()
        if kind not in ZIP_KINDS:
            flask.abort(404)
        path = RepoJob(username, kind).zip_path()
        if not path:
            flask.abort(404)
        name = ZIP_NAMES[kind].format(repo=app.config['STUDENT_REPO_NAME'])
        response = flask.send_file(path, mimetype='application/zip', as_attachment=True,
            download_name=name)
        response.headers['Cache-Control'] = 'no-store'
        return response

    @staticmethod
    def set_origin():
        """ Set the remote of the student repo of the logged user to the URL of the JSON body
        ({"origin": url}), or remove it if the URL is empty, and answer the URL """
        username = RepoController.logged_user()
        body = flask.request.get_json(silent=True)
        url = body.get('origin') if isinstance(body, dict) else None
        if not isinstance(url, str):
            return flask.jsonify({ 'error': 'invalid_origin' }), 400
        try:
            url = StudentRepo(username).set_origin(url)
        except ValueError:
            return flask.jsonify({ 'error': 'invalid_origin' }), 400
        except (GitError, OSError):
            app.logger.exception('could not set the origin of %s', username)
            return flask.jsonify({ 'error': 'failed' }), 500
        # The host tells which services students use; the path of their repo is not logged
        log_event('repo_origin', { 'host': origin_host(url) })
        return flask.jsonify({ 'origin': url })

    @staticmethod
    def logged_user() -> str:
        """ Return the username of the logged user, or stop the request with 401 """
        user = flask.session.get('user')
        if not user:
            flask.abort(401)
        return user['email']

def origin_host(url: str) -> str:
    """ Return the host of an SSH URL (ssh://user@host/path or user@host:path), or an empty
    string for an empty URL """
    if url.startswith('ssh://'):
        return urllib.parse.urlsplit(url).hostname or ''
    return url.partition('@')[2].partition(':')[0]
