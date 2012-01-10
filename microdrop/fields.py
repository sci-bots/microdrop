import re
from copy import deepcopy
import logging


class Field(object):
    def __init__(self, name, type=str, editable=True, default=None):
        self.name = name
        self.type = type
        self.editable = editable
        if default is None:
            self._default = self.type()
        else:
            self._default = self.type(default)

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __getstate__(self):
        return self.__dict__

    @property
    def default(self):
        return self._default


class FieldsStep(object):
    def __init__(self, **kwargs):
        for key, value in kwargs.iteritems():
            setattr(self, key, value)

    def __setstate__(self, state):
        self.__dict__.update(state)

    def __getstate__(self):
        return self.__dict__

    def __getattr__(self, name):
        if not name in dir(self):
            setattr(self, name, None)
        return object.__getattribute__(self, name)

    @property
    def attrs(self):
        return self.__dict__


class FieldSet(object):
    _fields = None
    _fields_type = None
    _step_class = None

    @property
    def field_names(self):
        return [f.attr for f in self.fields]

    @property
    def fields(self):
        return self._fields

    @property
    def name(self):
        return self._fields_name

    @property
    def step_class(self):
        if self._step_class is None:
            type_name = '_%sStep' % (self._fields_type)
            return FieldsStep
        else:
            return self._step_class


class CombinedStep(object):
    field_set_prefix = '%s__'

    def __init__(self, combined_fields, step_id=None):
        self.field_set_names = combined_fields.field_sets.keys()
        self.attributes = dict()

        for field_set_name, p in combined_fields.field_sets.iteritems():
            attr_values = dict([(f.name, f.default) for f in p.fields])
            logging.debug('[CombinedStep] attr_values=%s' % attr_values)
            self.attributes[field_set_name] = p.step_class(**dict([(f.name, f.default) for f in p.fields]))
        self.set_step(step_id)

    def get_fields_step(self, field_set_name):
        return self.attributes[field_set_name]
    
    def set_step(self, step_id):
        if 'DefaultFields' in self.field_set_names and step_id is not None:
            self.attributes['DefaultFields'].step = step_id

    def _mangle_name(self, field_set, name):
        return '%s%s' % (self.field_set_prefix % field_set.name, name)

    def __getattr__(self, name):
        logging.debug('[CombinedStep] name=%r' % name)
        if not name in ['attributes', 'field_set_names']:
            for p in self.field_set_names:
                field_set_prefix = self.field_set_prefix % p
                logging.debug('name=%s, field_set_prefix=%s' % (name, field_set_prefix))
                if name.startswith(field_set_prefix):
                    return getattr(self.attributes[p], name[len(field_set_prefix):])
        return object.__getattribute__(self, name)

    def __setattr__(self, name, value):
        logging.debug('[CombinedStep] set %s=%s' % (name, value))
        if not name in ['attributes', 'field_set_names']:
            for fields_type in self.field_set_names:
                field_set_prefix = '%s__' % fields_type
                if name.startswith(field_set_prefix):
                    setattr(self.attributes[fields_type], name[len(field_set_prefix):], value)
        self.__dict__[name] = value
        logging.debug(self.__dict__[name])

    def __str__(self):
        return '<CombinedStep attributes=%s>' % [(k, v.attrs) for k, v in self.attributes.iteritems()]


class DmfControlBoardStep(FieldsStep):
    def __init__(self, time, step, duration):
        self.time = time
        self.step = step
        self.duration = duration


class DefaultFields(FieldSet):
    _fields = [Field('step', type=int, editable=False),
                Field('duration', type=float, default=100.), ]
    _fields_name = 'DefaultFields'
    #_step_class = DmfControlBoardStep


class DmfControlBoardFields(FieldSet):
    _fields = [Field('voltage', type=int), Field('frequency', type=float, default=100.), ]
    _fields_name = 'DmfControlBoardPlugin'
    #_step_class = DmfControlBoardStep
