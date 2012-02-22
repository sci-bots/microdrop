import __builtin__
import itertools


def element_ancestry(element):
    """Iterates element plus element.parents."""
    return itertools.chain((element,), element.parents)


def search_ancestry(element, predicate):
    """Run *predicate* against element's ancestry.

    :param element: an :class:`~flatland.schema.base.Element`

    :param predicate: a callable function. Will be passed one
      argument, an element.

    Returns the first non-false value emitted by *predicate*.
    AttributeError raised by *predicate* are treated as equivalent to
    a pass.  Any other exception is raised to the caller.

    """
    for obj in element_ancestry(element):
        try:
            transform = predicate(obj)
            if transform:
                return transform
        except AttributeError:
            pass


def find_i18n_function(element, finder):
    """Find i18n form helpers such as ``ugettext``.

    :param element: an :class:`~flatland.schema.base.Element`

    :param finder: a callable function. Will be passed one argument,
      an element.  AttributeError is ignored, allowing
      ``operator.attrgetter('ugettext')`` to be used directly.

    Searches the ancestry of *element* and it's schema with *finder*
    ala :func:`search_ancestry`, falling back to a search against
    ``__builtin__``.

    """
    transformer = search_ancestry(element, finder)
    if transformer:
        return transformer
    try:
        return finder(__builtin__)
    except AttributeError:
        return None
