import requests, os, os.path

CONFIG_PREFIX = "death"
TWITCH_API = 'https://api.twitch.tv/kraken/'

def print_num(n):
	places = ['thousand', 'million', 'billion', 'trillion', 'quadrillion']
	if n < 100:
		digits = ['one','two','three','four','five','six','seven',
				'eight','nine','ten','eleven','twelve',
				'thirteen','fourteen','fifteen','sixteen',
				'seventeen','eighteen','nineteen']
		tens = ['twenty','thirty','forty','fifty','sixty','seventy',
				'eighty','ninety']
		if n < len(digits):
			return digits[n-1]
		else:
			tens = tens[(n // 10)-2]
			if n % 10 == 0:
				return tens
			ones = digits[n % 10 - 1]
			return tens + ' ' + ones
	elif n < 1000:
		hundreds = print_num(n // 100)
		ones = print_num(n % 100)
		return hundreds + ' hundred ' + ones
	else:
		parts = []
		idx = 0
		while(n > 0):
			if(idx > 0):
				parts.append(places[idx-1])
			parts.append(print_num(n % 1000))
			n //= 1000
			idx += 1
		return ' '.join(parts[::-1])

class ModuleMain:
	def __init__(self, conn, channel, conf):
		self.conf = conf
		self.conn = conn
		self.chan = channel
		self.admins = self.conf['admins'].split(',')

		self.deaths = 0
		self.enabled = False
		self.last_game = None

		# Find the game being played
		try:
			game = self.get_game()
			self.load_deaths(game)
		except IOError:
			self.error('Unable to determine game. Death counter disabled.')
			self.enabled = False
	
	def send(self, msg):
		self.conn.privmsg(self.chan, msg)
	
	def error(self, msg):
		self.status('error: %s' % msg)
	
	def status(self, msg):
		self.send('[deathcounter] %s' % msg)
	
	def get_game(self):
		hdrs = {'accept': 'application/vnd.twitchtv.v3+json'}
		url = TWITCH_API+'channels/'+self.chan[1:]
		r = requests.get(url, headers=hdrs)
		r.raise_for_status()
		return r.json()['game']
	
	def update_game(self):
		try:
			g = self.get_game()
		except IOError:
			self.error('Unable to determine game. Death counter disabled.')
			self.enabled = False
			return False

		if g != self.last_game:
			self.load_deaths(g)
		return True
	
	def load_deaths(self, game):
		self.last_game = game

		# Create user directory if it doesn't already exist
		pth_game = game.replace('/', '\xff')
		pth_chan = 'deaths_' + self.chan[1:]
		if not os.path.exists(pth_chan):
			os.mkdir(pth_chan)
		pth = os.path.join(pth_chan, pth_game)
		self.enabled = True

		# Open the data file
		try:
			with open(pth, 'r') as f:
				self.deaths = int(f.read())
		except IOError as e:
			pass
		except ValueError as e:
			pass
		self.status('Death count for %s: %d' % (game, self.deaths))
	
	def save_deaths(self):
		pth_game = self.last_game.replace('/', '\xff')
		pth_chan = 'deaths_' + self.chan[1:]
		pth = os.path.join(pth_chan, pth_game)
		with open(pth, 'w') as f:
			f.write(str(self.deaths))
	
	def count_death(self):
		self.deaths += 1
		self.save_deaths()
		return self.deaths
	
	def on_message(self, src, content):
		content = content.strip()
		words = content.split(' ')
		if len(words) == 0:
			return
		cmd = words[0]
		if cmd[0] != '!':
			return
		cmd = words[0][1:]
		
		if(hasattr(self, 'cmd_'+cmd)):
			getattr(self, 'cmd_'+cmd)(src,
					words[1:],
					content[len(words[0]):].strip(),
					src)
	
	def cmd_death(self, src, args, content, user):
		if(len(args) == 0):
			self.send("Error: !death requires arguments")
			return
		if src not in self.admins:
			self.send("Error: !death requires module admin access")
			return
		if(args[0] == 'set' and len(args) == 2):
			try:
				self.deaths = int(args[1])
			except ValueError as e:
				self.send("Error: '%s' is not a valid number" % args[2])
				return
			self.save_deaths()
			self.send("Number of deaths set to %d" % self.deaths)
		elif args[0] == 'reload':
			self.load_deaths(self.get_game())
		elif args[0] == 'save':
			self.save_deaths()
		else:
			self.send("Error: Unknown subcommand '%s'" % args[0])
			return

	def cmd_rip(self, src, args, content, user):
		if not self.update_game():
			return
		if not self.enabled:
			self.error('Death counter is currently disabled')

		n = self.count_death()
		if self.conf['spaced_text'].lower() == 'true':
			disp = print_num(n).upper().replace(' ','')
			final = ' '.join(disp + 'BOYS')
		else:
			final = str(self.deaths)
		self.send(final)

	def cmd_deaths(self, src, args, content, user):
		if not self.update_game():
			return
		if not self.enabled:
			self.error('Death counter is currently disabled')

		self.send("%s has died %d times" % (self.chan, self.deaths)) 
