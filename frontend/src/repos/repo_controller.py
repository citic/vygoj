""" Repositories section of the home page: the logged user manages their student repo, and
professors their professor repos too. The page asks for the state of the repos (GET /user/repo),
starts the background jobs of repo_jobs.py on the student repo (POST /user/repo/<kind>), downloads
their zips (GET /user/repo/<kind>.zip), and sets the remote of the student repo
(POST /user/repo/origin). Professors add a repo, which is cloned (POST /user/repo/professor), and
clone or pull one, after changing its URL if needed (POST /user/repo/professor/<id>). Every route
answers only the logged user, from their own folder """

import urllib.parse

import flask
from flask import current_app as app

from activity_log import log_event
from repos.git_repo import GitError
from repos.professor_repo import ProfessorRepo
from repos.repo_jobs import BUSY, PROFESSOR_KINDS, JOB_KINDS, ZIP_KINDS, RepoJob, RepoJobError
from repos.ssh_key import UserKey
from repos.student_repo import StudentRepo

# Names of the zips that the user downloads, by kind of job
ZIP_NAMES = { 'solutions': 'solutions.zip', 'history': '{repo}.zip' }

class RepoController:
    """ Routes of the repos of the logged user """

    @staticmethod
    def get_state():
        """ Answer the state of the repos of the logged user: the info, origin, and the state of
        each job of their student repo, their public key, and the repos of professors with the
        state of their jobs """
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
            'jobs': { kind: RepoJob(username, kind).state() for kind in JOB_KINDS
                if kind not in PROFESSOR_KINDS },
            'professorRepos': RepoController.professor_repos(username),
        }), 200, { 'Cache-Control': 'no-store' }

    @staticmethod
    def professor_repos(username: str) -> list | None:
        """ Return the professor repos of the logged user, with their id, URL, folder, whether
        they have a clone, and the state of their job, or None if the user is not a professor """
        if not is_professor():
            return None
        return [{
            'id': repo.id,
            'url': repo.url,
            'folder': repo.folder,
            'cloned': repo.clone().is_clone(),
            'job': RepoJob(username, 'pull', repo.id).state(),
        } for repo in ProfessorRepo.of_user(username)]

    @staticmethod
    def start_job(kind: str):
        """ Start the job of the kind for the logged user, and answer its state """
        username = RepoController.logged_user()
        if kind not in JOB_KINDS or kind in PROFESSOR_KINDS:
            flask.abort(404)
        return RepoController.start(RepoJob(username, kind))

    @staticmethod
    def start(job: RepoJob):
        """ Start the job, and answer its state """
        try:
            job.start()
        except RepoJobError as error:
            return flask.jsonify({ 'error': error.code }), 503 if error.code == BUSY else 409
        except OSError:
            app.logger.exception('could not start the repo job %s of %s', job.name, job.username)
            return flask.jsonify({ 'error': 'failed' }), 500
        log_event('repo_job', { 'kind': job.kind, **({ 'repo': job.repo_id } if job.repo_id
            else {}) })
        return flask.jsonify(job.state()), 202

    @staticmethod
    def add_professor_repo():
        """ Add a professor repo of the logged professor with the URL of the JSON body
        ({"url": url}), and start its clone. Answer its id, and the code of the error that did
        not let its clone start, if any: the repo is added anyway, and the page tries again """
        username = RepoController.logged_professor()
        try:
            repo = ProfessorRepo.add(username, RepoController.body_text('url'))
        except ValueError as error:
            return flask.jsonify({ 'error': str(error) }), 400
        # The host tells which services professors use; the path of their repo is not logged
        log_event('professor_repo', { 'repo': repo.id, 'host': origin_host(repo.url) })
        response, status = RepoController.start(RepoJob(username, 'pull', repo.id))
        error = response.get_json().get('error') if status >= 400 else None
        return flask.jsonify({ 'id': repo.id, **({ 'error': error } if error else {}) }), 201

    @staticmethod
    def pull_professor_repo(repo_id: int):
        """ Set the URL of the JSON body ({"url": url}) to the professor repo of the logged
        professor, if it changed, and start its clone, or its pull if it has a clone. Answer the
        state of its job """
        username = RepoController.logged_professor()
        repo = ProfessorRepo.find(username, repo_id)
        if not repo:
            flask.abort(404)
        url = RepoController.body_text('url')
        if url is None:
            return flask.jsonify({ 'error': 'invalid_url' }), 400
        url = url.strip()
        if url != repo.url:
            try:
                repo.set_url(url)
            except ValueError as error:
                return flask.jsonify({ 'error': str(error) }), 400
            log_event('professor_repo', { 'repo': repo.id, 'host': origin_host(repo.url) })
        return RepoController.start(RepoJob(username, 'pull', repo.id))

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
        url = RepoController.body_text('origin')
        if url is None:
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

    @staticmethod
    def logged_professor() -> str:
        """ Return the username of the logged user, or stop the request with 403 if they are not a
        professor """
        username = RepoController.logged_user()
        if not is_professor():
            flask.abort(403)
        return username

    @staticmethod
    def body_text(name: str) -> str | None:
        """ Return the text of the field of the JSON body of the request, or None if it is missing
        or not a text. The size of the body is bounded by MAX_CONTENT_LENGTH, and the validation of
        each field bounds the size of its text """
        body = flask.request.get_json(silent=True)
        text = body.get(name) if isinstance(body, dict) else None
        return text if isinstance(text, str) else None

def is_professor() -> bool:
    """ True if the logged user is a professor """
    return (flask.session.get('user') or {}).get('role') == 'professor'

def origin_host(url: str) -> str:
    """ Return the host of an SSH URL (ssh://user@host/path or user@host:path), or an empty
    string for an empty URL """
    if url.startswith('ssh://'):
        return urllib.parse.urlsplit(url).hostname or ''
    return url.partition('@')[2].partition(':')[0]
