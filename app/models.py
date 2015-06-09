# -*- coding:utf-8 -*-

from datetime import datetime
import hashlib
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from markdown import markdown
import bleach
from flask import current_app, request, url_for
from flask.ext.login import UserMixin, AnonymousUserMixin
from app.exceptions import ValidationError
from . import db, login_manager


class Permission:
    """权限常量
    0b00000001 == 0x01
    0b00000010 == 0x02
    0b00000100 == 0x04
    0b00001000 == 0x08
    0b00010000 == 0x10
    0b00100000 == 0x20
    0b01000000 == 0x40
    0b10000000 == 0x80
    """
    FOLLOW = 0x01  # 关注
    COMMENT = 0x02  # 评论
    WRITE_ARTICLES = 0x04  # 发推（目前停用）
    PUBLISH_COURSES = 0x08  # 发布课程
    MODERATE_COMMENTS = 0x10  # 审核评论
    MODERATE_USERS = 0x20  # 审核用户
    ADMINISTER = 0x80  # 管理员


class Role(db.Model):
    """角色表
    User 普通用户
    Publisher 发布者
    Moderator 审查者
    Administrator 管理者
    """
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), unique=True)
    default = db.Column(db.Boolean, default=False, index=True)
    permissions = db.Column(db.Integer)
    users = db.relationship('User', backref='role', lazy='dynamic')

    @staticmethod
    def insert_roles():
        roles = {
            'User': (Permission.FOLLOW |
                     Permission.COMMENT |
                     Permission.WRITE_ARTICLES, True),
            'Publisher': (Permission.FOLLOW |
                          Permission.COMMENT |
                          Permission.WRITE_ARTICLES |
                          Permission.PUBLISH_COURSES, False),
            'Moderator': (Permission.FOLLOW |
                          Permission.COMMENT |
                          Permission.WRITE_ARTICLES |
                          Permission.PUBLISH_COURSES |
                          Permission.MODERATE_COMMENTS |
                          Permission.MODERATE_USERS, False),
            'Administrator': (0xff, False)
        }
        for r in roles:
            role = Role.query.filter_by(name=r).first()
            if role is None:
                role = Role(name=r)
            role.permissions = roles[r][0]
            role.default = roles[r][1]
            db.session.add(role)
        db.session.commit()

    def __repr__(self):
        return '<Role %r>' % self.name


