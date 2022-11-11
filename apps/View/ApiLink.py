#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
import datetime, urlparse,hashlib
try:
    import json
except ImportError:
    import simplejson as json

import web
from google.appengine.api import memcache
from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from apps.utils import new_secret_key
from config import *


__auth_key__ = 'librz.link.luck!'





'''
同步用户
'''
class ApiSyncUser(BaseHandler):
    __url__ = "/api/v2/sync"
    def __init__(self):
        super(ApiSyncUser, self).__init__(setLang=False)
        self.now = datetime.datetime.utcnow()

    def POST(self):
        webInput = web.input()
        key = webInput.get('key')
        res = {"status": "ok", "msg": ""}
        if key != __auth_key__: # key 有问题不抛错误信息
            return ""

        user_name = webInput.get('user_name')
        to_email = webInput.get("to_email")
        send_days = webInput.get("send_days")
        expiration_days = int(webInput.get("expiration_days"))

        # 用户必须用户名和 邮箱
        if not user_name or not to_email:
            res['status'] = "failed"
            res["msg"] = "user or email is empty"
            return json.dumps(res)

        if len(send_days) != 0:
            send_days = send_days.split(',')
        else:
            send_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        if expiration_days > 366 or expiration_days == 0:
            expires_day = datetime.datetime.utcnow() + datetime.timedelta(days=30)
        else:
            expires_day = datetime.datetime.utcnow() + datetime.timedelta(days=expiration_days)


        u = KeUser.all().filter("name = ",user_name ).get()

        if not u:
            myfeeds = Book(title=MY_FEEDS_TITLE, description=MY_FEEDS_DESC,
                           builtin=False, keep_image=True, oldest_article=7,
                           needs_subscription=False, separate=False)
            myfeeds.put()
            secret_key = new_secret_key()
            au = KeUser(name=user_name, passwd=hashlib.md5(to_email + secret_key).hexdigest(),
                        kindle_email=to_email, enable_send=True, send_time=8, timezone=TIMEZONE,
                        send_days=send_days,book_type="epub", device='kindle', expires=expires_day, ownfeeds=myfeeds,
                        merge_books=False, secret_key=secret_key, expiration_days=expiration_days)
            au.put()
        else:
            res['msg'] = 'username alread exist!'
            res['status'] = 'failed'

        return json.dumps(res)

'''
同步订阅
'''
class ApiFeedRSS(BaseHandler):
    __url__ = "/api/v2/rss/(.*)"
    def __init__(self):
        super(ApiFeedRSS, self).__init__(setLang=False)
        self.now = datetime.datetime.utcnow()

    def GET(self):
        web.header('Content-Type', 'application/json')

    def POST(self,mgrType):  # 添加自定义RSS
        res = {"status": "ok", "msg": ""}
        webInput = web.input()
        user_name = webInput.get('user_name')
        if mgrType.lower() == 'myrss':
            if not user_name:
                return ""
            user = KeUser.all().filter("name = ", user_name).get()
            myfeeds = user.ownfeeds.feeds if user.ownfeeds else None
            data = []
            for feed in myfeeds:
                data.append({"title":feed.title,"url":feed.url,"feedid":feed.key().id()})
            return json.dumps(data)
        elif mgrType.lower() == 'pub':  #RSS公共库
            shared_data = []
            for d in LibRss.all().fetch(limit=10000):
                shared_data.append(
                    {'feedid': d.key().id(), 't': d.title, 'u': d.url, 'f': d.isfulltext, 'c': d.category,
                     's': d.subscribed,
                     'd': int((d.created_time - datetime.datetime(1970, 1, 1)).total_seconds())})

            return json.dumps(shared_data)

        elif mgrType.lower() == 'add':  # 我的订阅更新
            user = KeUser.all().filter("name = ", user_name).get()
            titles = webInput.get('rss_ids')
            if len(titles) != 0:
                rss_ids = titles.split(",")
                for rss_id in rss_ids:
                    rss = LibRss.get_by_id(int(rss_id))
                    if rss is None:
                        continue
                        # 判断是否重复
                    ownUrls = [rss.url for item in user.ownfeeds.feeds]
                    if rss.url in ownUrls:
                        continue
                    if not rss.url.lower().startswith('http'):  # http and https
                        url = 'https://' + url

                    fd = Feed(title=rss.title, url=rss.url, book=user.ownfeeds, isfulltext=rss.isfulltext,
                              time=datetime.datetime.utcnow())
                    fd.put()

                    memcache.delete('%d.feedscount' % user.ownfeeds.key().id())
                return json.dumps(res)
