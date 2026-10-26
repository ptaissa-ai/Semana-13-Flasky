from flask_wtf import FlaskForm
from wtforms import StringField, EmailField, SubmitField
from wtforms.validators import DataRequired, Length, Email

class NameForm(FlaskForm):
    username = StringField('Nome do usuário', validators=[DataRequired(), Length(min=2, max=80)])
    email = EmailField('E-mail para receber a notificação', validators=[DataRequired(), Email(), Length(max=254)])
    submit = SubmitField('Cadastrar usuário')
