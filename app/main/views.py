# -*- coding:utf-8 -*-

from flask import render_template, redirect, url_for, abort, flash, request, \
    current_app, make_response
from flask.ext.login import login_required, current_user
from flask.ext.sqlalchemy import get_debug_queries
from . import main
from .forms import EditProfileForm, EditProfileAdminForm, PostForm, \
    CommentForm
from .. import db
from ..models import Permission, Role, User, Post, Comment, Course
from ..decorators import admin_required, permission_required


@main.after_app_request
def after_request(response):
    for query in get_debug_queries():
        if query.duration >= current_app.config['SONGXUE_SLOW_DB_QUERY_TIME']:
            current_app.logger.warning(
                u'慢查询： %s\n参数: %s\n执行时间: %fs\n内容: %s\n'
                % (query.statement, query.parameters, query.duration,
                   query.context))
    return response


@main.route('/shutdown')
def server_shutdown():
    if not current_app.testing:
        abort(404)
    shutdown = request.environ.get('werkzeug.server.shutdown')
    if not shutdown:
        abort(500)
    shutdown()
    return u'网站已关闭...'


@main.route('/homepage', methods=['GET', 'POST'])
def home():
    return render_template('theme_base.html')


@main.route('/', methods=['GET', 'POST'])
@main.route('/index', methods=['GET', 'POST'])
def index():
    page = request.args.get('page', 1, type=int)
    show_followed = False
    if current_user.is_authenticated():
        show_followed = bool(request.cookies.get('show_followed', ''))
    if show_followed:
        query = current_user.followed_courses
    else:
        query = Course.query
    pagination = query.order_by(Course.timestamp.desc()).paginate(
        page, per_page=current_app.config['SONGXUE_POSTS_PER_PAGE'],
        error_out=False)
    courses = pagination.items
    return render_template('index.html', courses=courses,
                           show_followed=show_followed, pagination=pagination)


@main.route('/post-index', methods=['GET', 'POST'])
def post_index():
    form = PostForm()
    if current_user.can(Permission.WRITE_ARTICLES) and \
            form.validate_on_submit():
        post = Post(body=form.body.data,
                    author=current_user._get_current_object())
        db.session.add(post)
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    show_followed = False
    if current_user.is_authenticated():
        show_followed = bool(request.cookies.get('show_followed', ''))
    if show_followed:
        query = current_user.followed_posts
    else:
        query = Post.query
    pagination = query.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['SONGXUE_POSTS_PER_PAGE'],
        error_out=False)
    posts = pagination.items
    return render_template('post_index.html', form=form, posts=posts,
                           show_followed=show_followed, pagination=pagination)


@main.route('/user/<username>')
def user(username):
    user = User.query.filter_by(username=username).first_or_404()
    page = request.args.get('page', 1, type=int)
    post_pagination = user.posts.order_by(Post.timestamp.desc()).paginate(
        page, per_page=current_app.config['SONGXUE_POSTS_PER_PAGE'],
        error_out=False)
    posts = post_pagination.items
    pagination = user.courses.order_by(Course.timestamp.desc()).paginate(
        page, per_page=current_app.config['SONGXUE_POSTS_PER_PAGE'],
        error_out=False)
    courses = pagination.items
    return render_template('user.html', user=user, posts=posts,
                           courses=courses, pagination=pagination,
                           post_pagination=post_pagination)


@main.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    if form.validate_on_submit():
        current_user.name = form.name.data
        current_user.location = form.location.data
        current_user.about_me = form.about_me.data
        db.session.add(current_user)
        flash(u'你的个人资料已更新。')
        return redirect(url_for('.user', username=current_user.username))
    form.name.data = current_user.name
    form.location.data = current_user.location
    form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', form=form)


