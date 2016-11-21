#!/usr/bin/env python
# -*- coding:utf8 -*-

#__author__ == 'godlikeme'
import types
import threading
from transwarp.web.utils import load_module
from transwarp.web.exceptions import HttpError
from transwarp.db_module.db import Dict
from mylogging.factory import logger1
from const import _HEADER_X_POWERED_BY, _RESPONSE_STATUSES, _RE_RESPONSE_STATUS
import re, os, mimetypes, utils, cgi,  urllib , datetime






ctx = threading.local()



#######################################################
################  Route ###############################
#######################################################

# 用于捕获变量的re
_re_route = re.compile(r'(:[a-zA-Z_]\w*)')

def _build_regex(path):
    r"""
    用于将路径转换成正则表达式，并捕获其中的参数
    >>> _build_regex('/path/to/:file')
    '^\\/path\\/to\\/(?P<file>[^\\/]+)$'
    >>> _build_regex('/:user/:comments/list')
    '^\\/(?P<user>[^\\/]+)\\/(?P<comments>[^\\/]+)\\/list$'
    >>> _build_regex(':id-:pid/:w')
    '^(?P<id>[^\\/]+)\\-(?P<pid>[^\\/]+)\\/(?P<w>[^\\/]+)$'
    """

    re_list = ['^']
    var_list = []
    is_var = False
    for v in _re_route.split(path):
        if is_var:
            var_name = v[1:]
            var_list.append(var_name)
            re_list.append(r'(?P<%s>[^\/]+)' % var_name)
        else:
            s = ''
            for ch in v:
                if '0' <= ch <= '9' or 'a' <= ch <= 'z' or 'A' <= ch <= 'Z':
                    s += ch
                else:
                    s = s + '\\' + ch
            re_list.append(s)
        is_var = not is_var
    re_list.append('$')
    return ''.join(re_list)


def _static_file_generator(fpath, block_size=8192):
    """
    读取静态文件的一个生成器
    """
    with open(fpath, 'rb') as f:
        block = f.read(block_size)
        while block:
            yield block
            block = f.read(block_size)


def _build_interceptor_fn(func, next):
    """
    拦截器接受一个next函数，这样，一个拦截器可以决定调用next()继续处理请求还是直接返回
    """

    def _wrapper():
        if func.__interceptor__(ctx.request.path_info):
            return func(next)
        else:
            return next()
    return _wrapper


def _build_interceptor_chain(last_fn, *interceptors):
    L = list(interceptors)
    L.reverse()
    fn = last_fn
    for f in L:
        fn = _build_interceptor_fn(f, fn)
    return fn

_RE_INTERCEPTOR_STARTS_WITH = re.compile(r'^([^\*\?]+)\*?$')
_RE_INTERCEPTOR_ENDS_WITH = re.compile(r'^\*([^\*\?]+)$')


def _build_pattern_fn(pattern):
    """
    传入需要匹配的字符串： URL
    返回一个函数，该函数接收一个字符串参数，检测该字符串是否
    符合pattern
    """
    m = _RE_INTERCEPTOR_STARTS_WITH.match(pattern)
    if m:
        return lambda p: p.startswith(m.group(1))
    m = _RE_INTERCEPTOR_ENDS_WITH.match(pattern)
    if m:
        return lambda p: p.endswith(m.group(1))
    raise ValueError('Invalid pattern definition in interceptor.')


def interceptor(pattern='/'):
    """
    An @interceptor decorator.
    @interceptor('/admin/')
    def check_admin(req, resp):
        pass
    """
    def _decorator(func):
        func.__interceptor__ = _build_pattern_fn(pattern)
        return func
    return _decorator


class Route(object):
    def __init__(self, func):
        """
        path： 通过method的装饰器捕获的path
        method： 通过method装饰器捕获的method
        is_static： 路径是否含变量，含变量为True
        route：动态url（含变量）则捕获其变量的 re
        func： 方法装饰器里定义的函数
        """

        self.path = func.__web_route__
        self.method = func.__web_method__
        self.is_static = _re_route.search(self.path) is None
        if not self.is_static:
            self.route = re.compile(_build_regex(self.path))
        self.func = func

    def match(self, url):
        """

        传入url，返回捕获的变量
        """
        m = self.route.match(url)
        if m:
            return m.groups()
        return None

    def __call__(self, *args, **kwargs):
        """
        实例对象直接调用时，执行传入的函数对象
        """
        return self.func(*args)

    def __str__(self):
        if self.is_static:
            return 'Route(static, %s, path=%s)' % (self.method, self.path)

        return 'Route(dynamic, %s, path=%s)' % (self.method, self.path)

    __repr__ = __str__


