from blinker import signal


validator_validated = signal('validator_validated', doc="""\
Emitted after a validator has processed an element.

:param sender: the validator

:param element: the element being validated

:param state: the *state* passed to
  :meth:`~flatland.schema.base.Element.validate`

:param result: the result of validator execution

""")
