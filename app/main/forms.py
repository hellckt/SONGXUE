# -*- coding:utf-8 -*-

from flask.ext.wtf import Form
from wtforms import StringField, TextAreaField, BooleanField, SelectField,\
    SubmitField
from wtforms.validators import Required, Length, Email, Regexp
from wtforms import ValidationError
from flask.ext.pagedown.fields import PageDownField
from ..models import Role, User


class EditProfileForm(Form):
    name = StringField(u'真实姓名', validators=[Length(0, 64)])
    location = StringField(u'现居地', validators=[Length(0, 64)])
    about_me = TextAreaField(u'自我简介')
    submit = SubmitField(u'保存')


class EditProfileAdminForm(Form):
    email = StringField(u'邮箱', validators=[Required(), Length(1, 64),
                                             Email()])
    username = StringField(u'用户名', validators=[
        Required(), Length(1, 64), Regexp('^[A-Za-z][A-Za-z0-9_.]*$', 0,
                                          u'用户名只能使用字母 '
                                          u'数字，点或下划线。')])
    confirmed = BooleanField(u'验证')
    role = SelectField(u'角色', coerce=int)
    name = StringField(u'真实姓名', validators=[Length(0, 64)])
    location = StringField(u'现居地', validators=[Length(0, 64)])
    about_me = TextAreaField(u'自我简介')
    submit = SubmitField(u'保存')

    def __init__(self, user, *args, **kwargs):
        super(EditProfileAdminForm, self).__init__(*args, **kwargs)
        self.role.choices = [(role.id, role.name)
                             for role in Role.query.order_by(Role.name).all()]
        self.user = user

    def validate_email(self, field):
        if field.data != self.user.email and \
                User.query.filter_by(email=field.data).first():
            raise ValidationError(u'该邮箱已被注册。')

    def validate_username(self, field):
        if field.data != self.user.username and \
                User.query.filter_by(username=field.data).first():
            raise ValidationError(u'该用户名已被注册。')


class PostForm(Form):
    body = PageDownField(u'来发布你现在的想法吧。', validators=[Required()])
    submit = SubmitField(u'发布')


class CommentForm(Form):
    body = StringField(u'输入你的评论', validators=[Required()])
    submit = SubmitField(u'提交')