class StaticFileRoute(object):
    """
    静态文件路由对象，和Route相对应
    """
    def __init__(self):
        self.method = 'GET'
        self.is_static = False
        self.route = re.compile('^/static/(.+)$')

    def match(self, url):
        if url.startswith('/static'):
            return url[1:]
        return None

    def __call__(self, *args, **kwargs):
        fpath = os.path.join(ctx.application.document_root, args[0])
        if not os.path.isfile(fpath):
            raise HttpError.notfound()
        fext = os.path.splitext(fpath)[1]
        ctx.response.content_type = mimetypes.types_map.get(fext.lower(), "application/octet-stream")
        return _static_file_generator(fpath)


if __name__ == '__main__':
    # print _build_regex("/:user/:comments/list")

    @interceptor('/admin')
    def f1(next):
        print "before f1"
        return next()

    @interceptor('/admin')
    def f2(next):
        print "before f2"
        return next()

    @interceptor('/admin')
    def f3(next):
        print "before f3"
        return next()

    def last():
        print "last"
    s = _build_interceptor_chain(last, f1, f2, f3)
    s()



class WSGIApplication(object):

    def __init__(self, document_root=None, **kw):
        """

        Init a WSGIApplication.
        Args:
          document_root: document root path.
        """
        self._running = False
        self._document_root = document_root
        self._interceptors = []
        self._template_engine = None
        self._get_static = {}
        self._post_static = {}

        self._get_dynamic = []
        self._post_dynamic= []

    def _check_not_running(self):
        """
         check app if is running
        """
        if self._running:
            raise RuntimeError("Can not modify WSGIApplication when running.")

    @property
    def template_engine(self):
        return self._template_engine

    @template_engine.setter
    def template_engine(self, engine):
        """
        set template engine

        """
        self._check_not_running()
        self._template_engine = engine

    def add_module(self, mod):
        self._check_not_running()
        m = mod if type(mod) == types.ModuleType else load_module(mod)
        logger1.info('Add module: %s' % m.__name__)
        for name in dir(m):
            fn = getattr(m, name)
            if callable(fn) and hasattr(fn, '__web_route__') and hasattr(fn, '__web_method__'):
                self.add_url(fn)

    def add_url(self, func):
        """

        add url func
        """
        self._check_not_running()
        route = Route(func)
        if route.is_static:
            if route.method == 'GET':
                self._get_static[route.path] = route
            if route.method == 'POST':
                self._post_static[route.path] = route
        else:
            if route.method == 'GET':
                self._get_dynamic.append(route)
            if route.method == 'POST':
                self._post_dynamic.append(route)

        logger1.info('Add route: %s' % str(route))


    def add_interceptor(self, func):
        self._check_not_running()
        self._interceptors.append(func)
        logger1.info('Add interceptor: %s' % str(func))


    def run(self, port=9000, host='127.0.0.1', debug=False):
        """
        启动python自带的WSGI Server
        """
        from wsgiref.simple_server import make_server
        logger1.info('application (%s) will start at %s:%s...' % (self._document_root, host, port))
        server = make_server(host, port, self.get_wsgi_application(debug=debug))
        server.serve_forever()

    def get_wsgi_application(self, debug=False):
        self._check_not_running()
        if debug:
            self._get_dynamic.append(StaticFileRoute())
        self._running = True

        _application = Dict(document_root=self._document_root)

        def fn_route():
            request_method = ctx.request.request_method
            path_info = ctx.request.path_info
            if request_method == 'GET':
                fn = self._get_static.get(path_info, None)
                if fn:
                    return fn()
                for fn in self._get_dynamic:
                    args = fn.match(path_info)
                    if args:
                        return fn(*args)

                raise HttpError.notfound()

            if request_method == 'POST':
                fn = self._post_static.get(path_info, None)
                if fn:
                    return fn()
                for fn in self._post_dynamic:
                    args = fn.match(path_info)
                    if args:
                        return fn(*args)
                raise HttpError.notfound()

            raise HttpError.badrequest()

        fn_exec = _build_interceptor_chain(fn_route, *self._interceptors)

        def wsgi(env, start_response):
            """

            WSGI 处理函数
            """
            ctx.applicatioin = _application
            ctx.request = Request(env)
            response = ctx.response = Response()



