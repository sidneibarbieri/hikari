from wtforms import BooleanField, RadioField, StringField, TextAreaField
from wtforms.validators import InputRequired

from CTFd.forms import BaseForm
from CTFd.forms.fields import SubmitField


class NotificationForm(BaseForm):
    title = StringField("Título", description="Título exibido aos usuários")
    content = TextAreaField(
        "Conteúdo",
        description="Mensagem da notificação. Aceita HTML e Markdown.",
    )
    type = RadioField(
        "Tipo de notificação",
        choices=[
            ("toast", "Toast"),
            ("alert", "Alerta"),
            ("background", "Segundo plano"),
        ],
        default="toast",
        description="Forma de entrega da notificação aos usuários",
        validators=[InputRequired()],
    )
    sound = BooleanField(
        "Tocar som",
        default=True,
        description="Toca um som quando o usuário recebe a notificação",
    )
    submit = SubmitField("Enviar")
