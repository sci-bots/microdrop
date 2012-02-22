from flatland.util import Maybe


YES = (u'1', u'true', u'True', u't', u'on', u'yes')
NO = (u'0', u'false', u'False', u'nil', u'off', u'no')
MAYBE = (u'auto',)


def parse_trool(value):
    if value is True or value is False or value is Maybe:
        return value
    if isinstance(value, unicode):
        value = value.lower()
    else:
        value = unicode(value).lower()
    if value in YES:
        return True
    if value in NO:
        return False
    if value in MAYBE:
        return Maybe
    return Maybe
