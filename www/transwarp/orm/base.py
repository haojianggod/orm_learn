#!/usr/bin/env python
# -*- coding:utf8 -*-

#__author__ == 'godlikeme'
from transwarp.orm.exceptions import GenSqlException, PrimaryKeyException
from transwarp.db_module import opts
from mylogging.factory import logger1

_triggers = frozenset(['pre_insert', 'pre_update', 'pre_delete'])

def _gen_sql(table_name, mappings):
    """
    类 ==> 表时 生成创建表的sql
    """
    pk = None
    sql = ['-- generating SQL for %s: ' % table_name, 'create table `%s` (' % table_name]
    for f in sorted(mappings.values(), lambda x, y: cmp(x._order, y._order)):
        if not hasattr(f, "ddl"):
            raise GenSqlException('no ddl in field "%s"' % f)

        ddl = f.ddl
        nullable = f.nullable
        if f.primary_key:
            if pk is not None:
                raise GenSqlException('already has primary key : "%s"' % pk)
            pk = f.name

        sql.append(' `%s` %s, ' % (f.name, ddl) if nullable else ' `%s` %s not null, ' % (f.name, ddl))

    sql.append(' primary key(`%s`)' % pk)
    sql.append(');')
    return '\n'.join(sql)


class Field(object):
    _count = 0

    def __init__(self, **kwargs):
        self.name = kwargs.get("name", None)
        self._default = kwargs.get('default', None)
        self.primary_key = kwargs.get('primary_key', False)
        self.nullable = kwargs.get("nullable", False)
        self.updatable = kwargs.get('updatable', True)
        self.insertable = kwargs.get('insertable', True)
        self.ddl = kwargs.get('ddl', '')
        self._order = Field._count
        Field._count += 1

    @property
    def default(self):
        d = self._default
        return d() if callable(d) else d

    def __str__(self):
        """
        返回实例对象的描述信息，比如：
            <IntegerField:id,bigint,default(0),UI>
            类：实例：实例ddl属性：实例default信息，3中标志位：N U I
        """
        s = ['<%s:%s, %s, default(%s), ' % (self.__class__.__name__, self.name, self.ddl, self._default)]
        self.nullable and s.append('N')
        self.updatable and s.append('U')
        self.insertable and s.append('I')
        s.append('>')
        return ''.join(s)


class StringField(Field):
    def __init__(self, **kwargs):
        if 'default' not in kwargs:
            kwargs['default'] = ''
        if 'ddl' not in kwargs:
            kwargs['ddl'] = 'varchar(255)'

        super(StringField, self).__init__(**kwargs)


class IntegerField(Field):
    def __init__(self, **kwargs):
        if 'default' not in kwargs:
            kwargs['default'] = 0
        if 'ddl' not in kwargs:
            kwargs['ddl'] = 'bigint'

        super(IntegerField, self).__init__(**kwargs)


class FloatField(Field):
    """
    保存Float类型字段的属性
    """
    def __init__(self, **kw):
        if 'default' not in kw:
            kw['default'] = 0.0
        if 'ddl' not in kw:
            kw['ddl'] = 'real'
        super(FloatField, self).__init__(**kw)


class BooleanField(Field):
    """
    保存BooleanField类型字段的属性
    """
    def __init__(self, **kw):
        if not 'default' in kw:
            kw['default'] = False
        if not 'ddl' in kw:
            kw['ddl'] = 'bool'
        super(BooleanField, self).__init__(**kw)


class TextField(Field):
    """
    保存Text类型字段的属性
    """
    def __init__(self, **kw):
        if 'default' not in kw:
            kw['default'] = ''
        if 'ddl' not in kw:
            kw['ddl'] = 'text'
        super(TextField, self).__init__(**kw)


class BlobField(Field):
    """
    保存Blob类型字段的属性
    """
    def __init__(self, **kw):
        if 'default' not in kw:
            kw['default'] = ''
        if 'ddl' not in kw:
            kw['ddl'] = 'blob'
        super(BlobField, self).__init__(**kw)


class VersionField(Field):
    """
    保存Version类型字段的属性
    """
    def __init__(self, name=None):
        super(VersionField, self).__init__(name=name, default=0, ddl='bigint')


class ModelMataclass(type):
    def __new__(cls, name, bases, attrs):
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)

        # store all subclass info
        if not hasattr(cls, 'subclasses'):
            cls.subclasses = {}

        if not name in cls.subclasses:
            cls.subclasses[name] = name
        else:
            logger1.warning('Redefine class: %s' % name)

        logger1.info('Scan ORMapping %s...' % name)
        mappings = dict()
        primary_key = None
        for k, v in attrs.iteritems():
            if isinstance(v, Field):
                if not v.name:
                    v.name = k
                logger1.info('[ MAPPING ] Found mapping: %s => %s' % (k, v))
                if v.primary_key:
                    if primary_key:
                        raise PrimaryKeyException('Cannot define more than 1 primary key in class: %s' % name)

                    if v.updatable:
                        logger1.warning('NOTE: change primary key to non-updatable')
                        v.updatable = False

                    if v.nullable:
                        logger1.warning('NOTE: change primary key to non-nullable')
                        v.nullable = False

                    primary_key = v

                mappings[k] = v

        if not primary_key:
            raise PrimaryKeyException('Primary key not defined in class : %s' % name)

        for k in mappings.iterkeys():
            attrs.pop(k)

        if not '__table__' in attrs:
            attrs['__table__'] = name.lower()

        attrs['__mappings__'] = mappings
        attrs['__primary_key__'] = primary_key
        attrs['__sql__'] = lambda self: _gen_sql(attrs['__table__'], mappings)
        for trigger in _triggers:
            if not trigger in attrs:
                attrs[trigger] = None

        return type.__new__(cls, name, bases, attrs)


