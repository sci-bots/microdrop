import re

from flatland import AdaptationError, Long
from flatland.util import Unspecified
from flatland.validation import (
    Converted,
    Luhn10,
    Present,
    Validator,
)

VISA = 'Visa',
MASTERCARD = 'MasterCard',
AMEX = 'American Express',
DISCOVER = 'Discover',


class CreditCardNumber(Long):
    accepted = (VISA, MASTERCARD, AMEX)

    def __init__(self, value=Unspecified, **kw):
        validators = [
            self.Present(),
            self.Converted(),
            self.Luhn10(),
            self.AcceptedType()
        ]
        kw.setdefault('validators', validators)
        Long.__init__(self, value, **kw)

    def adapt(self, value):
        if value is None:
            return None
        elif isinstance(value, (int, long)):
            return long(value)

        value = _from_string(value)

        if value is None:
            raise AdaptationError()

        return value

    def serialize(self, value):
        if value is None:
            return u''
        elif isinstance(value, long):
            return _pretty_print(value)
        else:
            return unicode(value)

    Present = Present

    Converted = Converted

    Luhn10 = Luhn10

    class AcceptedType(Validator):
        def _formatter(element, state):
            accepted = element.accepted
            if len(accepted) > 2:
                types = (', '.join(label for label, in accepted) +
                       ', and ' + accepted[-1][0])
            elif len(accepted) == 2:
                types = ' and '.join(label for label, in accepted)
            else:
                types = accepted[0][0]

            return u'We accept %s' % types

        not_accepted = _formatter

        def validate(self, element, state):
            type_ = _card_type(element.value)
            if type_ in element.accepted:
                return True

            return self.note_error(element, state, 'not_accepted')

_re_visa = re.compile(r'^4\d{12}\d{3}?$')
_re_mc   = re.compile(r'^5[1-5]\d{14}$')
_re_amex = re.compile(r'^3[47]\d{13}$')
_re_disc = re.compile(r'^6011\d{12}$')

def _card_type(number):
    assert isinstance(number, (int, long))

    as_str = str(number)

    if _re_visa.match(as_str):
        return VISA
    elif _re_mc.match(as_str):
        return MASTERCARD
    elif _re_amex.match(as_str):
        return AMEX
    elif _re_disc.match(as_str):
        return DISCOVER
    else:
        return None

_re_strip = re.compile(r'[^0-9]')
_re_filler = re.compile(r'^[0-9\s-]{15,}$')

def _from_string(number):
    if number is None:
        return None
    elif isinstance(number, (int, long)):
        return long(number)
    elif not isinstance(number, basestring):
        return None

    if not _re_filler.match(number):
        return None

    return long(_re_strip.sub(u'', unicode(number)))

def _pretty_print(number):
    if number is None:
        return u''

    s = unicode(number)

    if len(s) == 16:
        return u'%s-%s-%s-%s' % (s[0:4], s[4:8], s[8:12], s[12:16])
    elif len(s) == 15:
        return u'%s-%s-%s' % (s[0:4], s[4:10], s[10:15])
    elif len(s) == 13:
        return u'%s-%s-%s-%s' % (s[0:4], s[4:7], s[7:10], s[10:13])
    else:
        return s
