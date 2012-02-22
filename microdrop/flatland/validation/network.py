# -*- coding: utf-8; fill-column: 78 -*-
"""Network address and URL validation."""
import re
import urlparse

from base import N_, Validator


class IsEmail(Validator):
    """Validates email addresses.

    The default behavior takes a very permissive stance on allowed characters
    in the **local-part** and a relatively strict stance on the **domain**.
    Given **local-part@domain**:

    - **local-part** must be present and contain at least one non-whitespace
      character.  Any character is permitted, including international
      characters.

    - **domain** must be preset, less than 253 characters and each
      dot-separated component must be 63 characters or less.  **domain** may
      contain non-ASCII international characters, and will be converted to IDN
      representation before length assertions are applied.  No top level
      domain validations are applied.

    **Attributes**

    .. attribute:: nonlocal

      Default ``True``.  When true, require at minimum two domain name
      components and reject local email addresses such as
      ``postmaster@localhost`` or ``user@workstation``.

    .. attribute:: local_part_pattern

      No default.  If present, a compiled regular expression that will be
      matched to the **local-part**.  Override this to implement more
      stringent checking such as RFC-compliant addresses.

    .. attribute:: domain_pattern

      Defaults to a basic domain-validating regular expression with no notion
      of valid top level domains.  Override this to require certain TLDs (or
      alternately and more simply, add another validator to your chain that
      checks the endings of the string against your list of TLDs.)

      The default pattern rejects the valid but obscure quoted IP-address form
      (``[1.2.3.4]``).

    **Messages**

    .. attribute:: invalid

      Emitted if the email address is not valid.

    """

    invalid = N_(u'%(label)s is not a valid email address.')

    nonlocal = True

    local_part_pattern = None

    domain_pattern = re.compile(r'^(?:[a-z0-9\-]+\.)*[a-z0-9\-]+$',
                                re.IGNORECASE)

    def validate(self, element, state):
        addr = element.u
        if addr.count(u'@') != 1:
            return self.note_error(element, state, 'invalid')

        local_part, domain = addr.split(u'@')
        if not local_part or local_part.isspace():
            return self.note_error(element, state, 'invalid')

        # optional local part validation
        if (self.local_part_pattern and
            not self.local_part_pattern.match(local_part)):
            return self.note_error(element, state, 'invalid')

        try:
            # convert domain to ascii
            domain = domain.encode('idna')
        except UnicodeError:
            return self.note_error(element, state, 'invalid')

        if len(domain) > 253:
            return self.note_error(element, state, 'invalid')

        if not self.domain_pattern.match(domain):
            return self.note_error(element, state, 'invalid')

        labels = domain.split('.')
        if len(labels) == 1 and self.nonlocal:
            return self.note_error(element, state, 'invalid')

        if not all(len(label) < 64 for label in labels):
            return self.note_error(element, state, 'invalid')

        return True


# ordered generic URL part names according to urlparse
_url_parts = ['scheme', 'netloc', 'path', 'params', 'query', 'fragment']

class URLValidator(Validator):
    """A general URL validator.

    Validates that a URL is well-formed and may optionally restrict
    the set of valid schemes and other URL components.

    **Attributes**

    .. attribute:: allowed_schemes

      Restrict URLs to just this sequence of named schemes, or allow
      all schemes with ('*',).  Defaults to all schemes.  Example::

        allowed_schemes = ('http', 'https', 'ssh')

    .. attribute:: allowed_parts

      A sequence of 0 or more part names in :mod:`urlparse`'s
      vocabulary::

        'scheme', 'netloc', 'path', 'params', 'query', 'fragment'

      Defaults to all parts allowed.

    .. attribute:: urlparse

      By default the :mod:`urlparse` module, but may be replaced by
      any object that implements :func:`urlparse.urlparse` and
      :func:`urlparse.urlunparse`.

    **Messages**

    .. attribute:: bad_format

      Emitted for an unparseable URL.

    .. attribute:: blocked_scheme

      Emitted if the URL ``scheme:`` is not present in
      :attr:`allowed_schemes`.

    .. attribute:: blocked_part

      Emitted if the URL has a component not present in
      :attr:`allowed_parts`.

    """

    bad_format = N_("%(label)s is not a valid URL.")
    blocked_scheme = N_("%(label)s is not a valid URL.")
    blocked_part = N_("%(label)s is not a valid URL.")

    allowed_schemes = ('*',)
    allowed_parts = set(_url_parts)
    urlparse = urlparse

    def validate(self, element, state):
        if element.value is None:
            return self.note_error(element, state, 'bad_format')

        try:
            url = self.urlparse.urlparse(element.value.strip())
        except Exception:
            return self.note_error(element, state, 'bad_format')

        scheme_name = url.scheme
        if scheme_name == u'':
            return self.note_error(element, state, 'blocked_scheme')
        elif self.allowed_schemes != ('*',):
            if scheme_name not in self.allowed_schemes:
                return self.note_error(element, state, 'blocked_scheme')

        for part in _url_parts:
            if (part not in self.allowed_parts and
                getattr(url, part) != ''):
                return self.note_error(element, state, 'blocked_part')
        return True


