# -*- coding: utf-8 -*-

__author__ = 'scott'

from flask import Blueprint

course = Blueprint('course', __name__)

from . import views
from ..models import Permission


@course.app_context_processor
def inject_permissions():
    return dict(Permission=Permission)