####################################################
######################## Request ###################


class MultipartFile(object):
    """
    Multipart file storage get from request input.
    f = ctx.request['file']
    f.filename # 'test.png'
    f.file # file-like object
    """
    def __init__(self, storage):
        self.filename = utils.to_unicode(storage.filename)
        self.file = storage.file



class Request(object):
    """
    请求对象， 用于获取所有http请求信息。
    """

    def __init__(self, environ):
        """
        environ  wsgi处理函数里面的那个 environ
        wsgi server调用 wsgi 处理函数时传入的
        包含了用户请求的所有数据
        """
        self._environ = environ

    def _parse_input(self):
        """
        将通过wsgi 传入过来的参数，解析成一个字典对象 返回
        比如： Request({'REQUEST_METHOD':'POST', 'wsgi.input':StringIO('a=1&b=M%20M&c=ABC&c=XYZ&e=')})
            这里解析的就是 wsgi.input 对象里面的字节流
        """

        def _convert(item):
            if isinstance(item, list):
                return [utils.to_unicode(i.value) for i in item]
            if item.filename:
                return MultipartFile(item)
            return utils.to_unicode(item.value)

        fs = cgi.FieldStorage(fp=self._environ['wsgi.input'], environ=self._environ, keep_blank_values=True)
        inputs = dict()
        for key in fs:
            inputs[key] = _convert(fs[key])
        return inputs

    def _get_raw_input(self):
        """
        将从wsgi解析出来的 数据字典，添加为Request对象的属性
        然后 返回该字典
        """
        if not hasattr(self, '_raw_input'):
            self._raw_input = self._parse_input()
        return self._raw_input

    def __getitem__(self, key):
        """
        实现通过键值访问Request对象里面的数据，如果该键有多个值，则返回第一个值
        如果键不存在，这会 raise KyeError
        >>> from StringIO import StringIO
        >>> r = Request({'REQUEST_METHOD':'POST', 'wsgi.input':StringIO('a=1&b=M%20M&c=ABC&c=XYZ&e=')})
        >>> r['a']
        u'1'
        >>> r['c']
        u'ABC'
        >>> r['empty']
        Traceback (most recent call last):
            ...
        KeyError: 'empty'
        >>> b = '----WebKitFormBoundaryQQ3J8kPsjFpTmqNz'
        >>> pl = ['--%s' % b, 'Content-Disposition: form-data; name=\\"name\\"\\n', 'Scofield', '--%s' % b, 'Content-Disposition: form-data; name=\\"name\\"\\n', 'Lincoln', '--%s' % b, 'Content-Disposition: form-data; name=\\"file\\"; filename=\\"test.txt\\"', 'Content-Type: text/plain\\n', 'just a test', '--%s' % b, 'Content-Disposition: form-data; name=\\"id\\"\\n', '4008009001', '--%s--' % b, '']
        >>> payload = '\\n'.join(pl)
        >>> r = Request({'REQUEST_METHOD':'POST', 'CONTENT_LENGTH':str(len(payload)), 'CONTENT_TYPE':'multipart/form-data; boundary=%s' % b, 'wsgi.input':StringIO(payload)})
        >>> r.get('name')
        u'Scofield'
        >>> r.gets('name')
        [u'Scofield', u'Lincoln']
        >>> f = r.get('file')
        >>> f.filename
        u'test.txt'
        >>> f.file.read()
        'just a test'
        """
        r = self._get_raw_input()[key]
        if isinstance(r, list):
            return r[0]
        return r

    def get(self, key, default=None):
        """
        实现了字典里面的get功能
        和上面的__getitem__一样(request[key]),但如果没有找到key,则返回默认值。
        >>> from StringIO import StringIO
        >>> r = Request({'REQUEST_METHOD':'POST', 'wsgi.input':StringIO('a=1&b=M%20M&c=ABC&c=XYZ&e=')})
        >>> r.get('a')
        u'1'
        >>> r.get('empty')
        >>> r.get('empty', 'DEFAULT')
        'DEFAULT'
        """
        r = self._get_raw_input().get(key, default)
        if isinstance(r, list):
            return r[0]
        return r

    def gets(self, key):
        '''
        Get multiple values for specified key.
        >>> from StringIO import StringIO
        >>> r = Request({'REQUEST_METHOD':'POST', 'wsgi.input':StringIO('a=1&b=M%20M&c=ABC&c=XYZ&e=')})
        >>> r.gets('a')
        [u'1']
        >>> r.gets('c')
        [u'ABC', u'XYZ']
        >>> r.gets('empty')
        Traceback (most recent call last):
            ...
        KeyError: 'empty'
        '''
        r = self._get_raw_input()[key]
        if isinstance(r, list):
            return r[:]
        return [r]

    def input(self, **kw):
        """
        返回一个由传入的数据和从environ里取出的数据 组成的Dict对象，Dict对象的定义 见db模块
        Get input as dict from request, fill dict using provided default value if key not exist.
        i = ctx.request.input(role='guest')
        i.role ==> 'guest'
        >>> from StringIO import StringIO
        >>> r = Request({'REQUEST_METHOD':'POST', 'wsgi.input':StringIO('a=1&b=M%20M&c=ABC&c=XYZ&e=')})
        >>> i = r.input(x=2008)
        >>> i.a
        u'1'
        >>> i.b
        u'M M'
        >>> i.c
        u'ABC'
        >>> i.x
        2008
        >>> i.get('d', u'100')
        u'100'
        >>> i.x
        2008
        """
        copy = Dict(**kw)
        raw = self._get_raw_input()
        for k, v in raw.iteritems():
            copy[k] = v[0] if isinstance(v, list) else v
        return copy

    def get_body(self):
        """
        从HTTP POST 请求中取得 body里面的数据，返回为一个str对象
        >>> from StringIO import StringIO
        >>> r = Request({'REQUEST_METHOD':'POST', 'wsgi.input':StringIO('<xml><raw/>')})
        >>> r.get_body()
        '<xml><raw/>'
        """
        fp = self._environ['wsgi.input']
        return fp.read()

    @property
    def remote_addr(self):
        """
        Get remote addr. Return '0.0.0.0' if cannot get remote_addr.
        >>> r = Request({'REMOTE_ADDR': '192.168.0.100'})
        >>> r.remote_addr
        '192.168.0.100'
        """
        return self._environ.get('REMOTE_ADDR', '0.0.0.0')

    @property
    def document_root(self):
        """
        Get raw document_root as str. Return '' if no document_root.
        >>> r = Request({'DOCUMENT_ROOT': '/srv/path/to/doc'})
        >>> r.document_root
        '/srv/path/to/doc'
        """
        return self._environ.get('DOCUMENT_ROOT', '')

    @property
    def query_string(self):
        """
        Get raw query string as str. Return '' if no query string.
        >>> r = Request({'QUERY_STRING': 'a=1&c=2'})
        >>> r.query_string
        'a=1&c=2'
        >>> r = Request({})
        >>> r.query_string
        ''
        """
        return self._environ.get('QUERY_STRING', '')

    @property
    def environ(self):
        """
        Get raw environ as dict, both key, value are str.
        >>> r = Request({'REQUEST_METHOD': 'GET', 'wsgi.url_scheme':'http'})
        >>> r.environ.get('REQUEST_METHOD')
        'GET'
        >>> r.environ.get('wsgi.url_scheme')
        'http'
        >>> r.environ.get('SERVER_NAME')
        >>> r.environ.get('SERVER_NAME', 'unamed')
        'unamed'
        """
        return self._environ

    @property
    def request_method(self):
        """
        Get request method. The valid returned values are 'GET', 'POST', 'HEAD'.
        >>> r = Request({'REQUEST_METHOD': 'GET'})
        >>> r.request_method
        'GET'
        >>> r = Request({'REQUEST_METHOD': 'POST'})
        >>> r.request_method
        'POST'
        """
        return self._environ['REQUEST_METHOD']

    @property
    def path_info(self):
        """
        Get request path as str.
        >>> r = Request({'PATH_INFO': '/test/a%20b.html'})
        >>> r.path_info
        '/test/a b.html'
        """
        return urllib.unquote(self._environ.get('PATH_INFO', ''))

    @property
    def host(self):
        """
        Get request host as str. Default to '' if cannot get host..
        >>> r = Request({'HTTP_HOST': 'localhost:8080'})
        >>> r.host
        'localhost:8080'
        """
        return self._environ.get('HTTP_HOST', '')

    def _get_headers(self):
        """
        从environ里 取得HTTP_开通的 header
        """
        if not hasattr(self, '_headers'):
            hdrs = {}
            for k, v in self._environ.iteritems():
                if k.startswith('HTTP_'):
                    # convert 'HTTP_ACCEPT_ENCODING' to 'ACCEPT-ENCODING'
                    hdrs[k[5:].replace('_', '-').upper()] = v.decode('utf-8')
            self._headers = hdrs
        return self._headers

    @property
    def headers(self):
        """
        获取所有的header， setter实现的属性
        Get all HTTP headers with key as str and value as unicode. The header names are 'XXX-XXX' uppercase.
        >>> r = Request({'HTTP_USER_AGENT': 'Mozilla/5.0', 'HTTP_ACCEPT': 'text/html'})
        >>> H = r.headers
        >>> H['ACCEPT']
        u'text/html'
        >>> H['USER-AGENT']
        u'Mozilla/5.0'
        >>> L = H.items()
        >>> L.sort()
        >>> L
        [('ACCEPT', u'text/html'), ('USER-AGENT', u'Mozilla/5.0')]
        """
        return dict(**self._get_headers())

    def header(self, header, default=None):
        """
        获取指定的header的值
        Get header from request as unicode, return None if not exist, or default if specified.
        The header name is case-insensitive such as 'USER-AGENT' or u'content-Type'.
        >>> r = Request({'HTTP_USER_AGENT': 'Mozilla/5.0', 'HTTP_ACCEPT': 'text/html'})
        >>> r.header('User-Agent')
        u'Mozilla/5.0'
        >>> r.header('USER-AGENT')
        u'Mozilla/5.0'
        >>> r.header('Accept')
        u'text/html'
        >>> r.header('Test')
        >>> r.header('Test', u'DEFAULT')
        u'DEFAULT'
        """
        return self._get_headers().get(header.upper(), default)

    def _get_cookies(self):
        """
        从environ里取出cookies字符串，并解析成键值对 组成的字典
        """
        if not hasattr(self, '_cookies'):
            cookies = {}
            cookie_str = self._environ.get('HTTP_COOKIE')
            if cookie_str:
                for c in cookie_str.split(';'):
                    pos = c.find('=')
                    if pos > 0:
                        cookies[c[:pos].strip()] = utils.unquote(c[pos + 1:])
            self._cookies = cookies
        return self._cookies

    @property
    def cookies(self):
        """
        setter 以Dict对象返回cookies
        Return all cookies as dict. The cookie name is str and values is unicode.
        >>> r = Request({'HTTP_COOKIE':'A=123; url=http%3A%2F%2Fwww.example.com%2F'})
        >>> r.cookies['A']
        u'123'
        >>> r.cookies['url']
        u'http://www.example.com/'
        """
        return Dict(**self._get_cookies())

    def cookie(self, name, default=None):
        """
        获取指定的cookie
        Return specified cookie value as unicode. Default to None if cookie not exists.
        >>> r = Request({'HTTP_COOKIE':'A=123; url=http%3A%2F%2Fwww.example.com%2F'})
        >>> r.cookie('A')
        u'123'
        >>> r.cookie('url')
        u'http://www.example.com/'
        >>> r.cookie('test')
        >>> r.cookie('test', u'DEFAULT')
        u'DEFAULT'
        """
        return self._get_cookies().get(name, default)


