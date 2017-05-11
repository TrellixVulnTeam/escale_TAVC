# -*- coding: utf-8 -*-

# Copyright (c) 2017, François Laurent

import os
import sys

SYNCACRE_NAME = 'syncacre'

PYTHON_VERSION = sys.version_info[0]


# this symbols are deprecated since the introduction of `asstr`
if PYTHON_VERSION == 2:
	binary_type = str
	text_type = unicode
elif PYTHON_VERSION == 3:
	binary_type = bytes
	text_type = str


def asstr(s):
	'''
	Coerce string to ``str`` type.

	In Python 2, `s` can be of type ``str`` or ``unicode``.
	In Python 3, `s` can be of type ``bytes`` or ``str``.

	Arguments:

		s (str-like): string.

	Returns:

		str: regular string.

	'''
	if PYTHON_VERSION == 2 and isinstance(s, unicode):
		s = s.encode('utf-8')
	elif PYTHON_VERSION == 3 and isinstance(s, bytes):
		s = s.decode('utf-8')
	return s



def join(dirname, *extranames):
	'''
	Combine path elements similarly to :func:`os.path.join`.
	
	Arguments are properly coerced and the extra path elements are
	considered relative even if they begin with a file separator.

	Only slashes (``/``) are considered as valid file separators.

	Arguments:

		dirname (str-like): directory name.

		extraname (str-like): subdirectory or file name.

	Returns:

		str: full path.
	'''
	extranames = [ s[1:] if s and s[0] in '/' else s for s in extranames ]
	return os.path.join(asstr(dirname), *[ asstr(s) for s in extranames ])



class Reporter(object):
	"""
	Base class for log- and user-interface- enabled classes.

	In a feature release, `logger` may become a property.

	Attributes:

		logger (Logger or LoggerAdapter): logger.

		ui_controller (DirectController or UIController): user-interface controller.

	"""

	__slots__ = [ 'logger', 'ui_controller' ]

	def __init__(self, logger=None, ui_controller=None, **ignored):
		self.logger = logger
		if ui_controller is None:
			import syncacre.cli.controller as ui
			ui_controller = ui.DirectController(logger=logger)
		elif self.logger is None:
			self.logger = ui_controller.logger
		self.ui_controller = ui_controller

