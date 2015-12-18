from irc import bot
import logging, importlib, time
import random, traceback, os, os.path

ERR_MSG = 'An error occurred in "%s" and it has been disabled. The MAGIC WORD is "%s".'

class Bot(bot.SingleServerIRCBot):
        def __init__(self, conf):
                self.conf = conf

                # Construct mapping between channels and loadable modules
                self.tojoin_channels = list(filter(lambda x: x[0] == '#',
                        conf.sections()))
                self.chan_modules = {} # Maps channel to list of module objects
                self.chan_mod_instances = {} # Maps channel to {modname->instance}
                self.modules = {} # Maps modname to module objects

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

                self.admins = conf.get('Connection', 'sys_admins').strip().split(',')

                logging.info("Connecting to %s:%d user %s", srv, port, user)

                srv = bot.ServerSpec(srv, port,
                                conf.get('Connection', 'oauth_password'))
                bot.SingleServerIRCBot.__init__(self, [srv], user, user)

        def load_module(self, mod, chan):
            # Load the module if needed
            if mod not in self.modules:
                # Load the module if necessary
                pth = 'src.modules.%s' % mod
                self.modules[mod] = importlib.import_module(pth)
                logging.info("Loaded module: %s" % mod)

            # Plug the module into this channel
            modname = mod
            mod = self.modules[mod]
            if mod not in self.chan_mod_instances[chan]:
                # Instantiate the module
                conf = self.get_module_conf(chan, mod)
                inst = mod.ModuleMain(self.connection, chan, conf)
                self.chan_modules[chan].append(mod)
                self.chan_mod_instances[chan][modname] = inst
                time.sleep(2)
                self.connection.privmsg(chan, "Module loaded: %s" % modname)

        def unload_module(self, mod, chan):
            if mod not in self.modules:
                return
            mname = mod
            mod = self.modules[mod]
            if chan != None:
                # Only unload from this channel
                self.chan_modules[chan].remove(mod)
                del self.chan_mod_instances[chan][mname]
                self.connection.privmsg(chan, "Module unloaded: %s" % mname)
            else:
                users = list(filter(lambda x: mod in self.chan_modules[x],
                    self.tojoin_channels))
                for u in users:
                    self.chan_modules[u].remove(mod)
                    del self.chan_mod_instances[u][mname]
                    self.connection.privmsg(u, "Module unloaded: %s" % mname)

        def reload_module(self, mod):
            users = list(filter(lambda x: mod in self.chan_modules[c],
                self.tojoin_channels))

        def get_module_conf(self, chan, mod):
                confdict = {}
                for k in self.conf.options(chan):
                        prefix = mod.CONFIG_PREFIX
                        if not k.startswith(prefix + '_'):
                                continue
                        val = self.conf.get(chan, k)
                        confdict[k[len(prefix)+1:]] = val
                return confdict

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
                        confdict = self.get_module_conf(chan, mod)

                        # Instantiate the module
                        instances[mname] = mod.ModuleMain(conn, chan, confdict)
                        time.sleep(2)
                self.chan_mod_instances[chan] = instances
                logging.info("Created all modules for channel: %s", chan)

                conn.privmsg(chan, 'Bot ready. Modules loaded: %s' % (' '.join(instances.keys())))

        def dump_exception(self):
                if not os.path.exists('crash_logs'):
                        os.mkdir('crash_logs')
                name = ''.join([random.choice('abcdefghijklmnopqrstuvwxyz') for x in range(16)])
                with open(os.path.join('crash_logs', name), 'w') as f:
                        f.write(traceback.format_exc())
                return name
        
        def on_pubmsg(self, conn, evt):
                chan = evt.target
                src = evt.source[:evt.source.find('!')]
                content = evt.arguments[0]

                if(content.startswith("!mbt")):
                    self.process_metacommand(chan, src, content)
                    return

                cmi = self.chan_mod_instances[chan]
                for iname in cmi.keys():
                        inst = cmi[iname]
                        try:
                                inst.on_message(src, content)
                        except Exception as e:
                                magic = self.dump_exception()
                                conn.privmsg(chan, ERR_MSG % (iname, magic))

        def process_metacommand(self, chan, src, content):
            if src not in self.admins:
                conn.privmsg(chan, '[metacmd] You do not have system-level access')
                return
            parts = content.split(' ')[1:]
            if len(parts) == 0:
                conn.privmsg(chan, '[metacmd] No operation specified')
                return
            cmd = parts[0]
            if cmd == 'unload':
                if len(parts) < 2:
                    conn.privmsg(chan, '[metacmd] Must specify module')
                    return
                opts = parts[2:]
                for i in opts:
                    if i not in ['force']:
                        conn.privmsg(chan, '[metacmd] Unknown option: %s' % i)

                if 'force' in opts:
                    self.unload_module(parts[1], None)
                else:
                    self.unload_module(parts[1], chan)
            if cmd == 'reload':
                if len(parts) != 2:
                    conn.privmsg(chan, '[metacmd] Must specify module')
                    return
                self.unload_module(parts[1], chan)
                self.load_module(parts[1], chan)
            if cmd == 'load':
                if len(parts) != 2:
                    conn.privmsg(chan, '[metacmd] Must specify module')
                    return
                self.load_module(parts[1], chan)
