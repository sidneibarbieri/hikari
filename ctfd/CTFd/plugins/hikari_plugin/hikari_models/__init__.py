from CTFd.models import db
from CTFd.models import Challenges

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
   
