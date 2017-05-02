# -*- coding: utf-8 -*-

# Copyright (c) 2017, François Laurent

# Copyright (c) 2017, Institut Pasteur
#   Contributor: François Laurent
#   Contributions:
#     * `ssl version`, `version ssl`, `file extension` in `fields`
#     * `_item_separator`, `getlist`
#     * `list = getlist` line in `getter`

from .essential import *
import os
try:
	from configparser import ConfigParser, NoOptionError # Py3
except ImportError:
	import ConfigParser as cp
	ConfigParser = cp.SafeConfigParser
	NoOptionError = cp.NoOptionError
import re # moved from syncacre.cli.config together with parse_address


# configparser
default_section = 'DEFAULT' # Python2 cannot modify it

default_filename = SYNCACRE_NAME + '.conf'
global_cfg_dir = '/etc'
default_cfg_dirs = [os.path.join(os.path.expanduser('~/.config'), SYNCACRE_NAME),
	os.path.expanduser('~/.' + SYNCACRE_NAME),
	global_cfg_dir]
default_conf_files = [ os.path.join(d, default_filename) for d in default_cfg_dirs ]


# fields expected in configuration files
# 'directory': 'host path', 'relay path', 'remote path' added in version 0.4a3
# 'password': 'secrets file' and 'credentials' removed in version 0.4a3
# 'refresh': can be bool in version 0.4a3
# 'maintainer' added in version 0.4.1a1
fields = dict(path=('path', ['local path', 'path']),
	address=['host address', 'relay address', 'remote address', 'address'],
	directory=['host directory', 'relay directory', 'remote directory',
		'directory', 'relay dir', 'remote dir', 'host dir', 'dir',
		'host path', 'relay path', 'remote path'],
	port=['port', 'host port', 'relay port', 'remote port'],
	username=['user', 'auth user', 'host user', 'relay user', 'remote user'],
	password=(('path', 'str'),
		['password', 'secret', 'secret file', 'credential']),
	refresh=(('bool', 'float'), ['refresh']),
	timestamp=(('bool', 'str'), ['modification time', 'timestamp', 'mtime']),
	clientname=['client name', 'client'],
	encryption=(('bool', 'str'), ['encryption']),
	passphrase=(('path', 'str'), ['passphrase', 'key']),
	push_only=('bool', ['push only', 'read only']),
	pull_only=('bool', ['pull only', 'write only']),
	ssl_version=['ssl version'],
	verify_ssl=('bool', ['verify ssl']),
	filetype=('list', ['file extension', 'file type']),
	maintainer=['maintainer', 'email'])


def getpath(config, section, attr):
	path = config.get(section, attr)
	if path[0] == '~':
		path = os.path.expanduser(path)
	if os.path.isdir(os.path.dirname(path)):
		return path
	else:
		raise ValueError


_item_separator = ','

def getlist(config, section, attr):
	_list = [ i.strip() for i in config.get(section, attr).split(_item_separator) ]
	return [ i for i in _list if i ]



def getter(_type='str'):
	"""
	Config getter.

	Arguments:

		_type (str): either ``bool``, ``int``, ``float``, ``str``, ``path`` or ``list``.

	Returns:

		function: getter(config (ConfigParser), section (str), field (str))

	"""
	return dict(
			bool =	ConfigParser.getboolean,
			int =	ConfigParser.getint,
			float =	ConfigParser.getfloat,
			str =	ConfigParser.get,
			path =	getpath,
			list =	getlist
		)[_type]


def parse_field(config, section, attrs, getters, logger=None):
	for attr in attrs:
		option = True
		for get in getters:
			try:
				return get(config, section, attr)
			except NoOptionError:
				option = False
				break
			except ValueError:
				pass
		if option:
			if logger is None:
				print("warning: wrong format for attribute '{}'".format(attr))
			else:
				logger.warning("wrong format for attribute '%s'", attr)
	return None


