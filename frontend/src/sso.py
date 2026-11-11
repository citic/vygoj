""" Single sign-on (SSO): users log in with an OpenID Connect (OIDC) provider, such as the one of
a university, instead of a password of VygOJ. Administrators add the providers in /admin/users,
and their client secrets are written in config.py (SSO_CLIENT_SECRETS). Authlib does the protocol:
discovery, Authorization Code Flow with PKCE, state, nonce, and the validation of the ID token
(signature with the keys of the provider, issuer, audience, and expiration) """
import re
import time
import urllib.parse

import flask
from flask import current_app as app
import flask_wtf
from flask_babel import gettext, lazy_gettext
import wtforms
from wtforms import validators
import requests
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from authlib.common.errors import AuthlibBaseError
from authlib.integrations.flask_client import FlaskIntegration, FlaskOAuth2App
from joserfc.errors import JoseError

from db import db
from activity_log import log_event
from users import MAX_USERNAME_LENGTH, User, is_admin, safe_next_url, start_session

# Aliases of providers name them in URLs (/login/sso/ucr) and in SSO_CLIENT_SECRETS
ALIAS_PATTERN = re.compile(r'[a-z0-9][a-z0-9-]{0,31}')
# Names of claims, or paths to claims nested in objects, e.g. realm_access.roles of Keycloak
CLAIM_PATTERN = re.compile(r'[A-Za-z_][\w-]{0,63}(\.[A-Za-z_][\w-]{0,63}){0,3}')
# Scopes requested to providers, separated by spaces. openid is required by OIDC
SCOPE_PATTERN = re.compile(r'[\w:./-]+')
# Path of the discovery document of OIDC, added to issuer URLs that lack it
DISCOVERY_PATH = '/.well-known/openid-configuration'
# Seconds to connect to a provider and to wait for its answer (discovery, keys, and tokens)
PROVIDER_TIMEOUT = (5, 10)
# Seconds that the discovery document and the keys of a provider are reused before downloading
# them again. Authlib also downloads the keys again when a token is signed with a new key
METADATA_TTL = 6 * 60 * 60

# States of a provider: disabled ones do not work, testing ones work only for who knows their
# login URL (a controlled test in production), and active ones are offered in the login page
STATUSES = {
    'disabled': lazy_gettext('Disabled'),
    'testing': lazy_gettext('Testing'),
    'active': lazy_gettext('Active'),
}

# Prefix of the names of the clients, and of the data that Authlib keeps in the session for them
CLIENT_PREFIX = 'sso_'
STATE_PREFIX = f'_state_{CLIENT_PREFIX}'

# Errors of a login with a provider: protocol, invalid tokens, network, and invalid answers
LOGIN_ERRORS = (AuthlibBaseError, JoseError, requests.exceptions.RequestException, ValueError,
    RuntimeError)

# Models ------------------------------------------------------------------------------------------

