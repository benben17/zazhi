#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version

import StringIO
import datetime
import hashlib
from apps.AESCipher import Encipher
try:
    import json
except ImportError:
    import simplejson as json
from collections import defaultdict
import web
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from apps.BaseHandler import BaseHandler
from apps.dbModels import *
from apps.utils import new_secret_key
from config import *
from PIL import Image
from google.appengine.api.datastore_errors import NeedIndexError

'''
同步用户
'''



class SyncUser(BaseHandler):
    __url__ = "/api/v2/sync/user/(.*)"
    def __init__(self):
        super(SyncUser, self).__init__(setLang=False)
        self.key = web.input().get('key')
        self.res = {"status": "ok", "msg": ""}
        self.webInput = web.input()

    def POST(self,mgrType):
        if not self.check_api_key(self.key):
            return self.check_api_key(self.key)
        res = {}
        webInput = web.input()
        user_name = webInput.get('user_name')
        if mgrType.lower() == 'add':
            book_name = webInput.get('book_name') if webInput.get('book_name') else MY_FEEDS_TITLE
            to_email = webInput.get("to_email")
            expiration_days = int(webInput.get('expiration_days')) if webInput.get('expiration_days') else 30
            # 用户必须用户名和 邮箱
            if not user_name or not to_email:
                self.res['status'] = "failed"
                self.res["msg"] = "user or email is empty"
                return json.dumps(self.res)

            # 判断传值是否正确，不正确默认
            u = KeUser.all().filter("name = ",user_name ).get()
            if not u:
                myfeeds = Book(title=book_name, description=MY_FEEDS_DESC,
                               builtin=False, keep_image=True, oldest_article=7,
                               needs_subscription=False, separate=False)
                myfeeds.put()
                secret_key = new_secret_key()
                au = KeUser(name=user_name, passwd=hashlib.md5(to_email + secret_key).hexdigest(),
                            kindle_email=to_email, enable_send=True, send_time=8, timezone=TIMEZONE,
                            send_days=DEFAULT_SEND_DAYS,book_type="epub", device='kindle', ownfeeds=myfeeds,
                            remove_hyperlinks='image',book_mode='periodical',titlefmt='YY-MM-DD',
                            merge_books=False, secret_key=secret_key, expiration_days=expiration_days)
                if webInput.get('expires') is None:
                    au.expires
                else:
                    au.expires = datetime.datetime.utcnow() + datetime.timedelta(days=expiration_days)
                au.put()

                book_rss = au.ownfeeds
                book_rss.language = webInput.get("lng", "zh-cn")
                book_rss.oldest_article = int(webInput.get('oldest', 7))
                book_rss.users = [au.name]
                book_rss.put()
                book = au.ownfeeds
                book.put()

            else:
                self.res['msg'] = 'username alread exist!'
                self.res['status'] = 'failed'

            return json.dumps(self.res)
        elif mgrType.lower() == 'seting':  # 每周 发送  oldest_article = 7 每天 发送1
            user = KeUser.all().filter("name = ", user_name).get()
            if not user:
                self.res['status'] = 'failed'
                return json.dumps(self.res)
            book = user.ownfeeds
            if self.webInput.get('frequency') == 'week':  # 每周发送  oldest_article = 7 每天 发送1
                book.oldest_article = 1
            elif self.webInput.get('frequency') == 'every':
                book.oldest_article = 7
            book.put()
            if not self.webInput.get('send_day'):  # 用户定义 哪天发送 不定义默认为周五 早上8点
                user.send_days = ['Friday']
            else:
                if self.webInput.get('send_day') in DEFAULT_SEND_DAYS:
                    user.send_days = [self.webInput.get('send_day')]
            user.send_time = int(self.webInput.get('send_time', 8))
            user.device = self.webInput.get('devicetype') or 'kindle'
            user.titlefmt = self.webInput.get('titlefmt') or '%Y-%m-%d'
            user.timezone = int(self.webInput.get('timezone', TIMEZONE))
            user.kindle_email = self.webInput.get('receive_email') or user.kindle_email
            user.remove_hyperlinks = webInput.get('removehyperlinks')
            user.put()
            return json.dumps(self.res)
        elif mgrType.lower == 'cover':# 设置封面图片
            user = KeUser.all().filter("name = ", user_name).get()
            if not user:
                return json.dumps({"status": "failed", "msg": "user not exists!"})
            try:
                x = web.input(coverfile={})
                file_ = x['coverfile'].file
                if user and file_:
                    # 将图像转换为JPEG格式，同时限制分辨率不超过1024
                    img = Image.open(file_)
                    width, height = img.size
                    fmt = img.format
                    if (width > self.MAX_IMAGE_PIXEL) or (height > self.MAX_IMAGE_PIXEL):
                        ratio = min(float(self.MAX_IMAGE_PIXEL) / float(width),
                                    float(self.MAX_IMAGE_PIXEL) / float(height))
                        img = img.resize((int(width * ratio), int(height * ratio)))
                    data = StringIO.StringIO()
                    img.save(data, 'JPEG')
                    user.cover = db.Blob(data.getvalue())
                    user.put()
            except Exception as e:
                res['status'] = 'failed'
                res['msg'] = str(e)
            return json.dumps(self.res)

        elif mgrType.lower == 'upgrade':  # 用户升级 使用时长
            user = KeUser.all().filter("name = ", user_name).get()
            if not user:
                return json.dumps({"status": "failed", "msg": "user not exists!"})
            try:
                if not webInput.get('expires') is None: # 判断是否为空
                    user.expires = webInput.get('expires')
                if not webInput.get('expiration_days') is None:  # 判断是否为空
                    user.expiration_days = webInput.get('expiration_days')
                user.put()
            except Exception as e:
                self.res['status'] = 'failed'
                self.res['msg'] = str(e)
            return json.dumps(self.res)