def parse_fields(config, section, fields, logger=None):
	args = {}
	for field, attrs in fields.items():
		if isinstance(attrs, tuple):
			types, attrs = attrs
			if isinstance(types, str):
				types = (types,)
			getters = [ getter(t) for t in types ]
		else:
			getters = [ getter() ]
		value = parse_field(config, section, attrs, getters, logger)
		if value is not None:
			args[field] = value
	return args


def parse_cfg(cfg_file='', msgs=[], new=False):
	'''
	Parse a configuration file.

	Arguments:

		cfg_file (str): path to a configuration file.

		msgs (list): list of pending messages.

		new (bool): if ``True`` and `cfg_file` does not exist, create the file.

	Returns:

		(ConfigParser, str, list):
		first argument is the parsed configuration,
		second argument is the corresponding file path,
		third argument is the list of pending messages.

	'''
	if cfg_file:
		err_msg_if_missing = 'file not found: {}'.format(cfg_file)
	else:
		err_msg_if_missing = 'cannot find a valid configuration file'
		candidates = default_conf_files + [None]
		for cfg_file in candidates:
			if cfg_file and os.path.isfile(cfg_file):
				break
		if not cfg_file:
			try: # check if superuser
				cfg_file = default_conf_files[-1] # global conf file
				with open(cfg_file, 'a'):
					pass
			except IOError: # [Errno13] Permission denied: 
				cfg_file = default_conf_files[0]
	if not os.path.isfile(cfg_file):
		if new:
			import logging
			msgs.append((logging.INFO, "creating new configuration file '%s'", cfg_file))
			cfg_dir = os.path.dirname(cfg_file)
			if not os.path.isdir(cfg_dir):
				os.makedirs(cfg_dir)
			with open(cfg_file, 'w'):
				pass # touch
		else:
			raise IOError(err_msg_if_missing)
	with open(cfg_file, 'r') as f:
		while True:
			line = f.readline()
			if f.tell() == 0: # file is empty
				break
			stripped = line.strip()
			if stripped and any([ stripped[0] == s for s in '#;' ]):
				stripped = ''
			if stripped:
				break
		if not line.startswith('[{}]'.format(default_section)):
			line = "[{}]\n{}".format(default_section, line)
		raw_cfg = "{}{}".format(line, f.read())
	if PYTHON_VERSION == 3:
		config = ConfigParser(default_section=default_section)
		config.read_string(raw_cfg, source=cfg_file)
	elif PYTHON_VERSION == 2:
		assert default_section == 'DEFAULT'
		assert isinstance(raw_cfg, str)
		config = ConfigParser()
		import io
		try:
			config.readfp(io.BytesIO(raw_cfg), filename=cfg_file)
		except UnicodeDecodeError:
			raw_cfg = "\n".join([ line.decode('utf-8').encode('unicode-escape')
					for line in raw_cfg.splitlines() ])
			config.readfp(io.BytesIO(raw_cfg), filename=cfg_file)
			config = crawl_config(lambda a: a.decode('unicode-escape'), config)
	return (config, cfg_file, msgs)


def parse_address(addr):
	# moved from syncacre.cli.config in version 0.4a3
	try:
		protocol, addr = re.split('://', addr)
	except ValueError:
		protocol = None
	try:
		addr, path = addr.split('/', 1)
	except ValueError:
		path = None
	try:
		addr, port = addr.split(':')
	except ValueError:
		port = None
	return (protocol, addr, port, path)


def crawl_config(fun, config=None):
	def crawl(__config__):
		__defaults__ = __config__.defaults()
		for __option__, __value__ in __defaults__.items():
			__config__.set(default_section, __option__, fun(__value__))
		for __section__ in __config__.sections():
			for __option__, __value__ in __config__.items(__section__):
				__config__.set(__section__, __option__, fun(__value__))
		return __config__
	if config:
		return crawl(config)
	else:
		return crawl

