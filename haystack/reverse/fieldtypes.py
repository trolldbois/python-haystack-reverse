#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011 Loic Jaquemet loic.jaquemet+python@gmail.com
#

import logging

"""
the Python classes to represent the guesswork record and field typing of
allocations.

Field is the base class of a Field declaration. Offset, name, type.
RecordField is "just" a field with a field_type of STRUCT., an offset, a field name, a type, and the declaration of its type
    The declaration of its type is as part of it's RecordType inheritance.
    field_type is not renamed to RecordType's name.

Now each field will get instanciated when AnonymousStruct returns get_fields(), 
and these instance inherits the Field and the InstanciantedField classes.

InstanciatedField allows access to memory bytes through a value property
"""


log = logging.getLogger('field')

# Field related functions and classes


class FieldType(object):
    """
    Represents the type of a field.
    """
    types = set()

    def __init__(self, _id, _name, _signature):
        self.__id = _id
        self.__name = _name
        self.__sig = _signature

    @property
    def id(self):
        return self.__id

    @property
    def name(self):
        return self.__name

    @property
    def signature(self):
        return self.__sig

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    def __str__(self):
        return '<FieldType %s>' % self.name

    def __repr__(self):
        return '<t:%s>' % self.name


# class FieldTypeStruct(FieldType):
#     """
#     Fields that are really inner records type (structure).
#     """
#
#     def __init__(self, _typename):
#         assert isinstance(_typename, str)
#         super(FieldTypeStruct, self).__init__(0x1, _typename, 'K')
#
#     def __str__(self):
#         return self.name
#
#
# class FieldTypeArray(FieldType):
#     """
#     An array type
#     """
#     def __init__(self, item_type, item_size, nb_items):
#         super(FieldTypeArray, self).__init__(0x60, '%s*%d' % (item_type.name, nb_items), 'a')
#         self.nb_items = nb_items
#         self.item_type = item_type
#         self.item_size = item_size
#         self.size = item_size*nb_items
#
#
# class RecordTypePointer(FieldType):
#     def __init__(self, _type):
#         #if typ == STRING:
#         #    return STRING_POINTER
#         super(RecordTypePointer, self).__init__(_type.id + 0xa, 'ctypes.POINTER(%s)' % _type.name, 'P')


# setup all the know types that are interesting to us
UNKNOWN = FieldType(0x0, 'ctypes.c_ubyte', 'u')
STRUCT = FieldType(0x1, 'Structure', 'K')
ZEROES = FieldType(0x2, 'ctypes.c_ubyte', 'z')
STRING = FieldType(0x4, 'ctypes.c_char', 'T')
STRING16 = FieldType(0x14, 'ctypes.c_char', 'T')
STRINGNULL = FieldType(0x6, 'ctypes.c_char', 'T')
STRING_POINTER = FieldType(0x4 + 0xa, 'ctypes.c_char_p', 's')
INTEGER = FieldType(0x18, 'ctypes.c_uint', 'I')
SMALLINT = FieldType(0x8, 'ctypes.c_uint', 'i')
SIGNED_SMALLINT = FieldType(0x28, 'ctypes.c_int', 'i')
ARRAY = FieldType(0x40, 'Array', 'a')
BYTEARRAY = FieldType(0x50, 'ctypes.c_ubyte', 'a')
# ARRAY_CHAR_P = FieldType(0x9, 'array_char_p',     'ctypes.c_char_p',   'Sp')
POINTER = FieldType(0xa, 'ctypes.c_void_p', 'P')
PADDING = FieldType(0xff, 'ctypes.c_ubyte', 'X')


