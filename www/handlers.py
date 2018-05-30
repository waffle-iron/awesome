#!/usr/bin/env python3
# -*- coding: utf-8 -*-

__author__ = 'Michael Liao'

' url handlers '

import asyncio
import base64
import hashlib
import json
import logging
import re
import time

import aiohttp_jinja2
from aiohttp import web

import markdown2
from apis import (APIPermissionError, APIResourceNotFoundError, APIValueError,
                  Page)
from config import configs
from models import Blog, Comment, User, next_id

COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret
routes = web.RouteTableDef()


def check_admin(request):
    if request.__user__ is None or not request.__user__.admin:
        raise APIPermissionError()


def get_page_index(page_str):
    p = 1
    try:
        p = int(page_str)
    except ValueError as e:
        pass
    if p < 1:
        p = 1
    return p


def user2cookie(user, max_age):
    '''
    Generate cookie str by user.
    '''
    # build cookie string by: id-expires-sha1
    expires = str(int(time.time() + max_age))
    s = '%s-%s-%s-%s' % (user.id, user.passwd, expires, _COOKIE_KEY)
    L = [user.id, expires, hashlib.sha1(s.encode('utf-8')).hexdigest()]
    return '-'.join(L)


def text2html(text):
    lines = map(lambda s: '<p>%s</p>' % s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'),
                filter(lambda s: s.strip() != '', text.split('\n')))
    return ''.join(lines)


async def cookie2user(cookie_str):
    '''
    Parse cookie and load user if cookie is valid.
    '''
    if not cookie_str:
        return None
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        uid, expires, sha1 = L
        if int(expires) < time.time():
            return None
        user = await User.find(uid)
        if user is None:
            return None
        s = '%s-%s-%s-%s' % (uid, user.passwd, expires, _COOKIE_KEY)
        if sha1 != hashlib.sha1(s.encode('utf-8')).hexdigest():
            logging.info('invalid sha1')
            return None
        user.passwd = '******'
        return user
    except Exception as e:
        logging.exception(e)
        return None


@routes.get('/')
@aiohttp_jinja2.template('blogs.html')
async def index(request):
    num = await Blog.findNumber('count(id)')
    page = Page(num)
    if num == 0:
        blogs = []
    else:
        blogs = await Blog.findAll(orderBy='created_at desc', limit=(page.offset, page.limit))
    return {
        '__user__': request.get('__user__'),
        'page': page,
        'blogs': blogs
    }


@routes.get('/blog/{id}')
@aiohttp_jinja2.template('blog.html')
async def get_blog(request):
    id = request.match_info['id']
    blog = await Blog.find(id)
    comments = await Comment.findAll('blog_id=?', [id], orderBy='created_at desc')
    for c in comments:
        c.html_content = text2html(c.content)
    blog.html_content = markdown2.markdown(blog.content)
    return {
        '__user__': request.get('__user__'),
        'blog': blog,
        'comments': comments
    }


@routes.get('/register')
@aiohttp_jinja2.template('register.html')
async def register(request):
    return {'__user__': request.get('__user__')}


@routes.get('/signin')
@aiohttp_jinja2.template('signin.html')
async def signin(request):
    return {'__user__': request.get('__user__')}


@routes.get('/signout')
async def signout(request):
    referer = request.headers.get('Referer')
    r = web.HTTPFound(referer or '/')
    r.set_cookie(COOKIE_NAME, '-deleted-', max_age=0, httponly=True)
    r.set_cookie('userID', '', max_age=0, httponly=False)
    logging.info('user signed out.')
    return r


@routes.post('/api/authenticate')
async def authenticate(request):
    data = await request.json()
    email = data.get('email')
    passwd = data.get('passwd')
    if not email:
        raise APIValueError('email', 'Invalid email.')
    if not passwd:
        raise APIValueError('passwd', 'Invalid password.')
    users = await User.findAll('email=?', [email])
    if len(users) == 0:
        raise APIValueError('email', 'Email not exist.')
    user = users[0]
    # check passwd:
    sha1 = hashlib.sha1()
    sha1.update(user.id.encode('utf-8'))
    sha1.update(b':')
    sha1.update(passwd.encode('utf-8'))
    if user.passwd != sha1.hexdigest():
        raise APIValueError('passwd', 'Invalid password.')
    # authenticate ok, set cookie:
    r = web.Response()
    r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
    r.set_cookie('userID', user.id, max_age=86400, httponly=False)
    user.passwd = '******'
    r.content_type = 'application/json'
    r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
    return r


@routes.get('/manage/')
async def manage(request):
    return web.HTTPFound('/manage/blogs')


@routes.get('/manage/blogs')
@aiohttp_jinja2.template('manage_blogs.html')
async def manage_blogs(request, page='1'):
    return {
        '__user__': request.get('__user__'),
        'page_index': get_page_index(page)
    }


@routes.get('/manage/blogs/create')
@aiohttp_jinja2.template('manage_blogs.html')
async def manage_create_blog(request):
    return {
        '__user__': request.get('__user__'),
        'id': '',
        'action': '/api/blogs'
    }


