from CTFd.models import db
from CTFd.models import Challenges

class Zerotier(db.Model):
    __tablename__ = 'zerotier'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True)
    network_id = db.Column(db.String(128))

# Zerotier table configuration
class ZerotierConfig(db.Model):
    __tablename__ = 'zerotier_config'

    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id', ondelete='SET NULL'), nullable=True, unique=True)
    zerotier_id = db.Column(db.Integer, db.ForeignKey('zerotier.id', ondelete='SET NULL'), nullable=True)

    team = db.relationship('Teams', backref=db.backref('zerotier_config', uselist=False, lazy='joined'))
    zerotier = db.relationship('Zerotier', backref=db.backref('zerotier', uselist=False, lazy='joined'))

class HikariFiles(db.Model):
    __tablename__ = 'hikari_files'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(128), unique=True, nullable=False)
    location = db.Column(db.String(1024))

###### Hikari Challenge database representation
class HikariChallengeModel(Challenges):
    __tablename__ = 'hikari_challenges'
    __mapper_args__ = {"polymorphic_identity": "hikari"}
    id = db.Column(db.Integer, db.ForeignKey("challenges.id", ondelete='CASCADE'), primary_key=True)
    logs_activated = db.Column(db.Boolean, default=False)
    log_filename = db.Column(db.String(128), db.ForeignKey("hikari_files.filename", ondelete='CASCADE'), nullable=True)
    
    log_file = db.relationship('HikariFiles', backref=db.backref('hikari_challenges', uselist=False, lazy='joined'))

    def __init__(self, *args, **kwargs):
        super(HikariChallengeModel, self).__init__(**kwargs)
   
