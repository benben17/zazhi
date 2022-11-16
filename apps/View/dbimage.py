#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#Contributors:
# rexdf <https://github.com/rexdf>

from apps.BaseHandler import BaseHandler
from apps.utils import etagged
import web, StringIO
from PIL import Image

#读取数据库中的图像数据，如果为dbimage/cover则返回当前用户的封面图片
class DbImage(BaseHandler):
    __url__ = r"/dbimage/(.*)"
    @etagged()
    def GET(self, id_):
        if id_ != 'cover':
            return ''
        x = web.input(coverfile={})
        file_ = x['coverfile'].file
        user = self.getcurrentuser(forAjax=True)
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
        user = self.getcurrentuser() 
        if user and user.cover:
            web.header("Content-Type", "image/jpeg")
            return user.cover
        else:
            raise web.notfound()
            