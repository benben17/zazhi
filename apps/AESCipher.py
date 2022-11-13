#!/usr/bin/env python
# -*- coding:utf-8 -*-
#A GAE web application to aggregate rss and send it to your kindle.
#Visit https://github.com/cdhigh/KindleEar for the latest version
#中文讨论贴：http://www.hi-pda.com/forum/viewthread.php?tid=1213082
#Author:
# cdhigh <https://github.com/cdhigh>
#Contributors:
# rexdf <https://github.com/rexdf>

import base64
from Crypto.Cipher import AES

class AESCipher():
    AES_KEY = '8547781758A3E194498AF0B41AA07028'
    AES_IV = 'FCE68D90B6D023741C6E9BB12CA08A73'
    BLOCK_SIZE = 16  # Bytes

    def __init__(self, key=None, iv=None):
        """
        Requires hex encoded param as a key
        """
        if key:
            self.key = key.decode('hex')
        else:
            self.key = self.AES_KEY.decode('hex')  # 基于python2
            # 如果是python3，就是bytes.fromhex(self.AES_KEY)

        if iv:
            self.iv = iv.decode('hex')
        else:
            self.iv = self.AES_KEY.decode('hex')

    def _pad(self, s):
        return s + (self.BLOCK_SIZE - len(s) % self.BLOCK_SIZE) * \
               chr(self.BLOCK_SIZE - len(s) % self.BLOCK_SIZE)

    def _unpad(self, s):
        return s[:-ord(s[len(s) - 1:])]

    def aes_encrypt(self, data):
        '''
        AES的ECB模式加密方法
        :param key: 密钥
        :param data:被加密字符串（明文）
        :return:密文
        '''
        key = self.AES_KEY.encode('utf8')
        # 字符串补位
        data = self._pad(data)
        cipher = AES.new(key, AES.MODE_ECB)
        # 加密后得到的是bytes类型的数据，使用Base64进行编码,返回byte字符串
        result = cipher.encrypt(data.encode())
        encodestrs = base64.b64encode(result)
        enctext = encodestrs.decode('utf8')
        return enctext

    def aes_decrypt(self, data):
        '''
        :param key: 密钥
        :param data: 加密后的数据（密文）
        :return:明文
        '''
        key = self.AES_KEY.encode('utf8')
        data = base64.b64decode(data)
        cipher = AES.new(key, AES.MODE_ECB)

        # 去补位
        text_decrypted = self._unpad(cipher.decrypt(data))
        text_decrypted = text_decrypted.decode('utf8')
        return text_decrypted


if __name__ == '__main__':
    text = '''{"user_name":"admin"}'''
    print AESCipher().aes_encrypt(text)