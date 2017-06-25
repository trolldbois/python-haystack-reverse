#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011 Loic Jaquemet loic.jaquemet+python@gmail.com
#

import logging

"""
the Python classes to represent the types of reversed structures.


Declaration classes:
- FieldType is the basic type of a field. int, array, pointer, record.... an id, fixed base type name, and a signature.
- Field is a Field declaration. Offset, name, FieldType.
    specialised subclasses are ArrayField, PointerField, ZeroField
- RecordType is the record declaration. type name, total size, Fields.
    total size should be equals to size of fields, but declaration is opened to gaps/missing fields.

- RecordField is a field that is a record declaration with a fieldtype of STRUCT.
    it has a field name, and a type name, an offset (its a field) 

1. the get_fields() method/property on RecordType, or RecordField, returns a list of Field
2. the signature property of a RecordType, or a Field
3. no declaration classes should allow to query for a value. This is the role of FieldInstance.


Instance classes (in structure.py):
- AnonymousRecord is the instance of a RecordType at a specific address.
- FieldInstance is the instance of a field, inside a AnonymousRecord, associated to an address.

4. instances can return values for field through the value property
    AnonymousRecord does not have a value property.
5. record instances have a get_fields() method/property iterator that returns instanciated field
    no full tree instanciation of fields, to avoid loops.
    FIXME: is there a dictionnary to keep dups out ?

InstantiatedField allows access to memory bytes through a value property
"""


log = logging.getLogger('field')


class FieldType(object):
    """
    the basic type of a field. int, array, pointer, record.... an id, fixed base type name, and a signature.
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


class RecordType(object):
    """
    the record declaration. type name, total size, Fields.
    total size should be equals to size of fields, but declaration is opened to gaps/missing fields.
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

    def get_field_at_offset(self, offset):
        """
        returns the field at a specific offset in this structure
        """
        if offset < 0 or offset > len(self):
            raise IndexError("Invalid offset")
        ## if self.get_reverse_level() < 10:
        ##    raise StructureNotResolvedError("Reverse level %d is too low for record 0x%x", self.get_reverse_level(), self.address)
        # find the field
        ret = [f for f in self.get_fields() if f.offset == offset]
        if len(ret) == 0:
            # then check for closest match
            ret = sorted([f for f in self.get_fields() if f.offset < offset])
            if len(ret) == 0:
                raise ValueError("Offset 0x%x is not in structure?!" % offset)  # not possible
            # the last field standing is the one ( ordered fields)
            ret = ret[-1]
            if offset < ret.offset + len(ret):
                return ret
            # in between fields. Can happens on un-analyzed structure.
            # or byte field
            raise IndexError('Offset 0x%x is in middle of field at offset 0x%x' % offset, ret.offset)
        elif len(ret) != 1:
            raise RuntimeError("there shouldn't multiple fields at the same offset")
        return ret[0]

    @property
    def signature(self):
        return ''.join([f.signature for f in self.get_fields()])

    @property
    def size(self):
        return len(self)

    def _get_type_name(self):
        return self.__type_name

    def _set_type_name(self, name):
        self.__type_name = name

    type_name = property(_get_type_name, _set_type_name, None, "The type name")

    def __len__(self):
        return int(self.__size)

    def to_string(self):
        # print self.fields
        self._fields.sort()
        field_string_lines = []
        for field in self._fields:
            field_string_lines.append('\t' + field.to_string())
        fields_string = '[ \n%s ]' % (''.join(field_string_lines))
        info = 'size:%d' % len(self)
        ctypes_def = '''
class %s(ctypes.Structure):  # %s
  _fields_ = %s

''' % (self.type_name, info, fields_string)
        return ctypes_def


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
    is a Field declaration. Offset, name, FieldType.
    specialised subclasses are ArrayField, PointerField, ZeroField
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

    @property
    def signature(self):
        return self.field_type.signature, self.size

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
        if not isinstance(other, Field):
            return False
        return self.offset < other.offset

    def __eq__(self, other):
        if not isinstance(other, Field):
            return False
        return self.field_type == other.field_type and self.offset == other.offset

    def __len__(self):
        return int(self.size)  # some long come and goes

    def __repr__(self):
        return str(self)

    def __str__(self):
        return '<Field offset:%d size:%s t:%s>' % (self.offset, self.size, self.field_type)

    def to_string(self):
        if self.is_pointer() or self.is_integer():
            comment = '# %s' % self.comment
        elif self.is_string():
            comment = '#  %s %s' % (self.comment, self.field_type.name)
        # moved to specialised classe
        elif self.is_record() or self.is_zeroes():
            raise TypeError('This is not reachable')
        else:
            # unknown
            comment = '# %s else' % (self.comment )
        # prep the string
        fstr = "( '%s' , %s ), %s\n" % (self.name, self.get_typename(), comment)
        return fstr


class PointerField(Field):
    """
    represent a pointer field.
    attributes such as ext_lib should be in this, because its a type information, most probably (fn pointer..)
    really, we should have a function_pointer subtype

    But pointee address is definitely an instance topic.
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
        # TODO, move to FieldInstance subtype ?
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

    def to_string(self):
        item_type = self.item_type
        # log.debug('P:%s I:%s Z:%s typ:%s' % (item_type.is_pointer(), item_type.is_integer(), item_type.is_zeroes(), item_type.name))
        log.debug("array type: %s", item_type.name)
        #
        comment = '# %s array' % self.comment
        fstr = "( '%s' , %s ), %s\n" % (self.name, self.get_typename(), comment)
        return fstr


class ZeroField(ArrayField):
    """
    Represents an array field of zeroes.
    """
    def __init__(self, name, offset, nb_item):
        super(ZeroField, self).__init__(name, offset, ZEROES, 1, nb_item)

    def is_zeroes(self):
        return True

    def to_string(self):
        comment = '''# %s zeroes: '\\x00'*%d''' % (self.comment, len(self))
        fstr = "( '%s' , %s ), %s\n" % (self.name, self.get_typename(), comment)
        return fstr


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

    def to_string(self):
        comment = '# field struct %s' % self.type_name
        fstr = "( '%s' , %s ), %s\n" % (self.name, self.get_typename(), comment)
        return fstr