@routes.get('/manage/blogs/edit/{id}')
@aiohttp_jinja2.template('manage_blog_edit.html')
async def manage_edit_blog(request):
    id = request.match_info['id']
    return {
        '__user__': request.get('__user__'),
        'id': id,
        'action': '/api/blogs/%s' % id
    }


@routes.get('/manage/users')
@aiohttp_jinja2.template('manage_users.html')
async def manage_users(request, page='1'):
    return {
        '__user__': request.get('__user__'),
        'page_index': get_page_index(page)
    }


@routes.get('/api/users')
async def api_get_users(request, page='1'):
    page_index = get_page_index(page)
    num = await User.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, users=())
    users = await User.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    for u in users:
        u.passwd = '******'
    return dict(page=p, users=users)


@routes.get('/api/blogs')
async def api_blogs(request, page='1'):
    page_index = get_page_index(page)
    num = await Blog.findNumber('count(id)')
    p = Page(num, page_index)
    if num == 0:
        return dict(page=p, blogs=())
    blogs = await Blog.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
    return web.json_response({'page': p.__dict__, 'blogs': blogs})


@routes.get('/api/blogs/{id}')
async def api_get_blog(request):
    id = request.match_info['id']
    blog = await Blog.find(id)
    return blog


@routes.post('/api/blogs')
async def api_create_blog(request, name, summary, content):
    check_admin(request)
    data = await request.json()
    name = data.get('name')
    summary = data.get('summary')
    content = data.get('content')
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    blog = Blog(user_id=request.__user__.id, user_name=request.__user__.name, user_image=request.__user__.image,
                name=name.strip(), summary=summary.strip(), content=content.strip())
    await blog.save()
    return blog


@routes.post('/api/blogs/{id}')
async def api_update_blog(request, name, summary, content):
    check_admin(request)
    data = await request.json()
    name = data.get('name')
    summary = data.get('summary')
    content = data.get('content')
    id = request.match_info['id']
    blog = await Blog.find(id)
    if not name or not name.strip():
        raise APIValueError('name', 'name cannot be empty.')
    if not summary or not summary.strip():
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content or not content.strip():
        raise APIValueError('content', 'content cannot be empty.')
    blog.name = name.strip()
    blog.summary = summary.strip()
    blog.content = content.strip()
    await blog.update()
    return blog


@routes.post('/api/blogs/{id}/delete')
async def api_delete_blog(request):
    check_admin(request)
    id = request.match_info['id']
    blog = await Blog.find(id)
    await blog.remove()
    return dict(id=id)


# _RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
# _RE_SHA1 = re.compile(r'^[0-9a-f]{40}$')


# @post('/api/users')
# async def api_register_user(*, email, name, passwd):
#     if not name or not name.strip():
#         raise APIValueError('name')
#     if not email or not _RE_EMAIL.match(email):
#         raise APIValueError('email')
#     if not passwd or not _RE_SHA1.match(passwd):
#         raise APIValueError('passwd')
#     users = await User.findAll('email=?', [email])
#     if len(users) > 0:
#         raise APIError('register:failed', 'email', 'Email is already in use.')
#     uid = next_id()
#     sha1_passwd = '%s:%s' % (uid, passwd)
#     user = User(id=uid, name=name.strip(), email=email, passwd=hashlib.sha1(sha1_passwd.encode('utf-8')).hexdigest(),
#                 image='https://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email.encode('utf-8')).hexdigest())
#     await user.save()
#     # make session cookie:
#     r = web.Response()
#     r.set_cookie(COOKIE_NAME, user2cookie(user, 86400), max_age=86400, httponly=True)
#     r.set_cookie('userID', user.id, max_age=86400, httponly=False)
#     user.passwd = '******'
#     r.content_type = 'application/json'
#     r.body = json.dumps(user, ensure_ascii=False).encode('utf-8')
#     return r


# @routes.get('/manage/comments')
# @aiohttp_jinja2.template('manage_comments.html')
# async def manage_comments(request, page='1'):
#     return {'page_index': get_page_index(page)}


# @routes.get('/api/comments')
# async def api_comments(request, page='1'):
#     page_index = get_page_index(page)
#     num = await Comment.findNumber('count(id)')
#     p = Page(num, page_index)
#     if num == 0:
#         return dict(page=p, comments=())
#     comments = await Comment.findAll(orderBy='created_at desc', limit=(p.offset, p.limit))
#     return dict(page=p, comments=comments)


# @post('/api/blogs/{id}/comments')
# async def api_create_comment(id, request, *, content):
#     user = request.__user__
#     if user is None:
#         raise APIPermissionError('Please signin first.')
#     if not content or not content.strip():
#         raise APIValueError('content')
#     blog = await Blog.find(id)
#     if blog is None:
#         raise APIResourceNotFoundError('Blog')
#     comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image, content=content.strip())
#     await comment.save()
#     return comment


# @post('/api/comments/{id}/delete')
# async def api_delete_comments(id, request):
#     check_admin(request)
#     c = await Comment.find(id)
#     if c is None:
#         raise APIResourceNotFoundError('Comment')
#     await c.remove()
#     return dict(id=id)
