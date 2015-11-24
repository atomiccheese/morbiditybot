#!/usr/bin/python3
import src.bot
import configparser
import logging

# Read config file
conf = configparser.ConfigParser()
conf.read('config.cfg')

if(conf['Connection'].get('debug').lower() == 'true'):
	logging.getLogger().setLevel(logging.DEBUG)
else:
	logging.getLogger().setLevel(logging.INFO)

bot = src.bot.Bot(conf)
bot.start()