class SsoProvider(db.Model):
    """ An OpenID Connect provider that users may log in with, configured by administrators """
    __tablename__ = 'sso_providers'
    # Providers are identified using incremental integer numbers
    id = db.Column(db.Integer, primary_key=True)
    # Short name for URLs and SSO_CLIENT_SECRETS, e.g. 'ucr'. It cannot change, because it is in
    # the callback URL registered in the provider
    alias = db.Column(db.String(32), unique=True, nullable=False)
    # Name shown in the login button, e.g. 'Universidad de Costa Rica'
    name = db.Column(db.String(64), nullable=False)
    # One of STATUSES
    status = db.Column(db.String(8), nullable=False, default='disabled')
    # URL of the discovery document of the provider (.well-known/openid-configuration)
    discovery_url = db.Column(db.String(512), nullable=False)
    # Client ID given by the team of the provider. The secret is in SSO_CLIENT_SECRETS
    client_id = db.Column(db.String(256), nullable=False)
    # Scopes requested, separated by spaces
    scopes = db.Column(db.String(256), nullable=False, default='openid profile email')
    # Claim with the email of the user, which is their username (some providers send 'mail')
    email_claim = db.Column(db.String(256), nullable=False, default='email')
    # True if the emails of the provider are trusted even without email_verified, e.g. an
    # institution that assigns them. Only verified emails link existing accounts or create new ones
    trust_emails = db.Column(db.Boolean, nullable=False, default=False)
    # True if users without an account in VygOJ get one (as students or professors) at their first
    # login, otherwise only existing users may log in with the provider
    allow_new_users = db.Column(db.Boolean, nullable=False, default=False)
    # Claim that tells professors from students, e.g. 'groups', and its values that mean professor,
    # separated by commas. New users are students if it is empty or has none of those values
    professor_claim = db.Column(db.String(256), nullable=False, default='')
    professor_values = db.Column(db.String(512), nullable=False, default='')

    def __repr__(self):
        """ Readable string representation for debugging/testing """
        return f'<SsoProvider {self.alias}>'

    @staticmethod
    def find(alias: str, usable: bool = False) -> 'SsoProvider | None':
        """ Return the provider of the given alias, or None. If usable, disabled ones are None """
        if not isinstance(alias, str) or not ALIAS_PATTERN.fullmatch(alias):
            return None
        provider = db.session.scalar(db.select(SsoProvider).filter_by(alias=alias))
        return None if usable and provider and provider.status == 'disabled' else provider

    @staticmethod
    def listed() -> list:
        """ Return the providers offered in the login page, by name """
        return db.session.scalars(db.select(SsoProvider).filter_by(status='active')
            .order_by(SsoProvider.name)).all()

    def secret(self) -> str | None:
        """ Return the client secret of this provider in config.py, or None """
        secret = app.config['SSO_CLIENT_SECRETS'].get(self.alias)
        return secret if isinstance(secret, str) and secret else None

    def infer_role(self, claims: dict) -> str:
        """ Return the role of a new user with the given claims: professor if the professor claim
        has one of the professor values, otherwise student. Never admin """
        professor_values = {value.strip() for value in self.professor_values.split(',')} - {''}
        if not self.professor_claim or not professor_values:
            return 'student'
        value = claim(claims, self.professor_claim)
        values = value if isinstance(value, list) else [value]
        is_professor = any(isinstance(item, str) and item in professor_values for item in values)
        return 'professor' if is_professor else 'student'

class UserIdentity(db.Model):
    """ An account of a user in a provider: the issuer and subject (sub) of its ID tokens, which
    OpenID Connect guarantees unique and stable, unlike emails and usernames """
    __tablename__ = 'user_identities'
    __table_args__ = (db.UniqueConstraint('issuer', 'subject'),)
    # Identities are identified using incremental integer numbers
    id = db.Column(db.Integer, primary_key=True)
    # The user of VygOJ of this identity. Deleting the user deletes their identities
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
        nullable=False, index=True)
    # Alias of the provider that linked the identity, shown to administrators
    provider = db.Column(db.String(32), nullable=False)
    # Issuer (iss) and subject (sub) of the ID tokens of the user
    issuer = db.Column(db.String(512), nullable=False)
    subject = db.Column(db.String(256), nullable=False)
    # Access the identities of a user from the User model
    user = db.relationship('User', backref=db.backref('identities', passive_deletes=True))

def claim(claims: dict, path: str):
    """ Return the claim of the given name, or path of names nested in objects, or None """
    value = claims
    for name in path.split('.'):
        if not isinstance(value, dict):
            return None
        value = value.get(name)
    return value

# OpenID Connect client ---------------------------------------------------------------------------

# Clients of the providers, reused while their configuration does not change, so the discovery
# document and keys are downloaded once in a while: {alias: (configuration, time, client)}. Each
# gunicorn worker has its own copy
_clients = {}

def oidc_client(provider: SsoProvider) -> FlaskOAuth2App:
    """ Return the Authlib client of the given provider """
    secret = provider.secret()
    configuration = (provider.discovery_url, provider.client_id, secret, provider.scopes)
    cached = _clients.get(provider.alias)
    if cached and cached[0] == configuration and time.monotonic() - cached[1] < METADATA_TTL:
        return cached[2]
    client_kwargs = {
        'scope': provider.scopes,
        'code_challenge_method': 'S256',
        'default_timeout': PROVIDER_TIMEOUT,
    }
    # Public clients have no secret, PKCE alone proves that the code is theirs
    if not secret:
        client_kwargs['token_endpoint_auth_method'] = 'none'
    name = CLIENT_PREFIX + provider.alias
    client = FlaskOAuth2App(FlaskIntegration(name), name=name, client_id=provider.client_id,
        client_secret=secret, server_metadata_url=provider.discovery_url,
        client_kwargs=client_kwargs)
    _clients[provider.alias] = (configuration, time.monotonic(), client)
    return client