class Model(dict):

    __metaclass__ = ModelMataclass

    def __init__(self, **kw):
        super(Model, self).__init__(**kw)

    def __getattr__(self, key):
        """
        get时生效，比如 a[key],  a.get(key)
        get时 返回属性的值
        """
        try:
            return self[key]
        except KeyError:
            raise AttributeError(r"'Dict' object has no attribute '%s'" % key)

    def __setattr__(self, key, value):
        """
        set时生效，比如 a[key] = value, a = {'key1': value1, 'key2': value2}
        set时添加属性
        """
        self[key] = value

    @classmethod
    def get_by_pk(cls, pk):
        """
        GET by primary key

        """
        d = opts.select_one('select * from %s where %s=?' % (cls.__table__, cls.__primary_key__.name), pk)
        return cls(**d) if d else None

    @classmethod
    def find_first(cls, where, *args):
        """
        通过where语句进行条件查询，返回1个查询结果。如果有多个查询结果
        仅取第一个，如果没有结果，则返回None
        """
        d = opts.select_one('select * from %s %s' % (cls.__table__, where), *args)
        return cls(**d) if d else None

    @classmethod
    def find_all(cls, *args):
        """
        查询所有字段， 将结果以一个列表返回
        """
        L = opts.select('select * from `%s`' % cls.__table__)
        return [cls(**d) for d in L]

    @classmethod
    def find_by(cls, where, *args):
        """
        通过where语句进行条件查询，将结果以一个列表返回
        """
        L = opts.select('select * from `%s` %s' % (cls.__table__, where), *args)
        return [cls(**d) for d in L]

    @classmethod
    def count_all(cls):
        """
        执行 select count(pk) from table语句，返回一个数值
        """
        return opts.select('select count(`%s`) from `%s`' % (cls.__primay_key__.name, cls.__table__))

    @classmethod
    def count_by(cls, where, *args):
        """
        通过select count(pk) from table where ...语句进行查询， 返回一个数值
        """
        return opts.select_int('select count(`%s`) from `%s` %s' % (cls.__primary_key__.name, cls.__table__, where),
                             *args)

    def update(self):
        """
        如果该行的字段属性有 updatable，代表该字段可以被更新
        用于定义的表（继承Model的类）是一个 Dict对象，键值会变成实例的属性
        所以可以通过属性来判断 用户是否定义了该字段的值
            如果有属性， 就使用用户传入的值
            如果无属性， 则调用字段对象的 default属性传入
            具体见 Field类 的 default 属性

        通过的db对象的update接口执行SQL
            SQL: update `user` set `passwd`=%s,`last_modified`=%s,`name`=%s where id=%s,
                 ARGS: (u'******', 1441878476.202391, u'Michael', 10190
        """
        self.pre_update and self.pre_update()
        L = []
        args = []
        for k, v in self.__mappings__.iteritems():
            if v.updatable:
                if hasattr(self, k):
                    arg = getattr(self, k)
                else:
                    arg = v.default
                    setattr(self, k, arg)
                L.append('`%s`=?' % k)
                args.append(arg)

        pk = self.__primary_key__.name
        args.append(getattr(self, pk))
        opts.update('update `%s` set %s where %s=?' % (self.__table__, ','.join(L), pk), *args)
        return self

    def delete(self):
        """
        通过db对象的 update接口 执行SQL
        SQL: delete from `user` where `id`=%s, ARGS: (10190,)
        """
        self.pre_delete and self.pre_delete()
        pk = self.__primary_key__.name
        args = (getattr(self, pk))
        opts.update('delete from `%s` where `%s`=?' % (self.__table__, pk), *args)
        return self

    def insert(self):
        """
        通过db对象的insert接口执行SQL
            SQL: insert into `user` (`passwd`,`last_modified`,`id`,`name`,`email`) values (%s,%s,%s,%s,%s),
            　　　　　 ARGS: ('******', 1441878476.202391, 10190, 'Michael', 'orm@db.org')
        """
        self.pre_insert and self.pre_insert()
        params = {}
        for k, v in self.__mappings__.iteritems():
            if v.insertable:
                if not hasattr(self, k):
                    setattr(self, k, v.default)
                params[v.name] = getattr(self, k)
        opts.insert('%s' % self.__table__, **params)
        return self







