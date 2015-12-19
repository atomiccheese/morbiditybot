class CommandModule:
        def __init__(self, name, bus, conn, chan, conf):
                self.name = name
                self.conf = conf
                self.chan = chan
                self.conn = conn
                self.bus = bus

        def send(self, msg):
                self.conn.privmsg(self.chan, msg)

        def error(self, msg):
                self.status('error: {}'.format(msg))

        def status(self, msg):
                self.send('[{}] {}'.format(self.name, msg))
        
        def on_message(self, src, content):
                content = content.strip()
                words = content.split(' ')
                if len(words) == 0:
                        return

                cmd = words[0]
                if cmd[0] != '!':
                        return
                cmd = words[0][1:]

                if hasattr(self, 'cmd_'+cmd):
                        getattr(self, 'cmd_'+cmd)(src, words[1:],
                                        content[len(words[0]):].strip(), src)
        
        def post(self, msg, *args, **kwargs):
                self.bus.post(self, msg, args, kwargs)

        def bus_handle(self, msg, args, kwargs):
                mname = 'busmsg_' + msg
                if hasattr(self, mname):
                        getattr(self, mname)(*args, **kwargs)
