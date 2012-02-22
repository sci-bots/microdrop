from __future__ import division
import types
from base import N_, Validator
import flatland.util as util



class NANPnxx(Validator):
    """Integer"""

    def validate(self, element, state):
        if element.value is None:
            return False

        nxx = element.value

        if nxx < 200 or nxx in (311, 411, 511, 611, 711, 811, 911,
                                555, 990, 959, 958, 950, 700,
                                976,):
            return False

        element.u = unicode(nxx)
        return True

class NANPnpa_nxx(Validator):
    "Validates npa and nxx compound elements."

    incomplete = None

    invalid = N_(u'The %(label)s can not be verified.')

    def __init__(self, npa_element, nxx_element, errors_to=None,
                 lookup='aq', method='valid_npanxx', **kw):
        assert isinstance(npa_element, basestring)
        assert isinstance(nxx_element, basestring)
        assert isinstance(errors_to, (basestring, types.NoneType))

        Validator.__init__(self, *kw)

        self.npa = npa_element
        self.nxx = nxx_element
        self.lookup = lookup
        self.method = method

    def validate(self, element, state):
        npa = element.find(self.npa, single=True).value
        nxx = element.find(self.nxx, single=True).value

        if self.errors_to:
            err = element.find(self.errors_to)
        else:
            err = element

        if npa is None or nxx is None:
            return self.note_error(err, state, 'incomplete')

        # Will explode at run-time if state does not contain the lookup
        # tool.
        if hasattr(state, self.lookup):
            lookup = getattr(state, self.lookup)
        else:
            lookup = state[self.lookup]

        # catch exceptions here?
        valid = getattr(lookup, self.method)(npa, nxx)

        if not valid:
            return self.note_error(err, state, 'invalid')

        return True


class Luhn10(Validator):
    """Int or Long"""

    invalid = N_('The %(label)s was not entered correctly.')

    def validate(self, element, state):
        num = element.value
        if num is None:
            return self.note_error(element, state, 'invalid')

        if util.luhn10(num):
            return True

        return self.note_error(element, state, 'invalid')
