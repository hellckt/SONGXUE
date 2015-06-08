# -*- coding: utf-8 -*-
from flask import render_template, flash, url_for, redirect, current_app, request
from flask.ext.login import login_required, current_user
from app import db
from app.course import course
from app.course.forms import CoursePublishForm, CommentForm, ApplicationForm
from app.decorators import permission_required
from app.models import Permission, Course, Comment, Application, User

__author__ = 'scott'

# Attention: 方法名不能是course！会与蓝图命名冲突！
# TODO-cott: 修改蓝图命名？


@course.route('/<int:id>', methods = ['GET', 'POST'])
def detail(id):
    courses = Course.query.get_or_404(id)
    # print current_user.is_applied_by(courses)
    form = CommentForm(prefix = "comment-form")
    if form.validate_on_submit():
        comment = Comment(body = form.body.data,
                          course = courses,
                          author = current_user._get_current_object())
        db.session.add(comment)
        flash(u'你的评论已发布。')
        return redirect(url_for('course.detail', id = courses.id, page = -1))
    application_form = ApplicationForm(prefix = "application")
    if application_form.validate_on_submit():
        application = Application()
        flash(u'报名成功！')
        return redirect(url_for('course.detail', id = courses.id, page = -1))
    page = request.args.get('page', 1, type = int)
    if page == -1:
        page = (courses.comments.count() - 1) / \
               current_app.config['SONGXUE_COMMENTS_PER_PAGE'] + 1
    pagination = courses.comments.order_by(Comment.timestamp.asc()).paginate(
        page, per_page = current_app.config['SONGXUE_COMMENTS_PER_PAGE'],
        error_out = False)
    comments = pagination.items
    # courses = [courses] 为course.html中courses[0].id,转化为list,否则会报错
    return render_template('course/course.html', form = form, courses = [courses],
                           comments = comments, pagination = pagination,
                           application_form = application_form)


@course.route('/publish', methods = ['GET', 'POST'])
@login_required
@permission_required(Permission.PUBLISH_COURSES)
def publish():
    form = CoursePublishForm()
    if form.validate_on_submit():
        course = Course(title = form.title.data,
                        name = form.name.data,
                        brief = form.brief.data,
                        detailed = form.detailed.data,
                        price = form.price.data,
                        contact = form.contact.data,
                        telephone = form.telephone.data,
                        category = form.category.data,
                        company = form.company.data,
                        publisher = current_user._get_current_object())
        db.session.add(course)
        flash(u'你的课程已发布。')
        return redirect(url_for('.publish', form = form))
    return render_template('course/publish.html', form = form)


@course.route('/edit/<int:id>', methods = ['GET', 'POST'])
@login_required
@permission_required(Permission.PUBLISH_COURSES)
def edit(id):
    course = Course.query.get_or_404(id)
    form = CoursePublishForm()
    if form.validate_on_submit():
        course.title = form.title.data
        course.name = form.name.data
        course.brief = form.brief.data
        course.detailed = form.detailed.data
        course.price = form.price.data
        course.contact = form.contact.data
        course.telephone = form.telephone.data
        course.category = form.category.data
        course.company = form.company.data
        db.session.add(course)
        flash(u'你的课程已修改。')
        return redirect(url_for('course.detail', id = course.id, page = -1))
    form.title.data = course.title
    form.name.data = course.name
    form.brief.data = course.brief
    form.detailed.data = course.detailed
    form.price.data = course.price
    form.contact.data = course.contact
    form.telephone.data = course.telephone
    form.category.data = course.category
    form.company.data = course.company
    return render_template('course/edit.html', form = form)


@course.route('/application/<int:id>', methods = ['POST'])
@login_required
def application(id):
    # TODO-cott: 优化表单，并了解安全方面
    course = Course.query.filter_by(id = id).first()
    if course is None:
        flash(u'错误的课程。')
        return redirect(url_for('course.detail', id = id, page = -1))
    if current_user.is_applied_by(course):
        flash(u'你已报名。')
        return redirect(url_for('course.detail', id = id, page = -1))
    if not course.is_appled_by(current_user):
        ap = Application(name = request.form['application-name'],
                         telephone = request.form['application-tel'],
                         address = request.form['application-address'],
                         applicant = current_user._get_current_object(),
                         apply_course = course)
        db.session.add(ap)
        flash(u'报名成功')
        return redirect(url_for('course.detail', id = id, page = -1))
    return redirect(url_for('course.detail', id = id, page = -1))


@course.route('/applications', methods = ['GET', 'POST'])
@login_required
def applications():
    """显示所有课程的报名表，按课程分类"""
    page = request.args.get('page', 1, type = int)
    pagination = current_user.applied \
        .order_by(Application.timestamp.asc()) \
        .paginate(page, per_page = current_app.config['SONGXUE_COMMENTS_PER_PAGE'],
                  error_out = False)
    apls = pagination.items
    return render_template('course/applications.html', apls = apls,
                           pagination = pagination)


@course.route('/application_summary', methods = ['GET', 'POST'])
@login_required
@permission_required(Permission.PUBLISH_COURSES)
def application_summary():
    page = request.args.get('page', 1, type = int)
    pagination = Application.query \
        .join(Course) \
        .join(User) \
        .filter(Course.author_id == current_user.id) \
        .order_by(Application.timestamp.asc()) \
        .paginate(page, per_page = current_app.config['SONGXUE_COMMENTS_PER_PAGE'],
                  error_out = False)
    apls = pagination.items
    # ps: apls[0].apply_course.publisher 是课程发布者,apls[0].applicant 是课程申请者(报名人)
    return render_template('course/application_summary.html', apls = apls,
                           pagination = pagination)


@course.route('/<int:id>/weixin/application', methods = ['GET', 'POST'])
def weixin_application(id):
    course = Course.query.get_or_404(id)
    form = ApplicationForm()
    if form.validate_on_submit():
        flash(u"报名成功！")
        return redirect(url_for('course.weixin_application', id = id))
    return render_template('course/weixin_application.html', form = form)