class FeedRSS(BaseHandler):
    '''
    RSS 订阅 / 删除
    '''
    __url__ = "/api/v2/rss/(.*)"
    def __init__(self):
        super(FeedRSS, self).__init__(setLang=False)
        self.now = datetime.datetime.utcnow()
        self.webInput = web.input()
        self.res = {"status": "ok", "msg": ""}

    def POST(self,mgrType):  # RSS 類
        if not self.check_api_key(self.webInput.get('key')):
            return self.check_api_key(self.webInput.get('key'))
        res = {"status": "ok", "msg": ""}
        user_name = self.webInput.get('user_name')
        if mgrType.lower() == 'myrss':  #RSS我的訂閱
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

        elif mgrType.lower() == 'add':  # 我的订阅新增
            if not user_name:
                return "error"
            user = KeUser.all().filter("name = ", user_name).get()
            title = self.webInput.get('title')
            url = self.webInput.get('url')
            assert user.ownfeeds
            # 判断是否重复
            user_feed_urls = [item.url for item in user.ownfeeds.feeds]
            # print user_feed_urls
            if url in user_feed_urls:
                res['msg'] = 'rss already subscribed!'
                return json.dumps(res)
            fd = Feed(title=title, url=url, book=user.ownfeeds, isfulltext=False,
                      time=datetime.datetime.utcnow())
            fd.put()
            memcache.delete('%d.feedscount' % user.ownfeeds.key().id())
            res['msg'] = fd.key().id()
            return json.dumps(res)

        elif mgrType == 'del':  #订阅删除
            feed_id = self.webInput.get('feed_id')
            if len(feed_id) != 0:

                feed = Feed.get_by_id(int(feed_id))
                if feed:
                    feed.delete()
                    return json.dumps(res)
                else:
                    res['status'] = 'failed'
                    res['msg'] = 'The feed(%d) not exist!' % feed_id
                    return json.dumps(res)
        elif mgrType.lower() == 'invalid':
            feed_id = self.webInput.get('feed_id')
            rss = Feed.get_by_id(int(feed_id))
            if rss:
                html = ' 不可用 %s  %s' % (rss.title,rss.url)
                BaseHandler.SendHtmlMail(name=rss.title, to=SRC_EMAIL, title=rss.title, html=html)



class ApiFeedBook(BaseHandler):
    __url__ = "/api/v2/feed/book/(.*)"
    def __init__(self):
        super(ApiFeedBook, self).__init__(setLang=False)
        self.webInput = web.input()
    def POST(self,mgrType):
        user_name = self.webInput.get('user_name')
        if not user_name:
            return json.dumps({'status': 'failed', "msg": "user_name empty!"})
        user = KeUser.all().filter("name = ", user_name).get()
        if not user:
            return json.dumps({'status': 'failed',"msg":"user not exists"})
        self.queue2push = defaultdict(list)
        if mgrType.lower() == 'deliver':
            books = Book.all()
            bks = [item for item in books if user_name in item.users]
            if len(bks) == 0:
                return json.dumps({'status': 'failed',"msg":_("No book to deliver!")})
            for book in bks:
                self.queueit(user, book.key().id(), book.separate, None)
                # print book.key().id,"11111"
            self.flushqueue()
            return json.dumps({'status': 'ok',"msg":"add task"})

    def check_words(self,words):
        return lambda x: x and frozenset(words.split()).intersection(x.split())

    def queueit(self, usr, bookid, separate, feedsId=None):
        param = {"u": usr.name, "id": bookid}
        taskqueue.add(url='/worker', queue_name="deliverqueue1", method='GET',
                params=param, target="worker")
    def flushqueue(self):
        for name in self.queue2push:
            param = {'u':name, 'id':','.join(self.queue2push[name])}
            taskqueue.add(url='/worker', queue_name="deliverqueue1", method='GET',
                params=param, target="worker")
        self.queue2push = defaultdict(list)



class MyDeliverLogs(BaseHandler,):
    '''
    推送日志
    '''
    __url__ = "/api/v2/my/deliver/logs"
    def __init__(self):
        super(MyDeliverLogs, self).__init__(setLang=False)
        self.webInput = web.input()
        self.res = {"status": "ok", "msg": "", "data":[]}
    def POST(self):
        if not self.check_api_key(self.webInput.get('key')):
            return self.check_api_key(self.webInput.get('key'))
        user_name = self.webInput.get('user_name')
        try:
            my_logs = DeliverLog.all().filter("username = ", user_name).order('-time').fetch(limit=100)
        except NeedIndexError:  # 很多人不会部署，经常出现没有建立索引的情况，干脆碰到这种情况直接消耗CPU时间自己排序得了
            my_logs = sorted(DeliverLog.all().filter("username = ", user_name), key=attrgetter('time'), reverse=True)[:50]
        for log in my_logs:
            my_log = {'to': log.to,'size': log.size,'datetime': log.datetime.strftime('%Y-%m-%d %H:%M:00') ,'book': log.book,'status': log.status}
            self.res['data'].append(my_log)
        return json.dumps(self.res)


'''
加密解密测试
'''
# class test(BaseHandler):
#     __url__ = '/api/v2/encrypt'
#     def POST(self):
#         data = web.input().get('data')
#         text = Encipher(data).aes_decrypt()
#         print(text)
#         json_data = json.loads(text)
#         return json_data.get('user_name')