class Field(object):
    """
    Class that represent a Field instance, a FieldType instance.
    """
    def __init__(self, name, offset, _type, size, is_padding):
        self._name = name
        self._offset = offset
        assert isinstance(_type, FieldType)
        self._field_type = _type
        self._size = size
        self._padding = is_padding
        self._comment = '#'

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, _name):
        if _name is None:
            self._name = '%s_%s' % (self.field_type.name, self.offset)
        else:
            self._name = _name

    @property
    def offset(self):
        return self._offset

    @property
    def field_type(self):
        return self._field_type

    @property
    def size(self):
        return self._size

    @property
    def padding(self):
        return self._padding

    @property
    def comment(self):
        return self._comment

    @comment.setter
    def comment(self, txt):
        self._comment = '# %s' % txt

    def is_string(self):  # null terminated
        return self.field_type in [STRING, STRING16, STRINGNULL, STRING_POINTER]

    def is_pointer(self):
        # we could be a pointer or a pointer string
        # return issubclass(self.__class__, PointerField)
        return self.field_type in [POINTER, STRING_POINTER]

    def is_zeroes(self):
        return self.field_type == ZEROES

    def is_array(self):  # will be overloaded
        return self.field_type in [ARRAY, BYTEARRAY]

    def is_integer(self):
        return self.field_type in [INTEGER, SMALLINT, SIGNED_SMALLINT]

    def is_record(self):
        return self.field_type == STRUCT

    def is_gap(self):
        return self.field_type == UNKNOWN

    def get_typename(self):
        if self.is_string() or self.is_zeroes():
            return '%s*%d' % (self.field_type.name, len(self))
        elif self.is_array():
            # TODO should be in type
            return '%s*%d' % (self.field_type.name, len(self) / self.nb_items)
        elif self.field_type == UNKNOWN:
            return '%s*%d' % (self.field_type.name, len(self))
        return self.field_type.name

    def __hash__(self):
        return hash((self.offset, self.size, self.field_type))

    def __lt__(self, other):
        return self.offset < other.offset

    def __eq__(self, other):
        return self.field_type == other.field_type and self.offset == other.offset

    # # FIXME obselete
    # def __cmp__(self, other):
    #     # XXX : Perf... cmp sux
    #     try:
    #         if self.offset < other.offset:
    #             return -1
    #         elif self.offset > other.offset:
    #             return 1
    #         elif (self.offset, self.size, self.field_type) == (other.offset, other.size, other.field_type):
    #             return 0
    #         # last chance, expensive cmp
    #         return cmp((self.offset, self.size, self.field_type),
    #                    (other.offset, other.size, other.field_type))
    #     except AttributeError as e:
    #         # if not isinstance(other, Field):
    #         return -1

    def __len__(self):
        return int(self.size)  # some long come and goes

    def __repr__(self):
        return str(self)

    def __str__(self):
        return '<Field offset:%d size:%s t:%s>' % (self.offset, self.size, self.field_type)

    def _get_signature(self):
        return self.field_type.signature, self.size
    signature = property(_get_signature, None, None, "Field Signature")

    def to_string(self, value):
        if value is None:
            value = 0
        if self.is_pointer():
            comment = '# @ 0x%0.8x %s' % (value, self.comment)
        elif self.is_integer():
            comment = '# 0x%x %s' % (value, self.comment)
        elif self.is_zeroes():
            comment = '''# %s zeroes: '\\x00'*%d''' % (self.comment, len(self))
        elif self.is_string():
            comment = '#  %s %s: %s' % (self.comment, self.field_type.name, value)
        elif self.is_record():
            comment = '# field struct %s' % self.type_name
        else:
            # unknown
            comment = '# %s else bytes:%s' % (self.comment, repr(value))
        # prep the string
        fstr = "( '%s' , %s ), %s\n" % (self.name, self.get_typename(), comment)
        return fstr


class PointerField(Field):
    """
    represent a pointer field.
    attributes such as ext_lib should be in this, because its a type information, most probably (fn pointer..)
    really, we should have a function_pointer subtype
    """
    def __init__(self, name, offset, size):
        super(PointerField, self).__init__(name, offset, POINTER, size, False)
        self.__pointee = None
        self.__pointer_to_ext_lib = False
        # ??
        self._child_addr = 0
        self._child_desc = None
        self._child_type = None

    @property
    def pointee(self):
        return self.__pointee

    @pointee.setter
    def pointee(self, pointee_field):
        self.__pointee = pointee_field

    def is_pointer_to_string(self):
        # if hasattr(self, '_ptr_to_ext_lib'):
        #    return False
        return self.pointee.is_string()

    def is_pointer_to_ext_lib(self):
        return self.__pointer_to_ext_lib

    def set_pointer_to_ext_lib(self):
        self.__pointer_to_ext_lib = True

    def set_pointee_addr(self, addr):
        self._child_addr = addr

    def set_pointee_desc(self, desc):
        self._child_desc = desc

    def set_pointee_ctype(self, _type):
        self._child_type = _type


