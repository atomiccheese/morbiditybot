import subprocess, requests, threading, re, logging, time

from .. import modules

CONFIG_PREFIX = "overwatch"
TWITCH_API = 'https://api.twitch.tv/kraken/'
CMD_TEMPLATE = ['livestreamer', '-nv', '--player-passthrough', 'rtmp',\
                '--player', '{exec}', '{stream}', 'best']
NOTIFY_TAG = "[sentinel] "
FPS_LINE_RE = re.compile('run fps=([0-9.]+)')
VARIANCE_THRESHOLD = 2
VAS_PREFIX = "Video analysis subsystem "

# Reader process to translate subprocess events into msgbus calls
def subproc_reader(proc, mbus):
        fpsen = []
        while True:
                line = proc.stdout.readline()
                if line == '':
                        break
                line = line.strip()
                if not line.startswith(NOTIFY_TAG):
                        continue
                line = line[len(NOTIFY_TAG):]
                if line == 'system starting':
                        mbus.post(None, 'monitor_starting', [], {})
                        continue
                m = FPS_LINE_RE.match(line)
                if m:
                        if fpsen is None:
                                continue
                        fpsen.append(float(m.group(1)))
                        fpsen = fpsen[-30:]
                        if len(fpsen) < 30:
                                continue
                        mean = sum(fpsen)/len(fpsen)
                        variance = sum(map(lambda x: (x-mean)**2, fpsen))/len(fpsen)
                        mbus.post(None, 'monitor_stable', (mean, variance), {})
                        fpsen = None
                        continue
                if line == 'died':
                        time.sleep(1.5)
                        mbus.post(None, 'died', [], {})
                        continue
                logging.warning("Unknown procline: '%s'" % line)
        mbus.post(None, 'monitor_ending', [], {})

class ModuleMain(modules.CommandModule):
        def __init__(self, bus, conn, chan, conf):
                modules.CommandModule.__init__(self, 'overwatch', bus, conn, chan, conf)

                self.process = None
                self.monitor = None

                self.exec_cwd = self.conf['cwd']
                self.admins = self.conf['admins'].split(' ')
                self.executable = self.conf['command']
                self.game = self.conf['game']

        def get_game(self):
                hdrs = {'accept': 'application/vnd.twitchtv.v3+json'}
                url = TWITCH_API+'channels/'+self.chan[1:]
                r = requests.get(url, headers=hdrs)
                r.raise_for_status()
                return r.json()['game']

        def should_enable(self):
                g = self.get_game()
                logging.debug("Checking game: '{}' vs '{}'".format(g, self.game))
                return g.lower() == self.game.lower()

        def cmd_vproc(self, src, args, content, user):
                if user not in self.admins:
                        self.error("Command access denied")
                cmd = args[0]
                args = args[1:]
                if cmd == 'start':
                        self.proc_begin('http://twitch.tv/{}'.format(self.chan[1:]))
                elif cmd == 'stop':
                        self.proc_terminate()
                elif cmd == 'status':
                        if self.process:
                                self.status('Video processing is online')
                        else:
                                self.status('Video processing is offline')
                else:
                        self.error("Unknown system command")

        def cmd_bigbro(self, src, args, content, user):
                should = self.should_enable()
                if self.process and not should:
                        self.proc_terminate()
                elif not self.process and should:
                        self.proc_begin('http://twitch.tv/{}'.format(self.chan[1:]))

        def cmd_dbgbro(self, src, args, content, user):
                self.proc_begin('http://www.twitch.tv/outstarwalker/v/30459989')

        def busmsg_monitor_starting(self):
                self.status(VAS_PREFIX+"initializing")

        def busmsg_monitor_stable(self, fps, fpsvar):
                TPL = "stable at {:.2f} FPS (variance {:.2f})"
                self.status(VAS_PREFIX + TPL.format(fps, fpsvar))

        def busmsg_monitor_ending(self):
                self.status(VAS_PREFIX+"shut down")

        def proc_terminate(self):
                if not self.process:
                        return
                self.process.terminate()
                self.process.wait()
                self.process = None
                self.monitor.join()

        def proc_begin(self, strm):
                if self.process:
                        return

                # Generate argument list
                kwdict = {}
                kwdict['exec'] = self.executable
                kwdict['stream'] = strm

                args = list(map(lambda x: x.format(**kwdict), CMD_TEMPLATE))
                self.process = subprocess.Popen(args, cwd=self.exec_cwd,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True)
                self.monitor = threading.Thread(target=subproc_reader,
                                args=(self.process,self.bus))
                self.monitor.start()
