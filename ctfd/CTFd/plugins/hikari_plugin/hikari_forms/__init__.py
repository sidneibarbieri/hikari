from flask_babel import lazy_gettext as _l
from wtforms.validators import InputRequired, DataRequired
from wtforms import TextAreaField, StringField, FileField, SelectMultipleField, IntegerField
from flask_wtf import FlaskForm
from CTFd.models import Teams
from CTFd.forms import BaseForm
from CTFd.forms.fields import SubmitField


from wtforms import SelectField
from CTFd.forms import CTFdCSRF
import CTFd.plugins.hikari_plugin.hikari_models as hikari_models

# Form for sending notifications to all competitors
def NotifyCompetitorsForm(*args, **kwargs):
    class _NotifyCompetitorsForm(BaseForm):
        textArea = TextAreaField(_l('Message'), validators=[InputRequired()])
        submit = SubmitField(_l('Send Email'))

    return _NotifyCompetitorsForm(*args, **kwargs)

def NotifyMultipleCompetitorsForm(*args, **kwargs):
    teams = Teams.query.all()
    team_choices = list()
    for team in teams:
        team_choices.append((str(team.id), team.name))

    class _NotifyCompetitorsForm(BaseForm):
        message = TextAreaField('Message', id='message-area' ,validators=[InputRequired()])
        team_selection = SelectMultipleField('Select team', id='team-selection-field', choices=team_choices ,validators=[InputRequired()])
        submit = SubmitField('Notify Team(s)')

    return _NotifyCompetitorsForm(*args, **kwargs)




# Form for registering zerotiers
def ZerotierForm(*args, **kwargs):
    class _ZerotierForm(BaseForm):
        network_id = StringField('Network ID', validators=[DataRequired()])
        name = StringField('Name', validators=[DataRequired()])
        submit = SubmitField('Submit')

    return _ZerotierForm(*args, **kwargs)


def SetupFirstChallengeForm(*args, **kwargs):
    challs = hikari_models.HikariChallengeModel.query.all()
    chall_choices = [(str(c.id), c.name) for c in challs]

    class _SetupFirstChallengeForm(BaseForm):
        challenge_selection = SelectField('Select challenge', id='chall-selection-field', choices=chall_choices ,validators=[InputRequired()])
        submit = SubmitField('Setup')

    return _SetupFirstChallengeForm(*args, **kwargs)



def ImportHikariCTFdForm(*args, **kwargs):
    class _ImportHikariCTFdForm(FlaskForm):
        class Meta:
            csrf = True
            csrf_class = CTFdCSRF
            csrf_field_name = "nonce"
        file_import = FileField('Zip file of exported competition', validators=[DataRequired()])
        submit = SubmitField('Setup')

    return _ImportHikariCTFdForm(*args, **kwargs)

def HikariFileUploadForm(*args, **kwargs):
    class _HikariFileUploadForm(FlaskForm):
        class Meta:
            csrf = True
            csrf_class = CTFdCSRF
            csrf_field_name = "nonce"
        file_log = FileField('JsonLogFile')
        submit = SubmitField('Upload')
    return _HikariFileUploadForm(*args, **kwargs)

def HikariAddChallengeForm(*args, **kwargs):
    class _HikariAddChallengeForm(FlaskForm):
        class Meta:
            csrf = True
            csrf_class = CTFdCSRF
            csrf_field_name = "nonce"
        
        challenge_id = IntegerField('Challenge id')
        max_attempts = IntegerField('Challenge max_attempts')
        connection_info = StringField('Challenge connection info')
        state = StringField('Challenge state field')
        name = StringField('Challenge name', validators=[DataRequired()])
        category = StringField('Challenge category', validators=[DataRequired()])
        description = StringField('Challenge description', validators=[DataRequired()])
        value = IntegerField('Challenge value', validators=[DataRequired()])
        type = StringField('Challenge type')
        
        log_filename = StringField('Challenge log filename')
        file_log = FileField('JsonLogFile')
        submit = SubmitField('Add Challenge')
    return _HikariAddChallengeForm(*args, **kwargs)