class Follow(db.Model):
    __tablename__ = 'follows'
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                            primary_key=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                            primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class Application(db.Model):
    __tablename__ = 'applications'
    # id = db.Column(db.Integer, primary_key = True)
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'), primary_key=True)
    applicant_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    name = db.Column(db.String)
    telephone = db.Column(db.String)
    address = db.Column(db.String)
    # status = db.Column(db.Integer)  # 报名表状态
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    @staticmethod
    def generate_fake(count=100):
        # TODO-cott: 模拟数据待完成
        pass

    def to_json(self):
        # TODO-cott: 完成该API
        json_post = {}
        return json_post


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(64), unique=True, index=True)
    username = db.Column(db.String(64), unique=True, index=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    password_hash = db.Column(db.String(128))
    confirmed = db.Column(db.Boolean, default=False)
    name = db.Column(db.String(64))
    location = db.Column(db.String(64))
    about_me = db.Column(db.Text())
    member_since = db.Column(db.DateTime(), default=datetime.utcnow)
    last_seen = db.Column(db.DateTime(), default=datetime.utcnow)
    avatar_hash = db.Column(db.String(32))
    posts = db.relationship('Post', backref='author', lazy='dynamic')
    courses = db.relationship('Course', backref='publisher', lazy='dynamic')
    followed = db.relationship('Follow',
                               foreign_keys=[Follow.follower_id],
                               backref=db.backref('follower', lazy='joined'),
                               lazy='dynamic',
                               cascade='all, delete-orphan')
    followers = db.relationship('Follow',
                                foreign_keys=[Follow.followed_id],
                                backref=db.backref('followed', lazy='joined'),
                                lazy='dynamic',
                                cascade='all, delete-orphan')
    comments = db.relationship('Comment', backref='author', lazy='dynamic')
    applied = db.relationship('Application',
                              foreign_keys=[Application.applicant_id],
                              backref=db.backref('applicant', lazy='joined'),
                              lazy='dynamic',
                              cascade='all, delete-orphan')

    @staticmethod
    def generate_fake(count=100):
        from sqlalchemy.exc import IntegrityError
        from random import seed
        import forgery_py

        seed()
        for i in range(count):
            u = User(email=forgery_py.internet.email_address(),
                     username=forgery_py.internet.user_name(True),
                     password=forgery_py.lorem_ipsum.word(),
                     confirmed=True,
                     name=forgery_py.name.full_name(),
                     location=forgery_py.address.city(),
                     about_me=forgery_py.lorem_ipsum.sentence(),
                     member_since=forgery_py.date.date(True))
            db.session.add(u)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()

    @staticmethod
    def add_self_follows():
        for user in User.query.all():
            if not user.is_following(user):
                user.follow(user)
                db.session.add(user)
                db.session.commit()

    def __init__(self, **kwargs):
        super(User, self).__init__(**kwargs)
        if self.role is None:
            if self.email == current_app.config['SONGXUE_ADMIN']:
                self.role = Role.query.filter_by(permissions=0xff).first()
            if self.role is None:
                self.role = Role.query.filter_by(default=True).first()
        if self.email is not None and self.avatar_hash is None:
            self.avatar_hash = hashlib.md5(
                self.email.encode('utf-8')).hexdigest()
        self.followed.append(Follow(followed=self))

    @property
    def password(self):
        raise AttributeError('password is not a readable attribute')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_confirmation_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'confirm': self.id})

    def confirm(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('confirm') != self.id:
            return False
        self.confirmed = True
        db.session.add(self)
        return True

    def generate_reset_token(self, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'reset': self.id})

    def reset_password(self, token, new_password):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('reset') != self.id:
            return False
        self.password = new_password
        db.session.add(self)
        return True

    def generate_email_change_token(self, new_email, expiration=3600):
        s = Serializer(current_app.config['SECRET_KEY'], expiration)
        return s.dumps({'change_email': self.id, 'new_email': new_email})

    def change_email(self, token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return False
        if data.get('change_email') != self.id:
            return False
        new_email = data.get('new_email')
        if new_email is None:
            return False
        if self.query.filter_by(email=new_email).first() is not None:
            return False
        self.email = new_email
        self.avatar_hash = hashlib.md5(
            self.email.encode('utf-8')).hexdigest()
        db.session.add(self)
        return True

    def can(self, permissions):
        return self.role is not None and \
               (self.role.permissions & permissions) == permissions

    def is_administrator(self):
        return self.can(Permission.ADMINISTER)

    def ping(self):
        self.last_seen = datetime.utcnow()
        db.session.add(self)

    def gravatar(self, size=100, default='identicon', rating='g'):
        if request.is_secure:
            url = 'https://secure.gravatar.com/avatar'
        else:
            url = 'http://www.gravatar.com/avatar'
        hash = self.avatar_hash or hashlib.md5(
            self.email.encode('utf-8')).hexdigest()
        return '{url}/{hash}?s={size}&d={default}&r={rating}'.format(
            url=url, hash=hash, size=size, default=default, rating=rating)

    def follow(self, user):
        if not self.is_following(user):
            f = Follow(follower=self, followed=user)
            db.session.add(f)

    def unfollow(self, user):
        f = self.followed.filter_by(followed_id=user.id).first()
        if f:
            db.session.delete(f)

    def is_following(self, user):
        return self.followed.filter_by(
            followed_id=user.id).first() is not None

    def is_followed_by(self, user):
        return self.followers.filter_by(
            follower_id=user.id).first() is not None

    def is_applied_by(self, course):
        return self.applied.filter_by(
            course_id=course.id).first() is not None

    @property
    def followed_posts(self):
        return Post.query.join(Follow, Follow.followed_id == Post.author_id) \
            .filter(Follow.follower_id == self.id)

    @property
    def followed_courses(self):
        return Course.query.join(Follow, Follow.followed_id == Course.author_id) \
            .filter(Follow.follower_id == self.id)

    def to_json(self):
        json_user = {
            'url': url_for('api.get_post', id=self.id, _external=True),
            'username': self.username,
            'member_since': self.member_since,
            'last_seen': self.last_seen,
            'posts': url_for('api.get_user_posts', id=self.id, _external=True),
            'followed_posts': url_for('api.get_user_followed_posts',
                                      id=self.id, _external=True),
            'post_count': self.posts.count()
        }
        return json_user

    def generate_auth_token(self, expiration):
        s = Serializer(current_app.config['SECRET_KEY'],
                       expires_in=expiration)
        return s.dumps({'id': self.id}).decode('ascii')

    @staticmethod
    def verify_auth_token(token):
        s = Serializer(current_app.config['SECRET_KEY'])
        try:
            data = s.loads(token)
        except:
            return None
        return User.query.get(data['id'])

    def __repr__(self):
        return '<User %r>' % self.username


class AnonymousUser(AnonymousUserMixin):
    def can(self, permissions):
        return False

    def is_applied_by(self, course):
        return False

    def is_administrator(self):
        return False

    def get_id(self):
        return -1


login_manager.anonymous_user = AnonymousUser


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Course(db.Model):
    __tablename__ = 'courses'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String)
    name = db.Column(db.String)
    brief = db.Column(db.String)  # 摘要
    detailed = db.Column(db.Text)  # 详细描述
    price = db.Column(db.Integer)  # 价格
    contact = db.Column(db.String)  # 联系人
    telephone = db.Column(db.String)  # 联系电话
    category = db.Column(db.String)  # TODO-cott: 优化类别为映射表形式
    company = db.Column(db.String)  # 公司名称
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)  # 时间戳
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comments = db.relationship('Comment', backref='course', lazy='dynamic')
    apply = db.relationship('Application',
                            foreign_keys=[Application.course_id],
                            backref=db.backref('apply_course', lazy='joined'),
                            lazy='dynamic',
                            cascade='all, delete-orphan')

    @staticmethod
    def generate_fake(count=100):
        # TODO-cott: 模拟数据待完成
        pass

    def is_appled_by(self, user):
        return self.apply.filter_by(
            applicant_id=user.id).first() is not None

    def to_json(self):
        # TODO-cott: 完成该API
        json_post = {}
        return json_post


