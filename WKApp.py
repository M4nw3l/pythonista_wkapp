''' 
WKApp - A modern HTML5 UI framework for building iOS apps with Pythonista 3 and WebKit

https://github.com/M4nw3l/pythonista-wkapp
'''
#pthonista specific
import ui

import os
import sys
import threading
from urllib.parse import urlparse

import bottle
from bottle import Bottle, default_app, BaseTemplate
from bottle import WSGIRefServer
from bottle import (
	request,
	route,
	static_file,
	mako_template as template,
	mako_view as view,
)

from mako.lookup import TemplateLookup

import logging
log = logging.getLogger(__name__)

try:
	from .WKWebView import *
except:
	from WKWebView import *

class WKAppWebView(WKWebView):
	def webview_did_start_load(self, url):
		log.warning(f'WKAppWebView - Start loading {url}')

	def webview_did_finish_load(self, url):
		log.warning(f'WKAppWebView - Finish loading {url}')
	
class WKAppView(ui.View):
		
	@property
	def webview(self):
		return self['webview']
		
	def did_load(self):
		if self.webview is None:
			raise RuntimeError("WKWebView not loaded")
		self.webview.clear_cache()
		pass
	
	def load(self, app):
		self.app = app
		if self.webview is None:
			raise RuntimeError("WKWebView not loaded")
		self.webview.delegate = self.app
		self.webview.load_url(self.app.base_url, no_cache=True)

	def will_close(self):
		self.webview.close()
		self.app.cleanup()


class WKAppServer(threading.Thread):
	def __init__(self, app, host='localhost', port=8080, server_class=None):
		threading.Thread.__init__(self)
		self.app = app
		self.host = host
		self.port = port
		self.server_class = server_class
		
	def run(self):
		log.warning(f'WKApp - Server Starting...')
		if self.server_class is None:
			self.server_class = WSGIRefServer
		server_class = self.server_class
		self.server = server_class(port=self.port)
		self.app.run(host=self.host,port=self.port,server=self.server, debug = True)
				
	def get_id(self):
		if hasattr(self, '_thread_id'):
			return self._thread_id
		for id, thread in threading._active.items():
			if thread is self:
				return id
		return None
	
	def stop(self):
		log.warning(f'WKApp - Server Stopping...')
		if hasattr(self,'server') and hasattr(self.server,'srv'):
			server = self.server.srv
			if hasattr(server,'shutdown'):
				server.shutdown()
			if hasattr(server,'close'):
				server.close()
			elif hasattr(server,'server_close'):
				server.server_close()
		else:
			thread_id = self.get_id()
			if not thread_id is None:
				res = ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, ctypes.py_object(KeyboardInterrupt))
				if res > 1:
					ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
		self.join()
		log.warning(f'WKApp - Server Stopped.')

class WKView:
	def __init__(self, url = '', path = '', template = None, context = None):
		self.url = url
		self.path = path
		self.template = template


class WKViews:
	def __init__(self, app, app_views_path, module_views_path):
		bottle.TEMPLATE_PATH.clear()
		bottle.TEMPLATE_PATH.append(app_views_path)
		bottle.TEMPLATE_PATH.append(module_views_path)
		self.lookup = TemplateLookup(directories=bottle.TEMPLATE_PATH)
		self.app = app
		self.load_view = None
		self.next_view = None
		self.views = {}
		self.view = WKView()
		self.views[self.view.url] = self.view
		self.about_blank_view = WKView('about:blank')
		self.views[self.about_blank_view.url] = self.about_blank_view
	
	@property
	def base_url(self):
		return self.app.base_url
	
	@property
	def url(self):
		return self.view.url if self.view else ''

	@property
	def load_url(self):
		return self.load_view.url if not self.load_view is None else ''
		
	@property
	def next_url(self):
		return self.next_view.url if not self.next_view is None else ''
		
	def cancel_load_view(self):
		self.load_view = self.about_blank_view
		return False
	
	def get_url_path(self, url = None, path = None):
		if url is None and path is None:
			raise Exception('Must specify one of url or path')
		if url == 'about:blank':
			return url, url
		if not path is None and not path.startswith('/'):
			path = '/'+path
		if url is None and not path is None:
			url = self.base_url + path
		elif path is None and not url is None:
			parsed_url = urlparse(url)
			path = parsed_url.path
		if url == self.base_url + '/' or path == '/':
			path = '/index.html'
			url = self.base_url + path
		return url, path
		
	def get_view(self, url = None, path = None, create = False):
		view = None
		url,path = self.get_url_path(url,path)
		if url == 'about:blank':
			return self.about_blank_view
		if create and not url in self.views:
			try:
				view_template = self.lookup.get_template(path)
				if view_template is None:
					raise Exception("Mako template not found.")
				log.warning(f'WKViewState - Template found for {path} {view_template}')
			except:
				log.warning(f'WKViewState - No template found for path {path} {view_template}')
			if not view_template is None and hasattr(view_template.module, 'view_class'):
				view_class = view_template.module.view_class
				view = view_class() # call parameterless func or class ctor
				if view is None:
					raise Exception(f"view_class is defined but returned None or not an object value = '{view}'")
				view.url = url 
				view.path = path
				view.template = view_template
			else:
				view = WKView(url, path, view_template)
			self.views[path] = view
			self.views[url] = view
			if hasattr(view, 'on_init'):
				view.on_init()
			return view
		if not url is None:
			view = self.views[url]
		elif not path is None:
			view = self.views[path]
		return view

	def prepare_load_view(self, url, scheme, nav_type):
		log.warning(f'WKViewState - Preparing load {url}')
		view = self.get_view(url = url, create = True)
		self.load_view = view
		if hasattr(view, "on_prepare"):
			view.on_prepare()
		return True
	
	def start_load_view(self, url):
		log.warning(f'WKViewState - Start load {url}')
		url,path = self.get_url_path(url = url)
		if self.load_url != url:
			raise Exception(f'Unexpected view url "{url}" expected "{self.load_url}"')
		self.load_view = None
		view = self.get_view(url = url)
		self.next_view = view
		if hasattr(view, 'on_loading'):
			view.on_loading()

	def finish_load_view(self, url):
		log.warning(f'WKViewState - Finish load {url}')
		url,path = self.get_url_path(url)
		if self.next_url != url:
			raise Exception(f'Unexpected view url "{url}" expected "{self.next_url}"')
		self.next_view = None
		view = self.get_view(url = url)
		self.view = view
		if hasattr(view, 'on_loaded'):
			view.on_loaded()

