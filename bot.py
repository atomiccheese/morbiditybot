#!/usr/bin/python3
import src.bot
import configparser

# Read config file
conf = configparser.ConfigParser()
conf.read('config.cfg')

bot = src.bot.Bot(conf)
bot.run()