def site_url_for(endpoint: str, **values) -> str:
    """ Return the full URL of the given endpoint in SITE_URL, or in the address of the request
    if SITE_URL is empty. Callback URLs must match the ones registered in the provider """
    site_url = app.config['SITE_URL']
    if site_url:
        return site_url.rstrip('/') + flask.url_for(endpoint, **values)
    return flask.url_for(endpoint, _external=True, **values)

# Login -------------------------------------------------------------------------------------------

class SsoLoginError(Exception):
    """ A user authenticated by a provider cannot log in VygOJ. The message is shown to the user,
    and the reason is logged """
    def __init__(self, message: str, reason: str):
        super().__init__(message)
        self.message = message
        self.reason = reason

class SsoController:
    """ Logs users in with single sign-on providers """

    @staticmethod
    def start(alias: str):
        """ Send the user to the login page of the provider, to come back to the callback. Only
        GET: a redirect after a form POST would break the form-action rule of the CSP """
        provider = SsoProvider.find(alias, usable=True)
        if not provider:
            flask.abort(404)
        next_url = safe_next_url(flask.request.args.get('next'))
        # Authlib keeps the state, nonce, and PKCE verifier of each login in the session cookie
        # for an hour. Only the last login is kept, so abandoned ones do not make it grow
        for name in [name for name in flask.session if name.startswith(STATE_PREFIX)]:
            flask.session.pop(name)
        try:
            response = oidc_client(provider).authorize_redirect(
                site_url_for('sso_callback', alias=provider.alias))
        except LOGIN_ERRORS:
            app.logger.exception('could not start the login with provider %s', provider.alias)
            return SsoController.fail(provider, 'provider not available', gettext(
                'Could not connect with %(provider)s. Try again later.', provider=provider.name))
        flask.session['sso_next'] = next_url
        return response

    @staticmethod
    def callback(alias: str):
        """ The provider sent the user back: get the ID token and log in its user """
        provider = SsoProvider.find(alias, usable=True)
        if not provider:
            flask.abort(404)
        next_url = safe_next_url(flask.session.pop('sso_next', None))
        try:
            token = oidc_client(provider).authorize_access_token()
            claims = token.get('userinfo')
            if not claims:
                raise ValueError('the provider sent no ID token')
            db_user = SsoController.find_user(provider, claims)
        except SsoLoginError as error:
            return SsoController.fail(provider, error.reason, error.message)
        except LOGIN_ERRORS as error:
            # The user pressed cancel in the login page of the provider
            if isinstance(error, AuthlibBaseError) and error.error == 'access_denied':
                return SsoController.fail(provider, 'cancelled', gettext('Login cancelled.'))
            app.logger.exception('could not log in with provider %s', provider.alias)
            return SsoController.fail(provider, 'invalid answer', gettext(
                'Could not log in with %(provider)s. Try again later.', provider=provider.name))
        return start_session(db_user, next_url, provider.alias)

    @staticmethod
    def fail(provider: SsoProvider, reason: str, message: str):
        """ Log the failed login, and go back to the login page with the given message """
        log_event('login_failed', { 'provider': provider.alias, 'reason': reason }, role=None)
        flask.flash(message, 'error')
        return flask.redirect(flask.url_for('user'))

    @staticmethod
    def find_user(provider: SsoProvider, claims: dict) -> User:
        """ Return the user of the given claims of the ID token: the one linked to its identity,
        or else the one with its email, which is linked, or else a new one if the provider allows
        it. Raise SsoLoginError if the user cannot log in """
        issuer, subject = claims.get('iss'), claims.get('sub')
        if not (isinstance(issuer, str) and 0 < len(issuer) <= 512
                and isinstance(subject, str) and 0 < len(subject) <= 256):
            raise ValueError('invalid issuer or subject in the ID token')
        identity = db.session.scalar(db.select(UserIdentity)
            .filter_by(issuer=issuer, subject=subject))
        if identity:
            return identity.user
        email = SsoController.verified_email(provider, claims)
        # Usernames of existing users are often their emails too
        db_user = db.session.scalar(db.select(User).filter(db.or_(
            db.func.lower(User.username) == email, db.func.lower(User.email) == email)))
        if db_user and db_user.role == 'admin':
            # Administrators can do everything, an account of a provider must not take theirs
            raise SsoLoginError(gettext('Administrators log in with their password.'),
                'administrator')
        if not db_user and not provider.allow_new_users:
            raise SsoLoginError(gettext('Your account of %(provider)s is not registered in '
                'VygOJ. Ask your professor.', provider=provider.name), 'not registered')
        created = not db_user
        if created:
            db_user = User(username=email, email=email, fullname=full_name(claims, email),
                role=provider.infer_role(claims))
            db.session.add(db_user)
        db.session.add(UserIdentity(user=db_user, provider=provider.alias, issuer=issuer,
            subject=subject))
        try:
            db.session.commit()
        except IntegrityError as error:
            # Another login of the same user created it at the same time
            db.session.rollback()
            raise SsoLoginError(gettext('Could not log in with %(provider)s. Try again.',
                provider=provider.name), 'concurrent login') from error
        if created:
            log_event('user_create', { 'source': 'sso', 'provider': provider.alias },
                user=db_user.username, role=db_user.role)
        return db_user

    @staticmethod
    def verified_email(provider: SsoProvider, claims: dict) -> str:
        """ Return the email of the given claims in lowercase, if it is valid and the provider
        verified it. Raise SsoLoginError otherwise, because an unverified email could take the
        account of its owner """
        email = claim(claims, provider.email_claim)
        email = email.strip().lower() if isinstance(email, str) else ''
        if not 3 <= len(email) <= MAX_USERNAME_LENGTH or '@' not in email:
            raise SsoLoginError(gettext('%(provider)s did not send your email. Ask the '
                'administrator.', provider=provider.name), 'no email')
        if claims.get('email_verified') is not True and not provider.trust_emails:
            raise SsoLoginError(gettext('Your email is not verified by %(provider)s.',
                provider=provider.name), 'email not verified')
        return email

