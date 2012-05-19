import os
import webapp2
import jinja2
import urllib2
import json

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
			       autoescape = True)

class Tweet():
	def __init__(self, created_at,from_user_name,profile_img,text,user):
		self.created_at = created_at
		self.from_user_name = from_user_name	
		self.profile_img = profile_img
		self.text = text
		self.profile_link = 'https://twitter.com/#!/%s' % user

class Handler(webapp2.RequestHandler):
	def write(self, *a, **kw):
	    self.response.out.write(*a, **kw)

	def render_str(self, template, **params):
	    t = jinja_env.get_template(template)
	    return t.render(params)

	def render(self, template, **kw):
	    self.write(self.render_str(template,**kw))

	def retrieve_newers(self, filtro = ''):
	    try:		
		url = 'http://search.twitter.com/search.json?q=%23vetatudodilma'
		if filtro:
			url = 'http://search.twitter.com/search.json?q=%40twitterapi%20%40anywhere'
		p = urllib2.urlopen(url)
	    	c = p.read()
	    	j = json.loads(c)
	    	tweets = []
	    	for c in j['results']:
			created_at = c['created_at']
			from_user_name = c['from_user_name']
			profile_img = c['profile_image_url']
			text = c['text']
			user = c['from_user']
			tweet = Tweet(created_at,from_user_name,profile_img,text,user)
			tweets.append(tweet)
	    except:
	 	tweets = []
	    return tweets

class MainPage(Handler):
	def write_form(self, newers):
	    self.render("front_template.html", tweets = newers)

	def get(self):
	    tweets = self.retrieve_newers()
	    self.write_form(tweets)

	def post(self):
	    filtro = self.request.get('filtro')
	    tweets = self.retrieve_newers(filtro)
	    self.write_form(tweets)

app = webapp2.WSGIApplication([('/', MainPage)], debug = True)