class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    comments = db.relationship('Comment', backref='post', lazy='dynamic')

    @staticmethod
    def generate_fake(count=100):
        from random import seed, randint
        import forgery_py

        seed()
        user_count = User.query.count()
        for i in range(count):
            u = User.query.offset(randint(0, user_count - 1)).first()
            p = Post(body=forgery_py.lorem_ipsum.sentences(randint(1, 5)),
                     timestamp=forgery_py.date.date(True),
                     author=u)
            db.session.add(p)
            db.session.commit()

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'blockquote', 'code',
                        'em', 'i', 'li', 'ol', 'pre', 'strong', 'ul',
                        'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'img',
                        'hr']
        target.body_html = markdown(value, output_format='html')
        # target.body_html = bleach.linkify(bleach.clean(
        # markdown(value, output_format='html'),
        # tags=allowed_tags, strip=True))

    def to_json(self):
        json_post = {
            'url': url_for('api.get_post', id=self.id, _external=True),
            'body': self.body,
            'body_html': self.body_html,
            'timestamp': self.timestamp,
            'author': url_for('api.get_user', id=self.author_id,
                              _external=True),
            'comments': url_for('api.get_post_comments', id=self.id,
                                _external=True),
            'comment_count': self.comments.count()
        }
        return json_post

    @staticmethod
    def from_json(json_post):
        body = json_post.get('body')
        if body is None or body == '':
            raise ValidationError('post does not have a body')
        return Post(body=body)


db.event.listen(Post.body, 'set', Post.on_changed_body)


class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.Text)
    body_html = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
    disabled = db.Column(db.Boolean)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    course_id = db.Column(db.Integer, db.ForeignKey('courses.id'))
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'))

    @staticmethod
    def on_changed_body(target, value, oldvalue, initiator):
        allowed_tags = ['a', 'abbr', 'acronym', 'b', 'code', 'em', 'i',
                        'strong']
        target.body_html = bleach.linkify(bleach.clean(
            markdown(value, output_format='html'),
            tags=allowed_tags, strip=True))

    def to_json(self):
        json_comment = {
            'url': url_for('api.get_comment', id=self.id, _external=True),
            'post': url_for('api.get_post', id=self.post_id, _external=True),
            'body': self.body,
            'body_html': self.body_html,
            'timestamp': self.timestamp,
            'author': url_for('api.get_user', id=self.author_id,
                              _external=True),
        }
        return json_comment

    @staticmethod
    def from_json(json_comment):
        body = json_comment.get('body')
        if body is None or body == '':
            raise ValidationError('comment does not have a body')
        return Comment(body=body)


db.event.listen(Comment.body, 'set', Comment.on_changed_body)


class TermRelationship(db.Model):
    """分类关系表"""
    __tablename__ = "term_relationships"
    object_id = db.Column(db.Integer, primary_key=True)
    term_taxonomy_id = db.Column(db.Integer,
                                 db.ForeignKey('term_taxonomy.term_taxonomy_id'),
                                 default='0')
    term_order = db.Column(db.Integer)


class TermTaxonomy(db.Model):
    """分类表"""
    __tablename__ = "term_taxonomy"
    term_taxonomy_id = db.Column(db.Integer, primary_key=True)
    term_id = db.Column(db.Integer, db.ForeignKey('terms.term_id'),
                        unique=True, nullable=False, default='0')
    taxonomy = db.Column(db.String, nullable=False, default='')
    parent = db.Column(db.Integer, nullable=False, default='0')
    count = db.Column(db.Integer, nullable=False, default='0')


class Terms(db.Model):
    """条目表"""
    __tablename__ = "terms"
    term_id = db.Column(db.Integer, primary_key=True)  # 有必要的话，将类型换为BIGINT
    name = db.Column(db.String, nullable=False, default='')
    slug = db.Column(db.String, nullable=False, default='')
    term_group = db.Column(db.Integer)
    term_taxonomy = db.relationship('TermTaxonomy', backref='term', lazy='dynamic')