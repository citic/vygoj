""" Sections (groups) of courses: the form where a professor offers a prepared course in a new
section or edits a section, the update of a section to the last version of its course, and the
enrollment of users in the open sections (courses/course_section.py) """

import datetime

import flask
import flask_wtf
import wtforms
from flask import current_app as app
from flask_babel import gettext, lazy_gettext, ngettext
from sqlalchemy.exc import IntegrityError
from wtforms import validators

from activity_log import log_event
from courses.course_section import (DURATION_WEEKS, DURATIONS, MAX_CAMPUS_LENGTH, MAX_COST,
    MAX_INSTITUTION_LENGTH, MAX_NUMBER, MAX_WEEKS, MAX_YEAR, MAX_SECTIONS_PER_COURSE, MIN_NUMBER,
    MIN_WEEKS, MIN_YEAR, MODALITIES, SECTION_FIELDS, TERMS, CourseSection, taken_numbers)
from courses.repo_course import RepoCourse
from db import db
from repos.git_repo import GitError
from repos.professor_repo import CloneError
from users import MAX_PASSWORD_LENGTH, LoginAttempt, User, has_role

# Numbers of the sections that the form of a new section offers at once, with up to 3 digits and
# separated by spaces, e.g. 003 005 006, and the most of them in a form
NUMBERS_PATTERN = r'\s*[0-9]{1,3}( +[0-9]{1,3})*\s*'
MAX_NUMBERS = 20
# Number of the section in the form of a section that exists
NUMBER_PATTERN = r'\s*[0-9]{1,3}\s*'

class SectionNumbersField(wtforms.StringField):
    """ The numbers of the sections in a text field, with 3 digits, e.g. 001: a number field would
    drop the zeros at the left. The form of a new section takes several numbers to offer several
    sections at once, e.g. 003 005 006, and the one of a section that exists takes one """

    def _value(self) -> str:
        """ The text of the field: as the user wrote it, or the number of a section that exists
        with 3 digits """
        if self.raw_data:
            return self.raw_data[0]
        return f'{self.data:03d}' if isinstance(self.data, int) else self.data or ''

    def numbers(self) -> list:
        """ Return the numbers of the field, as integers """
        if isinstance(self.data, int):
            return [self.data]
        return [int(text) for text in (self.data or '').split()]

def number_codes(numbers: list) -> str:
    """ Return the numbers of sections with 3 digits, separated by spaces, e.g. 003 005 """
    return ' '.join(f'{number:03d}' for number in numbers)

