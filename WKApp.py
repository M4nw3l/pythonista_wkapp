''' 
WKApp - A modern HTML5 UI framework for building iOS apps with Pythonista 3 and WebKit

https://github.com/M4nw3l/pythonista-wkapp
'''
import os
import sys
import threading
import ui

import logging
log = logging.getLogger(__name__)

import bottle
from bottle import Bottle, default_app
from bottle import WSGIRefServer
from bottle import (
	request,
	route,
	static_file,
	mako_template as template,
	mako_view as view,
)

try:
	from .WKWebView import *
except:
	from WKWebView import *

class WKAppWebView(WKWebView):
	pass
	
class WKAppView(ui.View):
		
	@property
	def webview(self):
		return self['webview']
		
	def did_load(self):
		if self.webview is None:
			raise RuntimeError("WKWebView not loaded")
		self.webview.clear_cache()
		pass
	
	def load(self, app, port=8080):
		self.app = app
		if self.webview is None:
			raise RuntimeError("WKWebView not loaded")
		self.webview.delegate = self
		self.webview.load_url(f'http://localhost:{port}', no_cache=True)

	def will_close(self):
		self.webview.close()
		self.app.cleanup()
	
	def webview_on_command(self, sender, text):
		self.app.webview_on_command(sender, text)

class WKAppServer(threading.Thread):
	def __init__(self, app, port=8080, server_class=None):
		threading.Thread.__init__(self)
		self.app = app
		self.port = port
		self.server_class = server_class
		
	def run(self):
		log.warning(f'WKApp - Server Starting...')
		if self.server_class is None:
			self.server_class = WSGIRefServer
		server_class = self.server_class
		self.server = server_class(host='localhost',port=self.port)
		self.app.run(host='localhost',port=self.port,server=self.server, debug = True)
				
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
		bottle.TEMPLATE_PATH.clear()
		bottle.TEMPLATE_PATH.insert(1,self.app_views_path)
		bottle.TEMPLATE_PATH.insert(3,self.module_views_path)
			
		if app is None:
			self._app = Bottle()
			default_app.push(self.app)
		else:
			self._app = app
		self._app_view = None
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
	
	def start_server(self, port=8080):
		if self.server is None:
			self.server = WKAppServer(self.app, port)
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
		
	def run(self, port = 8080, **kwargs):
		log.warning(f'WKApp - Run')
		self.start_server(port)
		self.present(**kwargs)
	
	def close(self):
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
	
	def setup_server_routes(self):
		
		@route('/static/<filepath:path>')
		def server_static(filepath):
			return self.static_file(filepath)
		
		@route('/<filepath:path>')
		def server_template(filepath):
			return template(filepath)
		
		@route('/')
		def server_index():
			return server_template('index.html')

	@property
	def app_view(self):
		return self._app_view

	@property
	def app_webview(self):
		return self.app_view.webview if self.app_view else None

	def webview_on_command(self, sender, text):
		url = sender.current_url
		log.warning(f'WKApp - COMMAND {url} "{text}"')
		text = text.strip()
		if text == "exit":
			self.close()
		else:
		  id = 'editor'
		  self.app_webview.eval_js(f'$("#{id}").val(`{text}`);')
		
				
class WKView:
	pass
		
if __name__ == '__main__':
	app = WKApp(__file__, app_views_path='test/views')
	app.run()