def full_name(claims: dict, email: str) -> str:
    """ Return the full name of the given claims, or the email if they have none """
    name = claims.get('name')
    if not isinstance(name, str) or not name.strip():
        parts = [claims.get('given_name'), claims.get('family_name')]
        name = ' '.join(part for part in parts if isinstance(part, str))
    return name.strip()[:128] or email

# Administration ----------------------------------------------------------------------------------

def discovery_url(url: str) -> str:
    """ Return the discovery URL of the given issuer URL, or the URL if it is a discovery one """
    url = url.strip()
    return url if url.endswith(DISCOVERY_PATH) else url.rstrip('/') + DISCOVERY_PATH

def check_discovery_url(_form, field):
    """ Accept only HTTPS URLs, because the provider sends the keys that validate tokens. Plain
    HTTP is accepted for providers in this computer, to test with a local Keycloak """
    parts = urllib.parse.urlsplit(discovery_url(field.data or ''))
    local = parts.hostname in ('localhost', '127.0.0.1', '::1')
    if not parts.hostname or not (parts.scheme == 'https' or parts.scheme == 'http' and local):
        raise validators.ValidationError(lazy_gettext('Write an https:// URL'))

def check_scopes(_form, field):
    """ Scopes are names separated by spaces, and openid is required """
    scopes = (field.data or '').split()
    if 'openid' not in scopes or not all(SCOPE_PATTERN.fullmatch(scope) for scope in scopes):
        raise validators.ValidationError(lazy_gettext(
            'Write scopes separated by spaces, including openid'))

def check_claim(_form, field):
    """ Claims are names, or names separated by dots for nested claims """
    if field.data and not CLAIM_PATTERN.fullmatch(field.data):
        raise validators.ValidationError(lazy_gettext(
            'Write a claim name, or names separated by dots'))

class SsoProviderForm(flask_wtf.FlaskForm):
    """ Lets administrators add or change a provider. Sizes are the ones of the columns """
    alias = wtforms.StringField(lazy_gettext('Alias'), validators=[validators.DataRequired(),
        validators.Regexp(ALIAS_PATTERN.pattern + '$', message=lazy_gettext(
            'Use up to 32 lowercase letters, digits, and hyphens'))])
    name = wtforms.StringField(lazy_gettext('Name'), validators=[validators.DataRequired(),
        validators.Length(max=64)])
    status = wtforms.RadioField(lazy_gettext('Status'), choices=list(STATUSES.items()),
        default='disabled')
    discovery_url = wtforms.URLField(lazy_gettext('Discovery URL or issuer'),
        validators=[validators.DataRequired(), validators.Length(max=480), check_discovery_url])
    client_id = wtforms.StringField(lazy_gettext('Client ID'),
        validators=[validators.DataRequired(), validators.Length(max=256)])
    scopes = wtforms.StringField(lazy_gettext('Scopes'), default='openid profile email',
        validators=[validators.DataRequired(), validators.Length(max=256), check_scopes])
    email_claim = wtforms.StringField(lazy_gettext('Email claim'), default='email',
        validators=[validators.DataRequired(), validators.Length(max=256), check_claim])
    trust_emails = wtforms.BooleanField(lazy_gettext(
        'Trust the emails of this provider even if they are not marked as verified'))
    allow_new_users = wtforms.BooleanField(lazy_gettext(
        'Create an account for users who are not registered in VygOJ'))
    professor_claim = wtforms.StringField(lazy_gettext('Professor claim'),
        validators=[validators.Length(max=256), check_claim])
    professor_values = wtforms.StringField(lazy_gettext('Professor values'),
        validators=[validators.Length(max=512)])
    save = wtforms.SubmitField(lazy_gettext('Save'))

