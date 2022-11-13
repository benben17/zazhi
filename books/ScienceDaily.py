#!/usr/bin/env python
# -*- coding:utf-8 -*-
# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4

from base import BaseFeedBook



def getBook():
    return ScienceDaily


class ScienceDaily(BaseFeedBook):
    title = u'Science'
    description = u'''ScienceDaily is one of the Internets most popular science news web sites. Since starting in 1995'''
    __author__ = 'Science'
    language = 'en'
    feed_encoding = "utf-8"
    page_encoding = "utf-8"
    coverfile = "cv_science.jpg"
    oldest_article = 7
    deliver_days = ['Friday']


    feeds = [
        (u'Latest Science News', 'https://www.sciencedaily.com/rss/top.xml'),
        (u'All Top News', 'https://www.sciencedaily.com/rss/top/science.xml'),
        (u'Health News', 'https://www.sciencedaily.com/rss/top/health.xml'),
        (u'Technology News', 'https://www.sciencedaily.com/rss/top/technology.xml'),
        (u'Environment News', 'https://www.sciencedaily.com/rss/top/environment.xml'),
        (u'Society News', 'https://www.sciencedaily.com/rss/top/society.xml'),
        (u'Strange Offbeat News',
         'https://www.sciencedaily.com/rss/strange_offbeat.xml'),
    ]


   