class ArrayField(Field):
    """
    Represents an array field.
    """
    # , basicTypename, basicTypeSize ): # use first element to get that info
    def __init__(self, name, offset, item_type, item_size, nb_items):
        size = item_size * nb_items
        self.__item_type = item_type
        self.__item_size = item_size
        self.__nb_items = nb_items
        super(ArrayField, self).__init__(name, offset, ARRAY, size, False)

    @property
    def item_type(self):
        return self.__item_type

    @property
    def item_size(self):
        return self.__item_size

    @property
    def nb_items(self):
        return self.__nb_items

    def __len__(self):
        return self.__nb_items

    def get_typename(self):
        return '%s*%d' % (self.item_type.name, self.nb_items)
        #return self.field_type.name

    def is_array(self):
        return True

    def _get_value(self, _record, maxLen=120):
        return None

    def to_string(self, _record, prefix=''):
        item_type = self.item_type
        # log.debug('P:%s I:%s Z:%s typ:%s' % (item_type.is_pointer(), item_type.is_integer(), item_type.is_zeroes(), item_type.name))
        log.debug("array type: %s", item_type.name)
        #
        comment = '# %s array' % self.comment
        fstr = "%s( '%s' , %s ), %s\n" % (prefix, self.name, self.get_typename(), comment)
        return fstr


class ZeroField(ArrayField):
    """
    Represents an array field of zeroes.
    """
    def __init__(self, name, offset, nb_item):
        super(ZeroField, self).__init__(name, offset, ZEROES, 1, nb_item)

    def is_zeroes(self):
        return True


#    def to_string(self, *args):
#        # print self.fields
#        fieldsString = '[ \n%s ]' % (''.join([field.to_string(self, '\t') for field in self.get_fields()]))
#        info = 'rlevel:%d SIG:%s size:%d' % (self.get_reverse_level(), self.get_signature(), len(self))
#        ctypes_def = '''
#class %s(ctypes.Structure):  # %s
#  _fields_ = %s
#
#''' % (self.name, info, fieldsString)
#        return ctypes_def

class RecordType(object):
    """
    The type of a record.

    """
    def __init__(self, name, size, fields):
        self.__type_name = name
        self.__size = int(size)
        self._fields = fields
        self._fields.sort()

    def get_fields(self):
        return [x for x in self._fields]

    def get_field(self, name):
        for f in self.get_fields():
            if f.name == name:
                return f
        raise ValueError('No such field named %s', name)

    @property
    def size(self):
        return len(self)

    @property
    def type_name(self):
        return self.__type_name

    def __len__(self):
        return int(self.__size)

    def to_string(self):
        # print self.fields
        self._fields.sort()
        field_string_lines = []
        for field in self._fields:
            field_string_lines.append('\t'+field.to_string(None))
        fields_string = '[ \n%s ]' % (''.join(field_string_lines))
        info = 'size:%d' % len(self)
        ctypes_def = '''
class %s(ctypes.Structure):  # %s
  _fields_ = %s

''' % (self.type_name, info, fields_string)
        return ctypes_def

    def _get_signature(self):
        return
    signature = property(_get_signature, None, None, "The Record type signature")


# FIXME, why use RecordType already ?
# just says its a fieldtypes.STRUCT
class RecordField(Field, RecordType):
    """
    make a record field
    """
    def __init__(self, field_name, offset, field_type_name, fields):
        size = sum([len(f) for f in fields])
        self.__type_name = field_type_name
        RecordType.__init__(self, field_type_name, size, fields)
        # the name is the name of the field
        Field.__init__(self, field_name, offset, STRUCT, size, False)
        # is_record() should return true
        assert self.field_type == STRUCT

    #@deprecated
    def get_typename(self):
        return self.type_name


