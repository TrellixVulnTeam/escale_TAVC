# -*- coding: utf-8 -*-

# Copyright © 2017, François Laurent

# Copyright © 2017, Institut Pasteur
#   Contributor: François Laurent
#   Contribution: UnrecoverableError

# This file is part of the Escale software available at
# "https://github.com/francoislaurent/escale" and is distributed under
# the terms of the CeCILL-C license as circulated at the following URL
# "http://www.cecill.info/licenses.en.html".

# The fact that you are presently reading this means that you have had
# knowledge of the CeCILL-C license and that you accept its terms.


import logging, logging.handlers
from multiprocessing import Process, Queue
import threading

from .exceptions import *
from .essential import *
from .config import parse_cfg, get_cache_file
from escale.log import *
# separate imports instead of single escale.manager
# single import breaks Sphinx
from escale.manager.config import *
from escale.manager.manager import Manager
from escale.manager.access import AccessController, access_modifier_prefix
from escale.manager.history import History, usage_statistics_prefix
from escale.cli.controller import DirectController, UIController



def escale(config, repository, log_handler=None, ui_connector=None):
	"""
	Read the section related to a repository in a loaded configuration object and runs a 
	:class:`~escale.manager.Manager` for that repository.

	Arguments:

		config (ConfigParser): configuration object.

		repository (str): configuration section name or, alternatively, client name.

		log_handler (log handler): input argument to :meth:`~logging.Logger.addHandler`.

		ui_connector (?): connector to user-interface controller.
	"""
	# set logger
	logger = logging.getLogger(log_root).getChild(repository)
	logger.setLevel(logging.DEBUG)
	if log_handler is not None:
		logger.propagate = False
		logger.addHandler(log_handler)
	# ui
	if ui_connector is None:
		ui_controller = DirectController(logger=logger)
	else:
		ui_controller = UIController(*ui_connector)
		ui_controller.logger = logger
	# parse config
	relay, args = parse_section(config, repository, logger)
	# local repository
	path = args.pop('path', None)
	mode = args.pop('mode', None)
	lr_controller = AccessController(repository, path=path, mode=mode,
			persistent=get_cache_file(config, repository,
				prefix=access_modifier_prefix),
			ui_controller=ui_controller, **args)
	# time and quota control
	refresh = args.pop('refresh', True)
	quota = args.pop('quota', None)
	tq_controller = History(refresh=refresh, quota=quota, logger=logger,
			repository=repository,
			persistent=get_cache_file(config, repository,
				prefix=usage_statistics_prefix))
	# extra UI options
	ui_controller.maintainer = args.pop('maintainer', None)
	# ready
	manager = Manager(relay,
			repository=lr_controller,
			ui_controller=ui_controller,
			tq_controller=tq_controller,
			**args)
	try:
		result = manager.run()
	except ExpressInterrupt:
		raise
	except Exception as exc:
		if not ui_controller.failure(repository, exc):
			raise
	else:
		ui_controller.success(repository, result)



def escale_launcher(cfg_file, msgs=[], verbosity=logging.NOTSET, keep_alive=False):
	"""
	Parse a configuration file, set the logger and launch the clients in separate subprocesses.

	Arguments:

		cfg_file (str): path to a configuration file.

		msgs (list): list of pending messages (`str` or `tuple`).

		verbosity (bool or int): verbosity level.

		keep_alive (bool or int): if ``True`` or non-negative `int`, clients are ran again 
			after they hit an unrecoverable error; 
			multiple threads and subprocesses are started even if a single client is defined;
			if `int`, specifies default sleep time after a subprocess crashed.

	"""
	restart_delay = 0
	if isinstance(keep_alive, (int, float)):
		restart_delay = keep_alive
		keep_alive = True
	# parse the config file
	config, cfg_file, msgs = parse_cfg(cfg_file, msgs)
	# configure logger
	logger, msgs = set_logger(config, cfg_file, verbosity, msgs)
	# flush messages
	flush_init_messages(logger, msgs)
	# launch each client
	sections = config.sections()
	if sections[1:] or keep_alive: # if multiple sections
		if PYTHON_VERSION == 3:
			log_queue = Queue()
			log_listener = QueueListener(log_queue)
			log_handler = logging.handlers.QueueHandler(log_queue)
		elif PYTHON_VERSION == 2:
			import escale.log.socket as socket
			log_host = 'localhost'
			log_listener = socket.SocketListener(log_host)
			log_handler = logging.handlers.SocketHandler(log_host, log_listener.port)
		# logger
		logger_thread = threading.Thread(target=log_listener.listen)
		logger_thread.start()
		# result handling
		result_queue = Queue()
		# user interface
		ui_controller = UIController(logger=logger, parent=result_queue)
		ui_thread = threading.Thread(target=ui_controller.listen)
		ui_thread.start()
		# escale subprocesses
		workers = {}
		for section in config.sections():
			worker = Process(target=escale,
				name='{}.{}'.format(log_root, section),
				args=(config, section, log_handler, ui_controller.conn))
			workers[section] = worker
			worker.start()
		# wait for everyone to terminate
		try:
			if True:#keep_alive:
				active_workers = len(workers)
				while 0 < active_workers:
					section, result = result_queue.get()
					if isinstance(result, Exception) and \
							(keep_alive or isinstance(result, UnrecoverableError)):
						workers[section].join() # should have already returned
						# restart worker
						worker = Process(target=escale,
							name='{}.{}'.format(log_root, section),
							args=(config, section, log_handler,
								ui_controller.conn))
						workers[section] = worker
						ui_controller.restartWorker(section, restart_delay)
						worker.start()
					else:
						active_workers -= 1
			else:
				for worker in workers.values():
					worker.join()
		except ExpressInterrupt:
			for section, worker in workers.items():
				try:
					worker.terminate()
				except Exception as e:
					# 'NoneType' object has no attribute 'terminate'
					logger.warning("[%s]: %s", section, e)
					logger.debug("%s", workers)
			for worker in workers.values():
				try:
					worker.join(1)
				except:
					pass
		ui_controller.abort()
		log_listener.abort()
		ui_thread.join(1)
		logger_thread.join(1)
	else:
		escale(config, sections[0])


