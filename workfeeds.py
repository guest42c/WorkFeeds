import os
import webapp2
import jinja2
import urllib2
import json
import urlparse
import re
import logging
import time

from google.appengine.api import memcache
from google.appengine.ext import db

from unicodedata import normalize

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
			       autoescape = True)

logger = logging.getLogger('tweetvagas_application')
logger.setLevel(logging.DEBUG)

DEFAULT_MAX_TWEETS = 20
TWEET_INC = 10

class Tweet():
	def __init__(self, created_at,from_user_name,profile_img,text,user,id_str, from_user):
		self.created_at = created_at
		self.from_user_name = from_user_name	
		self.profile_img = profile_img
		self.text = text
		self.id_str = id_str
		self.from_user = from_user
		self.profile_link = 'https://twitter.com/#!/%s' % user

class Vaga(db.Model):
	description = db.TextProperty(required = True)
	created = db.DateTimeProperty(auto_now_add = True)
	
	@classmethod
	def by_id(cls, bid):
		return cls.get_by_id(bid)

	def as_dict(self):
		time_fmt = '%c'
		d = {
			'description': self.description,
			'created': self.created.strftime(time_fmt)
		}
		return d

def find_urls(atext):
    url_list = re.findall('(http://[^"\' ]+|https://[^"\' ]+)',atext)
    return url_list

def get_vaga(vaga_id, update = False):
	key = vaga_id
	vaga = memcache.get(key)
	if vaga is None or update:
		vaga = Vaga.by_id(int(vaga_id))
		memcache.set(key,vaga)
	return vaga

def user_link(user_l):
	u = user_l.string[user_l.start(0):user_l.end(0)]
	return ('<a href="https://twitter.com/#!/%s" target="_blank">%s </a>' % (u[1:],u))

def datetimeformat(value, format='%d-%m-%Y (%H:%Mh)'):
    return value.strftime(format)

jinja_env.filters['datetimeformat'] = datetimeformat

def twitterdtformat(value):
	return time.strftime('%d-%m-%Y (%H:%Mh)',time.strptime(value, '%a, %d %b %Y %H:%M:%S +0000'))

jinja_env.filters['twitterdtformat'] = twitterdtformat

def remover_acentos(txt, codif='utf-8'):
	logger.info("removendo acentos")
	return normalize('NFKD', txt.decode(codif)).encode('ASCII','ignore')

class Handler(webapp2.RequestHandler):
	def __init__(self, request, response):
		self.initialize(request, response)
		self.max_tweets = self.get_max_tweets()

	def write(self, *a, **kw):
	    self.response.out.write(*a, **kw)

	def render_str(self, template, **params):
	    t = jinja_env.get_template(template)
	    return t.render(params)

	def render(self, template, **kw):
	    self.write(self.render_str(template,**kw))

	def retrieve_newers(self, t_query = None):
		try:		
			url = u'http://search.twitter.com/search.json?q=@tweetvagas'
			if t_query:
				for item in t_query:
					url = url + u"%20" + item
					logger.info(item)					
			result_size = u'&rpp=1000'
			url = url + result_size
			logger.info(url)
			p = urllib2.urlopen(url)
			c = p.read()
			j = json.loads(c)
			logger.info("JSON: %s" % j)
			tweets = []
			i = 0
			# logger.info("Numero de resultados no JSON: %s" % len(j['results']))
			for c in j['results']:
				created_at = c['created_at']
				from_user_name = c['from_user_name']
				from_user = c['from_user']
				profile_img = c['profile_image_url']
				text = c['text']
				id_str = c['id_str']
				urls = find_urls(text)
				for u in urls:
					text = text.replace(u,'<a href="%s" target="_blank">%s</a> ' % (u,u))
				text = re.sub(r' @([A-Za-z0-9_]+)',user_link,text)
				user = c['from_user']
				tweet = Tweet(created_at,from_user_name,profile_img,text,user,id_str,from_user)
				tweets.append(tweet)
				i = i + 1
				if i >= self.max_tweets:
					break
		except:
			tweets = []
		logger.info("Numero maximo de tweets: %s" % self.max_tweets)
		logger.info("Tweets exibidos: %s" % len(tweets))
		return tweets

	def more_tweets(self):
		self.max_tweets = int(self.request.cookies.get("max_tweets")) + TWEET_INC		
		self.response.headers.add_header('Set-Cookie','max_tweets=%s; Path=/' % self.max_tweets)

	def get_max_tweets(self):
		maxtweets = self.request.cookies.get("max_tweets")
		if maxtweets:
			max_tweets = int(maxtweets)
		else:
			max_tweets = DEFAULT_MAX_TWEETS
		self.response.headers.add_header('Set-Cookie','max_tweets=%s; Path=/' % max_tweets)
		return max_tweets

class MainPage(Handler):
	def write_form(self, newers, filtro = '', error_msg = ''):
		self.render("front_template.html", tweets = newers, filtro = filtro, error_msg = error_msg)

	def get(self):
		self.get_max_tweets()
		filtro = self.request.get('filtro')
		logger.info("Filtro entrada: %s" % filtro)
		filtro = remover_acentos(filtro.encode('utf-8'))
		logger.info("Filtro resultado: %s" % filtro)
		tweets = []
		if filtro:
			tweets = self.retrieve_newers(filtro.split(" "))
		else:
			tweets = self.retrieve_newers()
		error_msg = ''
		if not tweets:
			error_msg = u'Sua busca nao retornou resultados.' 
		self.write_form(tweets,filtro,error_msg)

	def post(self):
		if 'carregar_mais' in self.request.POST:
			self.more_tweets()
		if 'anunciar' in self.request.POST:
			texto = self.request.get('anuncio')
			if texto:
				v = Vaga(description = texto)
				v.put()				
				id_vaga = v.key().id()
				link = ('http://tweetvagas.appspot.com/vaga/%s' % id_vaga)
				desc_len = len(v.description)
				if desc_len > 90:
					tweet_text = v.description[0:89]
				else:
					tweet_text = v.description[0:(desc_len-1)]
				url = ('https://twitter.com/intent/tweet?text=%(tweet)s %(link)s @tweetvagas' %
					{'tweet':tweet_text.replace('\n',' '),'link':link})
				logger.info("Tweet url: %s" % url)
				self.response.out.write('<html><head><meta http-equiv="refresh" content="0;url=%s"></head><body></body></html>' % (url))

		filtro = self.request.get('filtro')
		logger.info("Filtro entrada: %s" % filtro)
		filtro = remover_acentos(filtro.encode('utf-8'))
		logger.info("Filtro resultado: %s" % filtro)
		tweets = []
		if filtro:
			tweets = self.retrieve_newers(filtro.split(" "))
		else:
			tweets = self.retrieve_newers()
		error_msg = ''
		if not tweets:
			error_msg = "Sua busca nao retornou resultados." 
		self.write_form(tweets,filtro,error_msg)

class VagaHandler(Handler):
	def write_form(self, vaga):
		self.render("vaga_template.html", vaga = vaga)

	def get(self, vaga_id):
		vaga = get_vaga(vaga_id)
		self.write_form(vaga)

app = webapp2.WSGIApplication([('/', MainPage),
							   ('/vaga/([0-9]+)',VagaHandler)
							   ], debug = True)