class HTTPURLValidator(Validator):
    """Validates ``http`` and ``https`` URLs.

    Validates that an ``http``-like URL is well-formed and may
    optionally require and restrict the permissible values of its
    components.

    **Attributes**

    .. attribute:: all_parts

      A sequence of known URL parts.  Defaults to the full 10-tuple of
      names in :mod:`urlparse`'s vocabulary for http-like URls.

    .. attribute:: required_parts

      A mapping of part names.  If value is True, the part is
      required.  The value may also be a sequence of strings; the
      value of the part must be present in this collection to
      validate.

      The default requires a ``scheme`` of 'http' or 'https'.

    .. attribute:: forbidden_parts

      A mapping of part names.  If value is True, the part is
      forbidden and validation fails.  The value may also be a
      sequence of strings; the value of the part must not be present
      in this collection to validate.

      The default forbids ``username`` and ``password`` parts.

    .. attribute:: urlparse

      By default the :mod:`urlparse` module, but may be replaced by
      any object that implements :func:`urlparse.urlparse` and
      :func:`urlparse.urlunparse`.

    **Messages**

    .. attribute:: bad_format

      Emitted for an unparseable URL.

    .. attribute:: required_part

      Emitted if URL is missing a part present in
      :attr:`required_parts`.

    .. attribute:: forbidden_part

      Emitted if URL contains a part present in
      :attr:`forbidden_parts`.

    """

    bad_format = N_(u'%(label)s is not a valid URL.')
    required_part = N_(u'%(label)s is not a valid URL.')
    forbidden_part = N_(u'%(label)s is not a valid URL.')

    all_parts = ('scheme', 'username', 'password', 'hostname', 'port',
                 'path', 'params', 'query', 'fragment')
    required_parts = dict(schema=('http', 'https'), hostname=True)
    forbidden_parts = dict(username=True, password=True)
    urlparse = urlparse

    def validate(self, element, state):
        url = element.value
        if url is None or not url.startswith('http'):
            return True
        parsed = self.urlparse.urlparse(url)

        for part in self.all_parts:
            try:
                value = getattr(parsed, part)
                if part == 'port':
                    value = None if value is None else str(value)
            except ValueError:
                return self.note_error(element, state, 'bad_format')
            required = self.required_parts.get(part)
            if required is True:
                if value is None:
                    return self.note_error(element, state, 'required_part')
            elif required:
                if value not in required:
                    return self.note_error(element, state, 'required_part')
            forbidden = self.forbidden_parts.get(part)
            if forbidden is True:
                if value:
                    return self.note_error(element, state, 'forbidden_part')
            elif forbidden:
                if value in forbidden:
                    return self.note_error(element, state, 'forbidden_part')
        return True


class URLCanonicalizer(Validator):
    """A URL canonicalizing validator.

    Given a valid URL, re-writes it with unwanted parts removed.  The
    default implementation drops the ``#fragment`` from the URL, if
    present.

    **Attributes**

    .. attribute:: discard_parts

      A sequence of 0 or more part names in :mod:`urlparse`'s
      vocabulary::

        'scheme', 'netloc', 'path', 'params', 'query', 'fragment'

    .. attribute:: urlparse

      By default the :mod:`urlparse` module, but may be replaced by
      any object that implements :func:`urlparse.urlparse` and
      :func:`urlparse.urlunparse`.

    **Messages**

    .. attribute:: bad_format

      Emitted for an unparseable URL.  This is impossible to hit with
      the Python's standard library implementation of urlparse.

    """

    bad_format = N_(u'%(label)s is not a valid URL.')

    discard_parts = 'fragment',
    urlparse = urlparse

    def validate(self, element, state):
        if not self.discard_parts:
            return True
        try:
            url = self.urlparse.urlparse(element.value)
        except Exception:
            return self.note_error(element, state, 'bad_format')

        url = list(url)
        for part in self.discard_parts:
            idx = _url_parts.index(part)
            current = url[idx]
            url[idx] = '' if current is not None else None

        element.value = self.urlparse.urlunparse(url)
        return True
