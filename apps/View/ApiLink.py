#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
import datetime, urlparse,hashlib,StringIO
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
from PIL import Image
from google.appengine.api.datastore_errors import NeedIndexError
__auth_key__ = 'rss2Ebook.com.luck!'


'''
同步用户
'''
class SyncUser(BaseHandler):
    __url__ = "/api/v2/sync"
    def __init__(self):
        super(SyncUser, self).__init__(setLang=False)


    def POST(self):
        if not self.check_api_key(self.key):
            return self.check_api_key(self.key)
        res = {}
        webInput = web.input()
        book_name = webInput.get('book_name') if webInput.get('book_name') else MY_FEEDS_TITLE
        user_name = webInput.get('user_name')
        to_email = webInput.get("to_email")
        send_days = webInput.get('send_days')
        expiration_days = int(webInput.get('expiration_days')) if webInput.get('expiration_days') else 30
        print send_days
        # 用户必须用户名和 邮箱
        if not user_name or not to_email:
            res['status'] = "failed"
            res["msg"] = "user or email is empty"
            return json.dumps(res)

        # 判断传值是否正确，不正确默认
        default_send_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        if send_days is not None and len(send_days) != 0:
            send_days = send_days.split(',')
            send_days = [send_day for send_day in send_days if send_day in default_send_days]
            if len(send_days) == 0:
                send_days = default_send_days
        else:
            send_days = default_send_days
        u = KeUser.all().filter("name = ",user_name ).get()
        if not u:
            myfeeds = Book(title=book_name, description=MY_FEEDS_DESC,
                           builtin=False, keep_image=True, oldest_article=7,
                           needs_subscription=False, separate=False)
            myfeeds.put()
            secret_key = new_secret_key()
            au = KeUser(name=user_name, passwd=hashlib.md5(to_email + secret_key).hexdigest(),
                        kindle_email=to_email, enable_send=True, send_time=8, timezone=TIMEZONE,
                        send_days=send_days,book_type="epub", device='kindle', ownfeeds=myfeeds,
                        remove_hyperlinks='image',book_mode='periodical',titlefmt='YY-MM-DD',
                        merge_books=True, secret_key=secret_key, expiration_days=expiration_days)
            if webInput.get('expires') is None:
                au.expires
            else:
                au.expires = datetime.datetime.utcnow() + datetime.timedelta(days=expiration_days)
            au.put()

            book_rss = au.ownfeeds
            print book_rss
            book_rss.language = webInput.get("lng", "en-us")
            book_rss.oldest_article = int(webInput.get('oldest', 7))
            book_rss.users = [au.name]
            book_rss.put()
        else:
            res['msg'] = 'username alread exist!'
            res['status'] = 'failed'

        return json.dumps(res)

# 设置封面图片
class AdvUploadCoverImageAjax(BaseHandler):
    __url__ = "/api/v2/sync/user/cover"
    MAX_IMAGE_PIXEL = 1024
    def __init__(self):
        self.webInput = web.input()

    def POST(self):
        if not self.check_api_key(self.webInput.get('key')):
            return self.check_api_key(self.webInput.get('key'))
        res = {"status": "ok", "msg": ""}
        user_name = self.webInput.get('user_name')

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
                    ratio = min(float(self.MAX_IMAGE_PIXEL) / float(width), float(self.MAX_IMAGE_PIXEL) / float(height))
                    img = img.resize((int(width * ratio), int(height * ratio)))
                data = StringIO.StringIO()
                img.save(data, 'JPEG')
                user.cover = db.Blob(data.getvalue())
                user.put()
        except Exception as e:
            ret = str(e)

        return ret

'''
訂閱
'''
class FeedRSS(BaseHandler):
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
            print user_feed_urls
            if url in user_feed_urls:
                res['msg'] = 'rss already subscribed!'
                return json.dumps(res)
            fd = Feed(title=title, url=url, book=user.ownfeeds, isfulltext=False,
                      time=datetime.datetime.utcnow())
            fd.put()
            memcache.delete('%d.feedscount' % user.ownfeeds.key().id())
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
    __url__ = "/api/v2/feed/book"
    def __init__(self):
        super(ApiFeedBook, self).__init__(setLang=False)
        self.now = datetime.datetime.utcnow()
        self.webInput = web.input()
        self.key = self.webInput.get('key')
        self.res = {"status": "ok", "msg": ""}
        # if self.key != __auth_key__:  # key 有问题不抛错误信息
        #     return "error"
    def GET(self):
        BASE = 'https://www.nature.com'
        from lib.urlopener import URLOpener
        from bs4 import BeautifulSoup
        opener = URLOpener(BASE)
        result = opener.open(BASE+'/nature/current-issue')
        soup = BeautifulSoup(result.content,'lxml')
        res =  soup.find(
            'img', attrs={'data-test': 'issue-cover-image'}
        )
        return 'https:'+res['src']
        # cover_url = 'https:' + ['src']
        # return cover_url
    def check_words(self,words):
        return lambda x: x and frozenset(words.split()).intersection(x.split())


class MyLogs(BaseHandler,):
    __url__ = "/api/v2/my/logs"
    def __init__(self):
        super(MyLogs, self).__init__(setLang=False)
        self.webInput = web.input()
        self.res = {"status": "ok", "msg": "", "data":[]}
    def POST(self):
        # 測試加密
        # import apps.AESCipher as AESCipher
        # input = AESCipher.AESCipher().aes_decrypt(self.webInput)
        # in_json = json.loads(input)
        # return in_json.get('user_name')
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