class SsoAdminController:
    """ Lets administrators manage the providers and see the users """

    @staticmethod
    def require_admin():
        """ Stop the request if the logged user is not an administrator """
        if not is_admin():
            flask.abort(403)

    @staticmethod
    def get_users():
        """ Show the page of users: the providers and the list of users """
        SsoAdminController.require_admin()
        providers = db.session.scalars(db.select(SsoProvider).order_by(SsoProvider.name)).all()
        users = db.session.scalars(db.select(User).order_by(User.username)
            .options(selectinload(User.identities))).all()
        return flask.render_template('users_admin.html', it={
            'title': gettext('Users'),
            'user': flask.session.get('user'),
            'providers': providers,
            'statuses': STATUSES,
            'users': users,
        })

    @staticmethod
    def edit_provider(alias: str = None):
        """ Show the form of a new provider, or of the provider of the given alias, and save it """
        SsoAdminController.require_admin()
        provider = SsoProvider.find(alias) if alias else SsoProvider()
        if not provider:
            flask.abort(404)
        form = SsoProviderForm(obj=provider)
        if alias:
            # The alias is in the callback URL registered in the provider, so it cannot change
            form.alias.data = alias
        if form.validate_on_submit():
            if not alias and SsoProvider.find(form.alias.data):
                form.alias.errors.append(gettext('Another provider has this alias'))
            else:
                return SsoAdminController.save_provider(form, provider, alias)
        return flask.render_template('sso_provider.html', it={
            'title': provider.name if alias else gettext('New SSO provider'),
            'user': flask.session.get('user'),
            'form': form,
            'alias': alias,
            'callback_url': site_url_for('sso_callback', alias=alias) if alias else None,
            'login_url': site_url_for('sso_login', alias=alias) if alias else None,
            'has_secret': bool(alias and provider.secret()),
            'breadcrumbs': [{ 'href': flask.url_for('get_users_admin'), 'text': gettext('Users') }],
        })

    @staticmethod
    def save_provider(form: SsoProviderForm, provider: SsoProvider, alias: str | None):
        """ Store the provider with the data of the valid form """
        provider.alias = alias or form.alias.data
        provider.name = form.name.data.strip()
        provider.status = form.status.data
        provider.discovery_url = discovery_url(form.discovery_url.data)
        provider.client_id = form.client_id.data.strip()
        provider.scopes = ' '.join(form.scopes.data.split())
        provider.email_claim = form.email_claim.data
        provider.trust_emails = form.trust_emails.data
        provider.allow_new_users = form.allow_new_users.data
        provider.professor_claim = form.professor_claim.data or ''
        provider.professor_values = ', '.join(value.strip() for value
            in (form.professor_values.data or '').split(',') if value.strip())
        if not alias:
            db.session.add(provider)
        db.session.commit()
        log_event('sso_provider', { 'action': 'update' if alias else 'add',
            'provider': provider.alias, 'status': provider.status })
        flask.flash(gettext('Provider %(provider)s saved.', provider=provider.name), 'success')
        # A new provider shows its callback URL, to send it to the team of the provider
        return flask.redirect(flask.url_for('edit_sso_provider', alias=provider.alias))

    @staticmethod
    def delete_provider(alias: str):
        """ Remove the provider of the given alias. The identities of its users are kept, so they
        are linked again if the provider is added back with the same issuer """
        SsoAdminController.require_admin()
        provider = SsoProvider.find(alias)
        if not provider:
            flask.abort(404)
        db.session.delete(provider)
        db.session.commit()
        _clients.pop(alias, None)
        log_event('sso_provider', { 'action': 'delete', 'provider': alias })
        flask.flash(gettext('Provider %(provider)s deleted.', provider=provider.name), 'warning')
        return flask.redirect(flask.url_for('get_users_admin'))