class SectionForm(flask_wtf.FlaskForm):
    """ The data of a section that its professor fills when they offer a course or edit the
    section. Sizes and ranges are the ones of the columns. The password is never shown: it is
    stored as a hash, and an empty field keeps the stored one """
    duration = wtforms.SelectField(lazy_gettext('Duration'),
        validators=[validators.InputRequired()], default='semester',
        choices=list(DURATIONS.items()))
    weeks = wtforms.IntegerField(lazy_gettext('Weeks'),
        validators=[validators.Optional(), validators.NumberRange(MIN_WEEKS, MAX_WEEKS)])
    year = wtforms.IntegerField(lazy_gettext('Year'),
        validators=[validators.InputRequired(), validators.NumberRange(MIN_YEAR, MAX_YEAR)])
    term = wtforms.SelectField(lazy_gettext('Term'),
        choices=[('', lazy_gettext('No term')), *((term, term) for term in TERMS)])
    start_date = wtforms.DateField(lazy_gettext('Start date'), validators=[validators.Optional()])
    end_date = wtforms.DateField(lazy_gettext('End date'), validators=[validators.Optional()])
    archive_date = wtforms.DateField(lazy_gettext('Archive date'),
        validators=[validators.Optional()])
    # The examples of the institution and campus are names, not translated
    institution = wtforms.StringField(lazy_gettext('Institution'),
        validators=[validators.Length(max=MAX_INSTITUTION_LENGTH)],
        render_kw={'placeholder': 'Universidad de Costa Rica'})
    campus = wtforms.StringField(lazy_gettext('Campus'),
        validators=[validators.Length(max=MAX_CAMPUS_LENGTH)],
        render_kw={'placeholder': 'Sede Rodrigo Facio'})
    number = SectionNumbersField(lazy_gettext('Section numbers'), default='001',
        validators=[validators.InputRequired(), validators.Regexp(f'^{NUMBERS_PATTERN}$',
            message=lazy_gettext('Write numbers of up to 3 digits separated by spaces, e.g. 003'
                ' 005 006.'))],
        render_kw={'inputmode': 'numeric', 'pattern': NUMBERS_PATTERN,
            'maxlength': MAX_NUMBERS * 4})
    modality = wtforms.SelectField(lazy_gettext('Modality of study'),
        validators=[validators.InputRequired()], default='regular',
        choices=[(value, names[1]) for value, names in MODALITIES.items()])
    self_enroll = wtforms.BooleanField(lazy_gettext('Self-enrollment'), default=True)
    new_password = wtforms.PasswordField(lazy_gettext('Enrollment password'),
        validators=[validators.Length(max=MAX_PASSWORD_LENGTH)])
    remove_password = wtforms.BooleanField(lazy_gettext('Remove the password'))
    manual_enroll = wtforms.BooleanField(lazy_gettext('Manual enrollment by the professor'))
    cost = wtforms.DecimalField(lazy_gettext('Cost'), places=2, default=0,
        validators=[validators.InputRequired(), validators.NumberRange(0, MAX_COST)])
    currency = wtforms.SelectField(lazy_gettext('Currency'), choices=[],
        validators=[validators.InputRequired()])
    save = wtforms.SubmitField(lazy_gettext('Save'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The currencies are a setting of the server, read in the request
        self.currency.choices = [(code, code) for code in app.config['SECTION_CURRENCIES']]
        # True in the form of a section that exists, which has one number
        self.single = False
        if not self.is_submitted():
            if self.year.data is None:
                self.year.data = datetime.date.today().year
            if self.weeks.data is None:
                self.weeks.data = DURATION_WEEKS.get(self.duration.data)

    def edit_one(self):
        """ Make the form edit a section that exists, with one number """
        self.single = True
        self.number.label.text = gettext('Section number')
        self.number.render_kw = { **self.number.render_kw, 'pattern': NUMBER_PATTERN,
            'maxlength': 3 }

    def validate(self, extra_validators=None) -> bool:
        """ Check the fields, and the rules between them: the weeks of a section that is not
        indefinite, the numbers, the dates in order, and at least one method of enrollment """
        valid = super().validate(extra_validators)
        if self.duration.data != 'indefinite' and self.weeks.data is None and not self.weeks.errors:
            self.weeks.errors.append(gettext('Write the weeks of the section.'))
            valid = False
        if not self.number.errors and not self.check_numbers():
            valid = False
        start, end = self.start_date.data, self.end_date.data
        if start and end and end < start:
            self.end_date.errors.append(gettext('The end date must not be before the start date.'))
            valid = False
        archive, last = self.archive_date.data, end or start
        if archive and last and archive < last:
            self.archive_date.errors.append(
                gettext('The archive date must not be before the start and end dates.'))
            valid = False
        if not self.self_enroll.data and not self.manual_enroll.data:
            self.manual_enroll.errors.append(gettext('Choose at least one method of enrollment.'))
            valid = False
        return valid

    def check_numbers(self) -> bool:
        """ Check the numbers of the sections: from 1 to 999, not repeated, at most MAX_NUMBERS,
        and only one in the form of a section that exists. Errors go to the field """
        numbers = self.number.numbers()
        if any(number < MIN_NUMBER or number > MAX_NUMBER for number in numbers):
            self.number.errors.append(gettext('Section numbers go from 001 to 999.'))
        elif len(set(numbers)) != len(numbers):
            self.number.errors.append(gettext('A section number is repeated.'))
        elif self.single and len(numbers) > 1:
            self.number.errors.append(gettext('Write one section number.'))
        elif len(numbers) > MAX_NUMBERS:
            self.number.errors.append(gettext('Write at most %(num)d section numbers.',
                num=MAX_NUMBERS))
        return not self.number.errors

    def store_in(self, section: CourseSection, number: int):
        """ Copy the valid fields to the section, with the given number, and its password if the
        professor typed one or removed it """
        for name in SECTION_FIELDS:
            if name != 'number':
                setattr(section, name, getattr(self, name).data)
        section.number = number
        if section.duration == 'indefinite':
            section.weeks = None
        # A request without these fields (not sent by browsers) leaves them empty
        section.institution = (section.institution or '').strip()
        section.campus = (section.campus or '').strip()
        if self.new_password.data:
            section.set_password(self.new_password.data)
        elif self.remove_password.data:
            section.set_password(None)

class SectionController:
    """ Routes of the sections: offer a course in a new section, edit and update a section, and
    enroll in it """

    @staticmethod
    def create(name: str):
        """ Show the form of a new section of the prepared course of the given name, and offer the
        course in that section, which shows the commit of the last pull of its repo """
        repo_course = SectionController.own_course(RepoCourse.find(name))
        if repo_course.hidden:
            flask.abort(404)
        form = SectionForm()
        if form.validate_on_submit():
            numbers = form.number.numbers()
            if CourseSection.count(repo_course.id) + len(numbers) > MAX_SECTIONS_PER_COURSE:
                flask.flash(gettext('The course %(name)s has too many sections.', name=name),
                    'error')
                return flask.redirect(flask.url_for('get_index'))
            sections = []
            for number in numbers:
                section = CourseSection(course_id=repo_course.id, commit=repo_course.commit)
                form.store_in(section, number)
                sections.append(section)
            taken = taken_numbers(sections[0], numbers)
            if taken:
                form.number.errors.append(ngettext('The course has another section with the'
                    ' number %(numbers)s in the same term, institution, and campus.',
                    'The course has other sections with the numbers %(numbers)s in the same'
                    ' term, institution, and campus.', len(taken), numbers=number_codes(taken)))
            elif (SectionController.prepare(repo_course, repo_course.commit)
                    and SectionController.save(form, sections)):
                for section in sections:
                    log_event('section_create', { 'section': section.id, **section.values(),
                        'commit': section.commit }, course=name)
                flask.flash(ngettext('Course %(name)s offered in section %(codes)s.',
                    'Course %(name)s offered in sections %(codes)s.', len(numbers), name=name,
                    codes=number_codes(numbers)), 'success')
                return flask.redirect(flask.url_for('get_index', _anchor='taught_courses'))
        return SectionController.render(form, repo_course, None)

    @staticmethod
    def edit(section_id: int):
        """ Show the form of a section of the logged professor, and save it """
        section = SectionController.own_section(section_id)
        form = SectionForm(obj=section)
        form.edit_one()
        if form.validate_on_submit():
            old_values = section.values()
            form.store_in(section, form.number.numbers()[0])
            if SectionController.save(form):
                new_values = section.values()
                changes = { name: [old, new_values[name]]
                    for name, old in old_values.items() if old != new_values[name] }
                if form.new_password.data:
                    changes['password'] = [old_values['password'], True]
                if changes:
                    log_event('section_edit', { 'section': section.id, 'changes': changes },
                        course=section.course.name)
                flask.flash(gettext('Section %(code)s of %(name)s saved.', code=section.code(),
                    name=section.course.name), 'success')
                return flask.redirect(flask.url_for('get_index', _anchor='taught_courses'))
        return SectionController.render(form, section.course, section)

    @staticmethod
    def update(section_id: int):
        """ Make the section show the last version of its course, the commit of the last pull of
        its repo, and delete the snapshot of its old commit if no other section shows it """
        section = SectionController.own_section(section_id)
        repo_course = section.course
        old_commit, new_commit = section.commit, repo_course.commit
        if repo_course.hidden:
            flask.flash(gettext('The repository of %(name)s does not have the course anymore.',
                name=repo_course.name), 'error')
        elif old_commit == new_commit:
            flask.flash(gettext('Section %(code)s of %(name)s already shows the last version.',
                code=section.code(), name=repo_course.name), 'info')
        elif SectionController.prepare(repo_course, new_commit):
            section.commit = new_commit
            db.session.commit()
            SectionController.drop_snapshot(repo_course, old_commit)
            log_event('section_update', { 'section': section.id,
                'commit': [old_commit, new_commit] }, course=repo_course.name)
            flask.flash(gettext('Section %(code)s of %(name)s updated.', code=section.code(),
                name=repo_course.name), 'success')
        return flask.redirect(flask.url_for('get_index', _anchor='taught_courses'))

    @staticmethod
    def enroll(section_id: int):
        """ The logged user enrolls in an open section, with its password if it has one. Failed
        passwords are limited as logins (LoginAttempt), so they cannot be guessed """
        user_id = User.logged_id()
        if not user_id:
            flask.abort(401)
        section = CourseSection.find(section_id)
        if not section or not section.is_open():
            flask.abort(404)
        name = section.course.name
        password = flask.request.form.get('password', '')
        # Each section limits the attempts of each user, by their id, which is short
        key, address = f'section:{section.id}:{user_id}', flask.request.remote_addr
        if CourseSection.of_student(section.course_id, user_id):
            flask.flash(gettext('You are enrolled in %(name)s already.', name=name), 'info')
        elif not section.has_started():
            flask.flash(gettext('The enrollment in %(name)s opens on %(date)s.', name=name,
                date=section.start_date.isoformat()), 'info')
        elif LoginAttempt.is_blocked(key, address):
            log_event('course_enroll_failed', { 'section': section.id, 'blocked': True },
                course=name)
            flask.flash(gettext('Too many failed attempts. Try again later.'), 'error')
        elif len(password) > MAX_PASSWORD_LENGTH or not section.check_password(password):
            LoginAttempt.record_failure(key, address)
            log_event('course_enroll_failed', { 'section': section.id }, course=name)
            flask.flash(gettext('The enrollment password is not valid.'), 'error')
        elif section.enroll(user_id):
            LoginAttempt.clear(key, address)
            log_event('course_enroll', { 'section': section.id }, course=name)
            flask.flash(gettext('You are enrolled in %(name)s, section %(code)s.', name=name,
                code=section.code()), 'success')
        return flask.redirect(flask.url_for('get_index'))

    @staticmethod
    def own_course(repo_course: RepoCourse | None) -> RepoCourse:
        """ Return the course if it is in a repo of the logged professor, or else stop the request
        with 404 if it does not exist, or 403 """
        user_id = User.logged_id()
        if not user_id or not repo_course:
            flask.abort(404)
        if not has_role('professor') or not repo_course.owned_by(user_id):
            flask.abort(403)
        return repo_course

    @staticmethod
    def own_section(section_id: int) -> CourseSection:
        """ Return the section of the given id if its course is in a repo of the logged professor,
        or else stop the request with 404 or 403 """
        section = CourseSection.find(section_id)
        SectionController.own_course(section and section.course)
        return section

    @staticmethod
    def prepare(repo_course: RepoCourse, commit: str) -> bool:
        """ Check out the snapshot of the commit, so the students of the section see it. Return
        False, with a message, if it could not be done """
        try:
            repo_course.repo.add_snapshot(commit)
            return True
        except (CloneError, GitError, OSError, ValueError):
            app.logger.exception('could not prepare the snapshot of %s', repo_course.name)
            flask.flash(gettext('The version of the course could not be prepared. Pull the'
                ' repository and try again.'), 'error')
            return False

    @staticmethod
    def drop_snapshot(repo_course: RepoCourse, commit: str):
        """ Delete the snapshot of the commit if no section of the repo shows it anymore. A
        failure is logged, and the snapshot stays on the disk """
        if CourseSection.shows_commit(repo_course.repo_id, commit):
            return
        try:
            repo_course.repo.remove_snapshot(commit)
        except (GitError, OSError, ValueError):
            app.logger.exception('could not remove the snapshot %s of %s', commit,
                repo_course.name)

    @staticmethod
    def save(form: SectionForm, new_sections: list = ()) -> bool:
        """ Store the new sections, or the changes of a section, all or none. Return False, with
        the error in the form, if the course has another section with the same year, term,
        institution, campus, and number (e.g. a professor saved it meanwhile) """
        db.session.add_all(new_sections)
        try:
            db.session.commit()
            return True
        except IntegrityError:
            db.session.rollback()
            form.number.errors.append(gettext(
                'The course has another section with this number in the same term, institution,'
                ' and campus.'))
            return False

    @staticmethod
    def render(form: SectionForm, repo_course: RepoCourse, section: CourseSection | None):
        """ Show the form of a new section (section is None) or of the given one """
        if section is None:
            title = gettext('Offer %(name)s in a new section', name=repo_course.name)
        else:
            title = gettext('Section %(code)s of %(name)s', code=section.code(),
                name=repo_course.name)
        return flask.render_template('section.html', it={
            'title': title,
            'user': flask.session.get('user'),
            'form': form,
            'course': repo_course,
            'section': section,
            # Weeks of each duration, so section.js estimates the end and archive dates
            'weeks': DURATION_WEEKS,
            'breadcrumbs': [{ 'href': flask.url_for('get_index'), 'text': repo_course.name }],
        })