class InstantiatedField(Field):
    """
    An instanciated field
    """

    def __init__(self, field_decl, parent):
        self._field_decl = field_decl
        Field.__init__(self, self._field_decl.name, self._field_decl.offset, self._field_decl.field_type,
                       self._field_decl.size, self._field_decl.padding)
        self.__parent = parent

    def __getattr__(self, item):
        for obj in [self] + self._field_decl.__class__.mro():
            if item in self.__dict__:
                if isinstance(self.__dict__[item], property):
                    return self.__dict__[item].fget(self)
                return self.__dict__[item]
        for obj in [self._field_decl] + self._field_decl.__class__.mro():
            if item in obj.__dict__:
                if isinstance(obj.__dict__[item], property):
                    return obj.__dict__[item].fget(self._field_decl)
                return obj._field_decl.__dict__[item]
        raise AttributeError('field %s not found in %s wrapping %s' % (item, self, self._field_decl))

    def __get_value_for_field(self, max_len=120):
        my_bytes = self.__get_value_for_field_inner(max_len)
        if isinstance(my_bytes, str):
            bl = len(str(my_bytes))
            if bl >= max_len:
                my_bytes = my_bytes[:max_len // 2] + '...' + \
                    my_bytes[-(max_len // 2):]  # idlike to see the end
        return my_bytes

    def __get_value_for_field_inner(self, max_len=120):
        word_size = self.__parent.target.get_word_size()
        if len(self) == 0:
            return '<-haystack no pattern found->'
        if self.is_string():
            if self.field_type == STRING16:
                try:
                    my_bytes = "%s" % (repr(self.__parent.bytes[self.offset:self.offset + self.size].decode('utf-16')))
                except UnicodeDecodeError as e:
                    log.error('ERROR ON : %s', repr(self.__parent.bytes[self.offset:self.offset + self.size]))
                    my_bytes = self.__parent.bytes[self.offset:self.offset + self.size]
            else:
                my_bytes = "'%s'" % (self.__parent.bytes[self.offset:self.offset + self.size])
        elif self.is_integer():
            # what about endianness ?
            endianess = '<' # FIXME dsa self.endianess
            data = self.__parent.bytes[self.offset:self.offset + word_size]
            val = self.__parent.target.get_target_ctypes_utils().unpackWord(data, endianess)
            return val
        elif self.is_zeroes():
            my_bytes = repr('\\x00'*len(self))
        elif self.is_array():
            my_bytes = self.__parent.bytes[self.offset:self.offset + len(self)]
        elif self.padding or self.field_type == UNKNOWN:
            my_bytes = self.__parent.bytes[self.offset:self.offset + len(self)]
        elif self.is_pointer():
            data = self.__parent.bytes[self.offset:self.offset + word_size]
            if len(data) != word_size:
                print(repr(data), len(data))
                import pdb
                pdb.set_trace()
            val = self.__parent.target.get_target_ctypes_utils().unpackWord(data)
            return val
        else:  # bytearray, pointer...
            my_bytes = self.__parent.bytes[self.offset:self.offset + len(self)]
        return my_bytes

    def to_string(self):
        if self.is_pointer():
            comment = '# @ 0x%0.8x %s' % (self.value, self.comment)
        elif self.is_integer():
            comment = '# 0x%x %s' % (self.value, self.comment)
        elif self.is_zeroes():
            comment = '''# %s zeroes: '\\x00'*%d''' % (self.comment, len(self))
        elif self.is_string():
            comment = '#  %s %s: %s' % (self.comment, self.field_type.name, self.value)
        elif self.is_record():
            comment = '# field struct %s' % self.type_name
        else:
            # unknown
            comment = '# %s else bytes:%s' % (self.comment, repr(self.value))
        # prep the string
        fstr = "( '%s' , %s ), %s\n" % (self.name, self.get_typename(), comment)
        return fstr

    #
    value = property(__get_value_for_field, None, None, "Get value from bytes")