@main.route('/edit-profile/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_profile_admin(id):
    user = User.query.get_or_404(id)
    form = EditProfileAdminForm(user=user)
    if form.validate_on_submit():
        user.email = form.email.data
        user.username = form.username.data
        user.confirmed = form.confirmed.data
        user.role = Role.query.get(form.role.data)
        user.name = form.name.data
        user.location = form.location.data
        user.about_me = form.about_me.data
        db.session.add(user)
        flash(u'该个人资料已更新。')
        return redirect(url_for('.user', username=user.username))
    form.email.data = user.email
    form.username.data = user.username
    form.confirmed.data = user.confirmed
    form.role.data = user.role_id
    form.name.data = user.name
    form.location.data = user.location
    form.about_me.data = user.about_me
    return render_template('edit_profile.html', form=form, user=user)


@main.route('/post/<int:id>', methods=['GET', 'POST'])
def post(id):
    post = Post.query.get_or_404(id)
    form = CommentForm()
    if form.validate_on_submit():
        comment = Comment(body=form.body.data,
                          post=post,
                          author=current_user._get_current_object())
        db.session.add(comment)
        flash(u'你的评论已发布。')
        return redirect(url_for('.post', id=post.id, page=-1))
    page = request.args.get('page', 1, type=int)
    if page == -1:
        page = (post.comments.count() - 1) / \
               current_app.config['SONGXUE_COMMENTS_PER_PAGE'] + 1
    pagination = post.comments.order_by(Comment.timestamp.asc()).paginate(
        page, per_page=current_app.config['SONGXUE_COMMENTS_PER_PAGE'],
        error_out=False)
    comments = pagination.items
    return render_template('post.html', posts=[post], form=form,
                           comments=comments, pagination=pagination)


@main.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    post = Post.query.get_or_404(id)
    if current_user != post.author and \
            not current_user.can(Permission.ADMINISTER):
        abort(403)
    form = PostForm()
    if form.validate_on_submit():
        post.body = form.body.data
        db.session.add(post)
        flash(u'该 post 已更新。')
        return redirect(url_for('.post', id=post.id))
    form.body.data = post.body
    return render_template('edit_post.html', form=form)


@main.route('/follow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def follow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash(u'错误的用户。')
        return redirect(url_for('.index'))
    if current_user.is_following(user):
        flash(u'你已经关注了该用户。')
        return redirect(url_for('.user', username=username))
    current_user.follow(user)
    flash(u'你现在关注了 %s.' % username)
    return redirect(url_for('.user', username=username))


@main.route('/unfollow/<username>')
@login_required
@permission_required(Permission.FOLLOW)
def unfollow(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash(u'错误的用户。')
        return redirect(url_for('.index'))
    if not current_user.is_following(user):
        flash(u'你已经取消了对该用户的关注')
        return redirect(url_for('.user', username=username))
    current_user.unfollow(user)
    flash(u'你不能再关注 %s 了。' % username)
    return redirect(url_for('.user', username=username))


@main.route('/followers/<username>')
def followers(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash(u'错误的用户。')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followers.paginate(
        page, per_page=current_app.config['SONGXUE_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.follower, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title="Followers of",
                           endpoint='.followers', pagination=pagination,
                           follows=follows)


@main.route('/followed-by/<username>')
def followed_by(username):
    user = User.query.filter_by(username=username).first()
    if user is None:
        flash(u'错误的用户。')
        return redirect(url_for('.index'))
    page = request.args.get('page', 1, type=int)
    pagination = user.followed.paginate(
        page, per_page=current_app.config['SONGXUE_FOLLOWERS_PER_PAGE'],
        error_out=False)
    follows = [{'user': item.followed, 'timestamp': item.timestamp}
               for item in pagination.items]
    return render_template('followers.html', user=user, title="Followed by",
                           endpoint='.followed_by', pagination=pagination,
                           follows=follows)


@main.route('/all')
@login_required
def show_all():
    resp = make_response(redirect(url_for('.post_index')))
    resp.set_cookie('show_followed', '', max_age=30 * 24 * 60 * 60)
    return resp


@main.route('/followed')
@login_required
def show_followed():
    resp = make_response(redirect(url_for('.post_index')))
    resp.set_cookie('show_followed', '1', max_age=30 * 24 * 60 * 60)
    return resp


@main.route('/moderate/comments')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_comments():
    page = request.args.get('page', 1, type=int)
    pagination = Comment.query.order_by(Comment.timestamp.desc()) \
        .paginate(page, per_page=current_app.config['SONGXUE_COMMENTS_PER_PAGE'],
                  error_out=False)
    comments = pagination.items
    return render_template('moderate/comments.html', comments=comments,
                           pagination=pagination, page=page)


@main.route('/moderate/comment/enable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_comment_enable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = False
    db.session.add(comment)
    return redirect(url_for('.moderate_comments',
                            page=request.args.get('page', 1, type=int)))


@main.route('/moderate/comment/disable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_COMMENTS)
def moderate_comment_disable(id):
    comment = Comment.query.get_or_404(id)
    comment.disabled = True
    db.session.add(comment)
    return redirect(url_for('.moderate_comments',
                            page=request.args.get('page', 1, type=int)))


@main.route('/moderate/users')
@login_required
@permission_required(Permission.MODERATE_USERS)
def moderate_users():
    page = request.args.get('page', 1, type=int)
    role = Role.query.filter_by(permissions=7).first()  # 普通用户role_id
    pagination = User.query.filter_by(role_id=role.id) \
        .order_by(User.last_seen.desc()) \
        .paginate(page, per_page=current_app.config['SONGXUE_COMMENTS_PER_PAGE'],
                  error_out=False)
    users = pagination.items
    return render_template('moderate/users.html', users=users,
                           pagination=pagination, page=page)


@main.route('/moderate/user/enable/<int:id>')
@login_required
@permission_required(Permission.MODERATE_USERS)
def moderate_user_enable(id):
    user = User.query.get_or_404(id)

    # TODO-cott: 在models.py中将permissions设置为常数
    role = Role.query.filter_by(permissions=15).first()
    user.role_id = role.id  # 设置用户为发布者

    db.session.add(user)
    return redirect(url_for('.moderate_users',
                            page=request.args.get('page', 1, type=int)))


# @main.route('/moderate/user/disable/<int:id>')
# @login_required
# @permission_required(Permission.MODERATE_USERS)
# def moderate_user_disable(id):
# user = User.query.get_or_404(id)
#
#     # TODO-cott: 在models.py中将permissions设置为常数
#     user.role_id = Role.query.filter_by(permissions = 7).first()  # 设置用户为普通用户
#
#     db.session.add(user)
#     return redirect(url_for('.moderate_users',
#                             page = request.args.get('page', 1, type = int)))
