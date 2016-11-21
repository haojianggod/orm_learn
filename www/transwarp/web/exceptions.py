#!/usr/bin/env python
# -*- coding:utf8 -*-

#__author__ == 'godlikeme'

from transwarp.web.const import _RESPONSE_HEADERS, _RESPONSE_STATUSES, _HEADER_X_POWERED_BY


# 用于异常处理
class _HttpError(Exception):
    """
    HttpError that defines http error code.
    >>> e = _HttpError(404)
    >>> e.status
    '404 Not Found'
    """
    def __init__(self, code):
        """
        Init an HttpError with response code.
        """
        super(_HttpError, self).__init__()
        self.status = '%d %s' % (code, _RESPONSE_STATUSES[code])
        self._headers = None

    def header(self, name, value):
        """
        添加header， 如果header为空则 添加powered by header
        """
        if not self._headers:
            self._headers = [_HEADER_X_POWERED_BY]
        self._headers.append((name, value))

    @property
    def headers(self):
        """
        使用setter方法实现的 header属性
        """
        if hasattr(self, '_headers'):
            return self._headers
        return []

    def __str__(self):
        return self.status

    __repr__ = __str__


class _RedirectError(_HttpError):
    """
    RedirectError that defines http redirect code.
    >>> e = _RedirectError(302, 'http://www.apple.com/')
    >>> e.status
    '302 Found'
    >>> e.location
    'http://www.apple.com/'
    """
    def __init__(self, code, location):
        """
        Init an HttpError with response code.
        """
        super(_RedirectError, self).__init__(code)
        self.location = location

    def __str__(self):
        return '%s, %s' % (self.status, self.location)

    __repr__ = __str__


class HttpError(object):
    """
    HTTP Exceptions
    """
    @staticmethod
    def badrequest():
        """
        Send a bad request response.
        >>> raise HttpError.badrequest()
        Traceback (most recent call last):
          ...
        _HttpError: 400 Bad Request
        """
        return _HttpError(400)

    @staticmethod
    def unauthorized():
        """
        Send an unauthorized response.
        >>> raise HttpError.unauthorized()
        Traceback (most recent call last):
          ...
        _HttpError: 401 Unauthorized
        """
        return _HttpError(401)

    @staticmethod
    def forbidden():
        """
        Send a forbidden response.
        >>> raise HttpError.forbidden()
        Traceback (most recent call last):
          ...
        _HttpError: 403 Forbidden
        """
        return _HttpError(403)

    @staticmethod
    def notfound():
        """
        Send a not found response.
        >>> raise HttpError.notfound()
        Traceback (most recent call last):
          ...
        _HttpError: 404 Not Found
        """
        return _HttpError(404)

    @staticmethod
    def conflict():
        """
        Send a conflict response.
        >>> raise HttpError.conflict()
        Traceback (most recent call last):
          ...
        _HttpError: 409 Conflict
        """
        return _HttpError(409)

    @staticmethod
    def internalerror():
        """
        Send an internal error response.
        >>> raise HttpError.internalerror()
        Traceback (most recent call last):
          ...
        _HttpError: 500 Internal Server Error
        """
        return _HttpError(500)

    @staticmethod
    def redirect(location):
        """
        Do permanent redirect.
        >>> raise HttpError.redirect('http://www.itranswarp.com/')
        Traceback (most recent call last):
          ...
        _RedirectError: 301 Moved Permanently, http://www.itranswarp.com/
        """
        return _RedirectError(301, location)

    @staticmethod
    def found(location):
        """
        Do temporary redirect.
        >>> raise HttpError.found('http://www.itranswarp.com/')
        Traceback (most recent call last):
          ...
        _RedirectError: 302 Found, http://www.itranswarp.com/
        """
        return _RedirectError(302, location)

    @staticmethod
    def seeother(location):
        """
        Do temporary redirect.
        >>> raise HttpError.seeother('http://www.itranswarp.com/')
        Traceback (most recent call last):
          ...
        _RedirectError: 303 See Other, http://www.itranswarp.com/
        >>> e = HttpError.seeother('http://www.itranswarp.com/seeother?r=123')
        >>> e.location
        'http://www.itranswarp.com/seeother?r=123'
        """
        return _RedirectError(303, location)

