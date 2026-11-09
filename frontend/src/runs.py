""" Code runs of the users, kept to limit the abuse of the backends """
import datetime
import hashlib
import json

from db import db
from limits import Limits
from users import User

# Runs of a user that are counted to limit them
RUNS_WINDOW = datetime.timedelta(hours=1)
# Maximum runs of a user in RUNS_WINDOW. A student who runs the code every 30 seconds while fixing
# it stays below this limit
MAX_RUNS_PER_WINDOW = 120
# Minimum time between the starts of two runs of a user. Students take longer to fix their code
MIN_RUN_INTERVAL = datetime.timedelta(seconds=5)
# A run that has not finished this many seconds after the longest wait for a backend
# (Limits.max_backend_wait()) is not running anymore, e.g. the server stopped before storing its end
STALE_RUN_GRACE = 15
# Runs are deleted after this time. The result of the last run of each problem is kept until then
# to answer the same submission again without running it
RUNS_KEPT = datetime.timedelta(days=1)
# Larger results are not stored, so their submissions run again if repeated
MAX_STORED_RESULT = 2**20

def plural(count: int, noun: str) -> str:
    """ Return the count with the noun in singular or plural, e.g. '1 minute', '2 minutes' """
    return f'{count} {noun}' if count == 1 else f'{count} {noun}s'

class RunRejected(Exception):
    """ A run that a limit does not allow now. Its message is shown to the user """

    def __init__(self, message: str, retry_after: datetime.timedelta):
        """ Store the message, and the time to wait before running again """
        super().__init__(message)
        # Seconds to wait before running again, for the Retry-After header of HTTP
        self.retry_after = max(1, int(retry_after.total_seconds() + 0.999))

class Run(db.Model):
    """ A run of the code of a user against the test cases of a problem. Runs are stored in the
    database, so all the gunicorn workers share them to apply the limits """
    __tablename__ = 'runs'
    __table_args__ = (
        db.Index('runs_user_started', 'user_id', 'started'),
        db.Index('runs_user_problem', 'user_id', 'course', 'problem'),
    )
    # Runs are identified using incremental integer numbers
    id = db.Column(db.Integer, primary_key=True)
    # The user who ran the code
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    # Names of the course and the problem, as in vygoj.json, e.g. 'CI0112' and 'hello'
    course = db.Column(db.String(64), nullable=False)
    problem = db.Column(db.String(64), nullable=False)
    # SHA-256 of the language and the code, to recognize the same submission
    code_hash = db.Column(db.String(64), nullable=False)
    # When the run started, and when it finished (None while running)
    started = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    finished = db.Column(db.DateTime(timezone=True))
    # JSON of the execution result, only for the last run of the problem, if it is not too large
    result = db.Column(db.Text)

    @staticmethod
    def hash_code(problem_dict: dict, language: str, code: str) -> str:
        """ Return the hash that identifies a submission of the given code to the problem, as it is
        sent to the backend: its test cases, effective limits, and other fields that judge it, but
        not the statement, so fixing a typo does not make students run their code again. The code
        goes last, and the other parts have no null characters (JSON escapes them), so different
        submissions cannot have the same text to hash """
        # Sorted keys, so the same problem always gives the same text
        problem_json = json.dumps(problem_dict, sort_keys=True, separators=(',', ':'))
        text = f'{problem_json}\0{language}\0{code}'
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    @staticmethod
    def find_user_id(username: str):
        """ Return the id of the user with the given username, or None if it does not exist """
        return db.session.scalar(db.select(User.id).filter_by(username=username))

    @staticmethod
    def find_repeated(user_id: int, course: str, problem: str, code_hash: str):
        """ Return the stored result of the last run of the user in the problem if it was the same
        submission, or None. Running it again would give the same result """
        last = db.session.scalar(db.select(Run).filter_by(user_id=user_id, course=course,
            problem=problem).order_by(Run.started.desc()).limit(1))
        if last and last.code_hash == code_hash and last.finished and last.result:
            return last.result
        return None

    @staticmethod
    def start(user_id: int, course: str, problem: str, code_hash: str) -> 'Run':
        """ Store a new run of the user and return it, or raise RunRejected if a limit does not
        allow it now """
        # Lock the row of the user until the commit, so two requests of the same user sent at the
        # same time (e.g. by a robot) are checked one after the other, and both cannot pass
        db.session.execute(db.select(User.id).filter_by(id=user_id).with_for_update())
        now = datetime.datetime.now(datetime.timezone.utc)
        try:
            Run.check_limits(user_id, now)
        except RunRejected:
            db.session.rollback()
            raise
        # Only the result of the last run of a problem is needed. Old runs are not needed
        db.session.execute(db.update(Run).filter_by(user_id=user_id, course=course,
            problem=problem).values(result=None))
        db.session.execute(db.delete(Run).filter(Run.started < now - RUNS_KEPT))
        run = Run(user_id=user_id, course=course, problem=problem, code_hash=code_hash,
            started=now)
        db.session.add(run)
        db.session.commit()
        return run

    @staticmethod
    def check_limits(user_id: int, now: datetime.datetime):
        """ Raise RunRejected if the user cannot run code now """
        recent = db.select(Run).filter(Run.user_id == user_id, Run.started > now - RUNS_WINDOW)
        last = db.session.scalar(recent.order_by(Run.started.desc()).limit(1))
        max_duration = datetime.timedelta(seconds=Limits.max_backend_wait() + STALE_RUN_GRACE)
        if last and not last.finished and last.started > now - max_duration:
            # Most runs take a few seconds, so the client may try again soon
            raise RunRejected('Your previous run has not finished yet. Wait for its result.',
                MIN_RUN_INTERVAL)
        if last and last.started > now - MIN_RUN_INTERVAL:
            wait = last.started + MIN_RUN_INTERVAL - now
            raise RunRejected(f'Wait {plural(int(wait.total_seconds()) + 1, "second")} before '
                'running again.', wait)
        count = db.session.scalar(db.select(db.func.count()).select_from(recent.subquery()))
        if count >= MAX_RUNS_PER_WINDOW:
            oldest = db.session.scalar(db.select(db.func.min(Run.started)).filter(
                Run.user_id == user_id, Run.started > now - RUNS_WINDOW))
            wait = oldest + RUNS_WINDOW - now
            raise RunRejected(f'You reached {MAX_RUNS_PER_WINDOW} runs in an hour. Try again in '
                f'{plural(int(wait.total_seconds() // 60) + 1, "minute")}.', wait)

    def finish(self, result: str):
        """ Store the end of this run, and its result in JSON if it is not too large. The result
        is None if the run failed, e.g. the backend was not available """
        self.finished = datetime.datetime.now(datetime.timezone.utc)
        self.result = result if result and len(result) <= MAX_STORED_RESULT else None
        db.session.commit()
