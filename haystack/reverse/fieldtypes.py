#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011 Loic Jaquemet loic.jaquemet+python@gmail.com
#

import logging
import os
import collections
import struct
import itertools

from haystack.config import Config
from haystack.utils import unpackWord
from haystack.reverse import re_string

import ctypes

log = logging.getLogger('field')

## Field related functions and classes

def findFirstNot(s, c):
  for i in xrange(len(s)):
    if s[i] != c:
      return i
  return -1



def makeArrayField(parent, fields): 
  #vaddr = parent.vaddr+firstField.offset
  newField = ArrayField(parent, fields)
  return newField


class FieldType(object):
  types = set()
  def __init__(self, _id, basename, typename, ctype, sig, isPtr=False):
    self._id = _id
    self.basename = basename
    self.ctypes = typename
    self._ctype = ctype
    self.sig = sig
    self.isPtr = isPtr
  @classmethod
  def makePOINTER(cls, typ):
    if typ == FieldType.STRING:
      return FieldType.STRING_POINTER
    return cls( typ._id+0xa, typ.basename+'_ptr', 'ctypes.POINTER(%s)'%(typ.ctypes), 'P', True)

  @classmethod
  def makeStructField(cls, parent, offset, fields): # struct name should be the vaddr... otherwise itgonna be confusing
    import structure
    vaddr = parent.vaddr+offset
    newfieldType = FieldTypeStruct('%lx'%(vaddr), fields)
    newfieldType.setStruct(structure.makeStructure(parent.context, vaddr, len(newfieldType) ) )
    newField = Field(parent, offset, newfieldType, len(newfieldType), False)
    return newField

  def __cmp__(self, other):
    try:
      return cmp(self._id, other._id)
    except AttributeError,e:
      return -1

  def __hash__(self):
    return hash(self._id)

  def __str__(self):
    return '<FieldType %s>'%(self.basename)

  def __repr__(self):
    return '<t:%s>'%(self.basename)

class FieldTypeStruct(FieldType):
  def __init__(self, name, fields):
    FieldType.__init__(self, 0x1, 'struct', name, 'K', isPtr=False)
    self.size = sum([len(f) for f in fields])
    self.elements = fields
    #TODO s2[0].elements[0].typename.elements[0] is no good

  def setStruct(self, struct):
    self._struct = struct
    
  def getStruct(self):
    return self._struct

  def __len__(self):
    return self.size
  
class FieldTypeArray(FieldType):
  def __init__(self, basicTypeName):
    FieldType.__init__(self, 0x60, 'array_%s'%basicTypeName, None, 'a', isPtr=False)


