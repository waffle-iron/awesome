#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import aiohttp_jinja2
import jinja2
from aiohttp import web
from jinja2 import Environment, FileSystemLoader

import handlers
import orm
import uvloop
from config import configs
from handlers import COOKIE_NAME, cookie2user

parser = argparse.ArgumentParser(description="aiohttp server")
parser.add_argument('--path')
parser.add_argument('--port')
parent = Path('.').parent
parent = str(parent.absolute())
sys.path.insert(0, parent)
logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger()
log.setLevel(logging.DEBUG)


@web.middleware
async def logger_factory(request, handler):
    logging.info('Request: %s %s' % (request.method, request.path))
    return await handler(request)


@web.middleware
async def auth_factory(request, handler):
    logging.info('check user: %s %s' % (request.method, request.path))
    request.__user__ = None
    cookie_str = request.cookies.get(COOKIE_NAME)
    if cookie_str:
        user = await cookie2user(cookie_str)
        if user:
            logging.info('set current user: %s' % user.email)
            request['__user__'] = user
    if request.path.startswith('/manage/') and (request.get('__user__') is None or not request.get('__user__').admin):
        return web.HTTPFound('/signin')
    return await handler(request)


def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)


async def init(loop):
    await orm.create_pool(loop=loop, **configs.db)
    PROJECT_ROOT = Path(__file__).parent
    templates = PROJECT_ROOT / 'templates'
    app = web.Application(loop=loop, middlewares=[logger_factory, auth_factory])
    loader = jinja2.FileSystemLoader([str(templates)])
    aiohttp_jinja2.setup(app, loader=loader, filters=dict(datetime=datetime_filter))
    app.add_routes(handlers.routes)
    return app

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
loop = asyncio.get_event_loop()
if __name__ == "__main__":
    args = parser.parse_args()
    app = loop.run_until_complete(init(loop))
    web.run_app(app, path=args.path, port=args.port)
