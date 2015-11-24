from irc import bot
import logging, importlib, time

class Bot(bot.SingleServerIRCBot):
	def __init__(self, conf):
		self.conf = conf

		# Construct mapping between channels and loadable modules
		self.tojoin_channels = list(filter(lambda x: x[0] == '#',
			conf.sections()))
		self.chan_modules = {}
		self.chan_mod_instances = {}
		self.modules = {}
		for c in self.tojoin_channels:
			# Try to load a module if it isn't already available
			mods = self.conf.get(c, 'modules').split(',')
			for m in mods:
				if m in self.modules:
					continue
				modpath = 'src.modules.%s' % m
				self.modules[m] = importlib.import_module(modpath)
				logging.info("Loaded module: %s", m)
			self.chan_modules[c] = list(
					map(lambda x: self.modules[x], mods))

		# Establish connection to IRC server
		srv = conf.get('Connection', 'server')
		port = int(conf.get('Connection', 'port'))
		user = conf.get('Connection', 'username')

		logging.info("Connecting to %s:%d user %s", srv, port, user)

		srv = bot.ServerSpec(srv, port,
				conf.get('Connection', 'oauth_password'))
		bot.SingleServerIRCBot.__init__(self, [srv], user, user)
	
	def on_endofmotd(self, conn, evt):
		logging.debug("Connected to server. MOTD ended.")

		for c in self.tojoin_channels:
			self.connection.join(c)

	def on_join(self, conn, evt):
		chan = evt.target
		logging.debug("Joined channel: %s", chan)

		# Initialize channel modules
		chanmods = self.chan_modules[evt.target]
		instances = {}
		for mod in chanmods:
			mname = mod.__name__.split('.')[-1]

			# Build config dict
			confdict = {}
			for k in self.conf.options(chan):
				prefix = mod.CONFIG_PREFIX
				if not k.startswith(prefix + '_'):
					continue
				val = self.conf.get(chan, k)
				confdict[k[len(prefix)+1:]] = val
			
			# Instantiate the module
			instances[mname] = mod.ModuleMain(conn, chan, confdict)
		self.chan_mod_instances[chan] = instances
		logging.info("Created all modules for channel: %s", chan)

		time.sleep(1)

		conn.privmsg(chan, 'Bot ready. Modules loaded: %s' % (' '.join(instances.keys())))
	
	def on_pubmsg(self, conn, evt):
		chan = evt.target
		src = evt.source[:evt.source.find('!')]
		content = evt.arguments[0]

		for inst in self.chan_mod_instances[chan].values():
			inst.on_message(src, content)
