# -*- coding: utf-8 -*-
from flask.ext.wtf import Form
from wtforms import StringField, IntegerField, SelectField, SubmitField, TextAreaField
from wtforms.validators import Length, Required
from wtforms.widgets.html5 import TelInput

__author__ = 'scott'


class CoursePublishForm(Form):
    title = StringField(u'标题', validators = [Length(1, 64)])
    name = StringField(u'课程名', validators = [Length(1, 64)])
    brief = StringField(u'简要描述')
    detailed = TextAreaField(u'详细描述')
    price = IntegerField(u'价格')
    contact = StringField(u'联系人')
    telephone = StringField(u'联系电话')
    category = SelectField(u'分类')
    company = StringField(u'公司名称')
    submit = SubmitField(u'发布')

    def __init__(self, *args, **kwargs):
        super(CoursePublishForm, self).__init__(*args, **kwargs)
        self.category.choices = [('language_trainning', u'语言培训')]


class ApplicationForm(Form):
    name = StringField(u'姓名', validators=[Required()])
    tel = StringField(u'联系电话', validators=[Required()])
    address = StringField(u'联系地址')
    submit = SubmitField(u'确认')


class CommentForm(Form):
    body = StringField(u'输入你的评论', validators=[Required()])
    submit = SubmitField(u'提交')