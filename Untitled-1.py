#!/usr/bin/env python
# -*- coding:utf-8 -*-


def processtitle(title):
    return title[:-6] if title.endswith(u'_三联生活网') else title


print(processtitle(u"三联生活网abc"))