#####################################################################
################################# Response ##########################
######################################################################

_RESPONSE_HEADERS = (
    'Accept-Ranges',
    'Age',
    'Allow',
    'Cache-Control',
    'Connection',
    'Content-Encoding',
    'Content-Language',
    'Content-Length',
    'Content-Location',
    'Content-MD5',
    'Content-Disposition',
    'Content-Range',
    'Content-Type',
    'Date',
    'ETag',
    'Expires',
    'Last-Modified',
    'Link',
    'Location',
    'P3P',
    'Pragma',
    'Proxy-Authenticate',
    'Refresh',
    'Retry-After',
    'Server',
    'Set-Cookie',
    'Strict-Transport-Security',
    'Trailer',
    'Transfer-Encoding',
    'Vary',
    'Via',
    'Warning',
    'WWW-Authenticate',
    'X-Frame-Options',
    'X-XSS-Protection',
    'X-Content-Type-Options',
    'X-Forwarded-Proto',
    'X-Powered-By',
    'X-UA-Compatible',
)

_RESPONSE_HEADER_DICT = dict(zip(map(lambda x: x.upper(), _RESPONSE_HEADERS), _RESPONSE_HEADERS))
from utils import UTC
UTC_0 = UTC('+00:00')

class Response(object):

    def __init__(self):
        self._status = '200 OK'
        self._headers = {'CONTENT-TYPE': 'text/html; charset=utf-8'}

    def unset_header(self, name):
        """
        删除指定的header
        >>> r = Response()
        >>> r.header('content-type')
        'text/html; charset=utf-8'
        >>> r.unset_header('CONTENT-type')
        >>> r.header('content-type')
        """
        key = name.upper()
        if key not in _RESPONSE_HEADER_DICT:
            key = name
        if key in self._headers:
            del self._headers[key]

    def set_header(self, name, value):
        """
        给指定的header 赋值
        >>> r = Response()
        >>> r.header('content-type')
        'text/html; charset=utf-8'
        >>> r.set_header('CONTENT-type', 'image/png')
        >>> r.header('content-TYPE')
        'image/png'
        """
        key = name.upper()
        if key not in _RESPONSE_HEADER_DICT:
            key = name
        self._headers[key] = utils.to_str(value)

    def header(self, name):
        """
        获取Response Header 里单个 Header的值， 非大小写敏感
        >>> r = Response()
        >>> r.header('content-type')
        'text/html; charset=utf-8'
        >>> r.header('CONTENT-type')
        'text/html; charset=utf-8'
        >>> r.header('X-Powered-By')
        """
        key = name.upper()
        if key not in _RESPONSE_HEADER_DICT:
            key = name
        return self._headers.get(key)

    @property
    def headers(self):
        """
        setter 构造的属性，以[(key1, value1), (key2, value2)...] 形式存储 所有header的值，
        包括cookies的值
        >>> r = Response()
        >>> r.headers
        [('Content-Type', 'text/html; charset=utf-8'), ('X-Powered-By', 'transwarp/1.0')]
        >>> r.set_cookie('s1', 'ok', 3600)
        >>> r.headers
        [('Content-Type', 'text/html; charset=utf-8'), ('Set-Cookie', 's1=ok; Max-Age=3600; Path=/; HttpOnly'), ('X-Powered-By', 'transwarp/1.0')]
        """
        L = [(_RESPONSE_HEADER_DICT.get(k, k), v) for k, v in self._headers.iteritems()]
        if hasattr(self, '_cookies'):
            for v in self._cookies.itervalues():
                L.append(('Set-Cookie', v))
        L.append(_HEADER_X_POWERED_BY)
        return L

    @property
    def content_type(self):
        """
        setter 方法实现的属性，用户保存header： Content-Type的值
        >>> r = Response()
        >>> r.content_type
        'text/html; charset=utf-8'
        >>> r.content_type = 'application/json'
        >>> r.content_type
        'application/json'
        """
        return self.header('CONTENT-TYPE')

    @content_type.setter
    def content_type(self, value):
        """
        让content_type 属性可写， 及设置Content-Type Header
        """
        if value:
            self.set_header('CONTENT-TYPE', value)
        else:
            self.unset_header('CONTENT-TYPE')

    @property
    def content_length(self):
        """
        获取Content-Length Header 的值
        >>> r = Response()
        >>> r.content_length
        >>> r.content_length = 100
        >>> r.content_length
        '100'
        """
        return self.header('CONTENT-LENGTH')

    @content_length.setter
    def content_length(self, value):
        """
        设置Content-Length Header 的值
        >>> r = Response()
        >>> r.content_length = '1024'
        >>> r.content_length
        '1024'
        >>> r.content_length = 1024 * 8
        >>> r.content_length
        '8192'
        """
        self.set_header('CONTENT-LENGTH', str(value))

    def delete_cookie(self, name):
        """
        Delete a cookie immediately.
        Args:
          name: the cookie name.
        """
        self.set_cookie(name, '__deleted__', expires=0)

    def set_cookie(self, name, value, max_age=None, expires=None, path='/', domain=None, secure=False, http_only=True):
        if not hasattr(self, '_cookies'):
            self._cookies = {}
        L = ['%s=%s' % (utils.quote(name), utils.quote(value))]
        if expires is not None:
            if isinstance(expires, (float, int, long)):
                L.append('Expires=%s' % datetime.datetime.fromtimestamp(expires, UTC_0).strftime(
                    '%a, %d-%b-%Y %H:%M:%S GMT'))
            if isinstance(expires, (datetime.date, datetime.datetime)):
                L.append('Expires=%s' % expires.astimezone(UTC_0).strftime('%a, %d-%b-%Y %H:%M:%S GMT'))
        elif isinstance(max_age, (int, long)):
            L.append('Max-Age=%d' % max_age)
        L.append('Path=%s' % path)
        if domain:
            L.append('Domain=%s' % domain)
        if secure:
            L.append('Secure')
        if http_only:
            L.append('HttpOnly')
        self._cookies[name] = '; '.join(L)

    def unset_cookie(self, name):
        """
        Unset a cookie.
        >>> r = Response()
        >>> r.set_cookie('company', 'Abc, Inc.', max_age=3600)
        >>> r._cookies
        {'company': 'company=Abc%2C%20Inc.; Max-Age=3600; Path=/; HttpOnly'}
        >>> r.unset_cookie('company')
        >>> r._cookies
        {}
        """
        if hasattr(self, '_cookies'):
            if name in self._cookies:
                del self._cookies[name]

    @property
    def status_code(self):
        """
        Get response status code as int.
        >>> r = Response()
        >>> r.status_code
        200
        >>> r.status = 404
        >>> r.status_code
        404
        >>> r.status = '500 Internal Error'
        >>> r.status_code
        500
        """
        return int(self._status[:3])

    @property
    def status(self):
        """
        Get response status. Default to '200 OK'.
        >>> r = Response()
        >>> r.status
        '200 OK'
        >>> r.status = 404
        >>> r.status
        '404 Not Found'
        >>> r.status = '500 Oh My God'
        >>> r.status
        '500 Oh My God'
        """
        return self._status

    @status.setter
    def status(self, value):
        if isinstance(value, (int, long)):
            if 100 <= value <= 999:
                st = _RESPONSE_STATUSES.get(value, '')
                if st:
                    self._status = '%d %s' % (value, st)
                else:
                    self._status = str(value)
            else:
                raise ValueError('Bad response code: %d' % value)
        elif isinstance(value, basestring):
            if isinstance(value, unicode):
                value = value.encode('utf-8')
            if _RE_RESPONSE_STATUS.match(value):
                self._status = value
            else:
                raise ValueError('Bad response code: %s' % value)
        else:
            raise TypeError('Bad type of response code.')


#################################################################
# 实现URL路由功能
# 将URL 映射到 函数上
#################################################################


# 方法的装饰器，用于捕获url
def get(path):
    """
    A @get decorator.
    @get('/:id')
    def index(id):
        pass
    >>> @get('/test/:id')
    ... def test():
    ...     return 'ok'
    ...
    >>> test.__web_route__
    '/test/:id'
    >>> test.__web_method__
    'GET'
    >>> test()
    'ok'
    """
    def _decorator(func):
        func.__web_route__ = path
        func.__web_method__ = 'GET'
        return func
    return _decorator


def post(path):
    """
    A @post decorator.
    >>> @post('/post/:id')
    ... def testpost():
    ...     return '200'
    ...
    >>> testpost.__web_route__
    '/post/:id'
    >>> testpost.__web_method__
    'POST'
    >>> testpost()
    '200'
    """
    def _decorator(func):
        func.__web_route__ = path
        func.__web_method__ = 'POST'
        return func
    return _decorator