FieldType.UNKNOWN  = FieldType(0x0,  'untyped',   'ctypes.c_ubyte', ctypes.c_ubyte,   'u')
FieldType.STRUCT   = FieldType(0x1, 'struct',      'Structure', None,   'K')
FieldType.ZEROES   = FieldType(0x2,  'zerroes',   'ctypes.c_ubyte', ctypes.c_ubyte,  'z')
FieldType.STRING   = FieldType(0x4, 'text',      'ctypes.c_char', ctypes.c_char,   'T')
FieldType.STRINGNULL   = FieldType(0x6, 'text0',      'ctypes.c_char', ctypes.c_char,   'T')
FieldType.STRING_POINTER   = FieldType(0x4+0xa, 'text_ptr',      'ctypes.c_char_p', ctypes.c_char_p, 's', True)
FieldType.INTEGER  = FieldType(0x18, 'int',       'ctypes.c_uint', ctypes.c_uint,   'I')
FieldType.SMALLINT = FieldType(0x8, 'small_int', 'ctypes.c_uint', ctypes.c_uint,   'i')
FieldType.SIGNED_SMALLINT = FieldType(0x28, 'signed_small_int', 'ctypes.c_int', ctypes.c_uint,   'i')
FieldType.ARRAY    = FieldType(0x40, 'array',     'Array',  None,  'a')
FieldType.BYTEARRAY    = FieldType(0x50, 'array',     'ctypes.c_ubyte', ctypes.c_ubyte,  'a')
#FieldType.ARRAY_CHAR_P = FieldType(0x9, 'array_char_p',     'ctypes.c_char_p',   'Sp')
FieldType.POINTER  = FieldType(0xa,  'ptr',       'ctypes.c_void_p', ctypes.c_void_p, 'P', True)
FieldType.PADDING  = FieldType(0xff, 'pad',       'ctypes.c_ubyte', ctypes.c_ubyte,  'X')

  
class Field:
  def __init__(self, astruct, offset, typename, size, isPadding):
    self.struct = astruct
    self.offset = offset
    self.size = size
    self.typename = typename
    self._ctype = None
    self.padding = isPadding
    self.typesTested = []
    self.value = None
    self.comment = ''
    self.usercomment = ''  
    self.decoded = True
    
  def setComment(self, txt):
    self.usercomment = '# %s'%txt
  def getComment(self):
    return self.usercomment
    
  def isString(self): # null terminated
    return self.typename in [ FieldType.STRING, FieldType.STRINGNULL, FieldType.STRING_POINTER]
  def isPointer(self): # 
    return self.typename.isPtr
  def isZeroes(self): # 
    return self.typename == FieldType.ZEROES
  def isArray(self): # will be overloaded
    return self.typename == FieldType.ARRAY or self.typename == FieldType.BYTEARRAY 
  def isInteger(self): # 
    return self.typename == FieldType.INTEGER or self.typename == FieldType.SMALLINT or self.typename == FieldType.SIGNED_SMALLINT
  
  
  def setCtype(self, name):
    self._ctype = name
  
  def getCtype(self):
    if self._ctype is None:
      return self.typename._ctype
    return self._ctype
    # FIXME TODO

  def getTypename(self):
    if self.isString() or self.isZeroes():
      return '%s * %d' %(self.typename.ctypes, len(self) )
    elif self.isArray():
      return '%s * %d' %(self.typename.ctypes, len(self)/self.element_size ) #TODO should be in type
    elif self.typename == FieldType.UNKNOWN:
      return '%s * %d' %(self.typename.ctypes, len(self) )
    return self.typename.ctypes
  
  def setName(self, name):
    self.name = name
  
  def getName(self):
    if hasattr(self, 'name'):
      return self.name
    else:
      return '%s_%s'%(self.typename.basename, self.offset)
    
  def __hash__(self):
    return hash( (self.offset, self.size, self.typename) )
      
  #def tuple(self):
  #  return (self.offset, self.size, self.typename)

  def __cmp__(self, other):
    # XXX : Perf... cmp sux
    try:
      if self.offset < other.offset:
        return -1
      elif self.offset > other.offset:
        return 1
      elif (self.offset, self.size, self.typename) == (other.offset, other.size, other.typename):
        return 0
      # last chance, expensive cmp
      return cmp((self.offset, self.size, self.typename), (other.offset, other.size, other.typename))
    except AttributeError,e:
      #if not isinstance(other, Field):
      return -1

  def __len__(self):
    return int(self.size) ## some long come and goes

  def __str__(self):
    i = 'new'
    try:
      if self in self.struct._fields:
        i = self.struct._fields.index(self)
    except ValueError, e:
      log.warning('self in struct.fields but not found by index()')
    return '<Field %s offset:%d size:%s t:%s'%(i, self.offset, self.size, self.typename)
    
  def getValue(self, maxLen):
    bytes = self._getValue(maxLen)
    bl = len(str(bytes))
    if bl >= maxLen:
      bytes = str(bytes[:maxLen/2])+'...'+str(bytes[-(maxLen/2):]) # idlike to see the end
    return bytes
        
  def _getValue(self, maxLen):
    if len(self) == 0:
      return '<-haystack no pattern found->'
    if self.isString():
      bytes = repr(self.value)
    elif self.isInteger():
      return self.value 
    elif self.isZeroes():
      bytes=repr(self.value)#'\\x00'*len(self)
    elif self.isArray():
      log.warning('ARRAY in Field type, %s'%self.typename)
      bytes= ''.join(['[',','.join([el.toString() for el in self.elements]),']'])
    elif self.padding or self.typename == FieldType.UNKNOWN:
      bytes = self.struct.bytes[self.offset:self.offset+len(self)]
    else: # bytearray, pointer...
      return self.value
    return bytes
  
  def getSignature(self):
    return (self.typename, self.size)
  
  def toString(self, prefix=''):
    #log.debug('isPointer:%s isInteger:%s isZeroes:%s padding:%s typ:%s'
    #    %(self.isPointer(), self.isInteger(), self.isZeroes(), self.padding, self.typename.basename) )
  
    if self.isPointer():
      comment = '# @ 0x%0.8x %s %s'%( self.value, self.comment, self.usercomment ) 
    elif self.isInteger():
      comment = '#  0x%x %s %s'%( self.getValue(Config.commentMaxSize), self.comment, self.usercomment ) 
    elif self.isZeroes():
      comment = '# %s %s zeroes:%s'%( self.comment, self.usercomment, self.getValue(Config.commentMaxSize)  ) 
    elif self.isString():
      comment = '#  %s %s %s:%s'%( self.comment, self.usercomment, self.encoding, self.getValue(Config.commentMaxSize) ) 
    else:
      #unknown
      comment = '# %s %s else bytes:%s'%( self.comment, self.usercomment, repr(self.getValue(Config.commentMaxSize)) ) 
          
    fstr = "%s( '%s' , %s ), %s\n" % (prefix, self.getName(), self.getTypename(), comment) 
    return fstr
    

class ArrayField(Field):
  def __init__(self, astruct, elements): #, basicTypename, basicTypeSize ): # use first element to get that info
    self.struct = astruct
    self.offset = elements[0].offset
    self.typename = FieldTypeArray(elements[0].typename.basename)

    self.elements = elements
    self.nbElements = len(elements)
    self.basicTypeSize = len(elements[0])
    self.basicTypename = elements[0].typename

    self.size = self.basicTypeSize * len(self.elements)
    self.padding = False
    self.value = None
    self.comment = ''
    self.usercomment = ''  
    self.decoded = True
  
  def isArray(self):
    return True

  def getCtype(self):
    return self._ctype

  def getTypename(self):
    return '%s * %d' %(self.basicTypename.ctypes, self.nbElements )

  def _getValue(self, maxLen):
    # show number of elements and elements types
    #bytes= ''.join(['[',','.join([str(el._getValue(10)) for el in self.elements]),']'])
    bytes= '%d x '%(len(self.elements)) + ''.join(['[',','.join([el.toString('') for el in self.elements]),']'])
    # thats for structFields
    #bytes= '%d x '%(len(self.elements)) + ''.join(['[',','.join([el.typename for el in el0.typename.elements]),']'])
    return bytes

  def toString(self, prefix):
    log.debug('isPointer:%s isInteger:%s isZeroes:%s padding:%s typ:%s'
        %(self.isPointer(), self.isInteger(), self.isZeroes(), self.padding, self.typename.basename) )
    #
    comment = '# %s %s array:%s'%( self.comment, self.usercomment, self.getValue(Config.commentMaxSize) )
    fstr = "%s( '%s' , %s ), %s\n" % (prefix, self.getName(), self.getTypename(), comment) 
    return fstr


def isIntegerType(typ):
  return typ == FieldType.INTEGER or typ == FieldType.SMALLINT or typ == FieldType.SIGNED_SMALLINT 