class WKApp:
	
	def __init__(self, root = None, app = None, server = None, 
							app_views_path = 'views', app_static_path = 'static', 
							module_views_path = 'views', module_static_path ='static'):
		self.module_path = os.path.dirname(__file__)
		self.module_static_path = os.path.join(self.module_path, module_static_path)
		self.module_views_path = os.path.join(self.module_path, module_views_path)
		self._app_path = ''
		if root is None:
			root = self.module_static_path
		if os.path.isfile(root):
			root = os.path.dirname(root)
		self._app_path = root
		self.app_static_path = os.path.join(self.app_path,app_static_path)
		self.app_views_path = os.path.join(self.app_path,app_views_path)
			
		if app is None:
			self._app = Bottle()
			default_app.push(self.app)
		else:
			self._app = app
		self._app_view = None
		self._views = WKViews(self, self.app_views_path, self.module_views_path)
		self.host = 'localhost'
		self.port = 8080
		self.server = server
		self.server_internal = self.server is None
		with self.app:
			self.setup_server_routes()

		log.warning(f"WKApp - Init\n" +
		f"      - Module path: {self.module_path}\n"
		f"      - App path: {self.app_path}\n" +
		f"      - TEMPLATE_PATH: {bottle.TEMPLATE_PATH}")

	@property
	def app(self):
		return self._app
	
	@property
	def app_path(self):
		return self._app_path
		
	@property
	def base_url(self):
		return f'http://{self.host}:{self.port}'
	
	def start_server(self, host='localhost', port=8080):
		self.host = host
		self.port = port
		if self.server is None:
			self.server = WKAppServer(self.app, host, port)
			self.server_internal = True
		self.server.start()
	
	def stop_server(self):
		if not self.server is None:
			self.server.stop()
			if self.server_internal:
				self.server = None

	def present(self, mode='fullscreen', **kwargs):
		self._app_view = ui.load_view(os.path.join(self.module_path,'WKApp.pyui'))
		self.app_view.load(self)
		self.app_view.present(mode, **kwargs)
		
	def run(self, host = 'localhost', port = 8080, mode='fullscreen', **kwargs):
		log.warning(f'WKApp - Run')
		self.start_server(host, port)
		self.present(mode, **kwargs)
	
	def exit(self):
		if not self.app_view:
			return
		self.app_view.close()
	
	def cleanup(self):
		self.stop_server()
	
	def static_file(self, filepath, root = '/'):
		if root == '/':
			root = self.app_path
		if root != self.module_static_path and not os.path.exists(os.path.join(root,filepath)):
			root = self.module_static_path
		return static_file(filepath, root=root)
		
	def template(self, path, *args, **kwargs):
		return template(path, *args, lookup=self.views.lookup, **kwargs)
	
	def setup_server_routes(self):
		
		@route('/static/<filepath:path>')
		def server_static(filepath):
			return self.static_file(filepath)
		
		@route('/<filepath:path>')
		def server_template(filepath):
			view = self.views.get_view(path = filepath, create = True)
			return self.template(filepath, view = view)
		
		@route('/')
		def server_index():
			return server_template('index.html')

	@property
	def app_view(self):
		return self._app_view

	@property
	def app_webview(self):
		return self.app_view.webview if self.app_view else None
	
	@property
	def views(self):
		return self._views
	
	@property
	def view(self):
		return self.views.view
		
	def webview_should_start_load(self, webview, url, scheme, nav_type):
		 start = self.views.prepare_load_view(url, scheme, nav_type)
		 return start

	def webview_did_start_load(self, webview, url):
		self.views.start_load_view(url)

	def webview_did_finish_load(self, webview, url):
		self.views.finish_load_view(url)

	def webview_on_invoke(self, sender, typ, context, target, args, kwargs):
		url = sender.current_url
		log.warning(f'WKApp - INVOKE "{url}" "{typ}" "{context}" "{target}" "{args}" "{kwargs}"')
		pycontext = None
		if typ == "WKApp":
			pycontext = self
		elif typ == "WKView":
			pycontext = self.view
		else:
			raise Exception(f"Context type {typ} unhandled")
		if not hasattr(pycontext,target):
			raise Exception(f"Target '{target}' not found in context {pycontext}")
		pytarget = getattr(pycontext,target)
		if not callable(pytarget):
			raise Exception(f"Target '{target} {pytarget}' in context {pycontext} not callable")
		pytarget(*args,**kwargs)



if __name__ == '__main__':
	app = WKApp(__file__, app_views_path='test/views')
	app.run()
