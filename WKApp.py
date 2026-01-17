''' 
WKApp - A modern HTML5 UI framework for building iOS apps with Pythonista 3 and WebKit

https://github.com/M4nw3l/pythonista-wkapp
'''
__version__ = '0.0.1'

try:
	#pythonista specific libraries
	import ui
except:
	raise Exception("Pythonista 3 is required.")

import inspect
import os
import sys
import threading
from urllib.parse import urlparse

import bottle
from bottle import Bottle, default_app, BaseTemplate
from bottle import WSGIRefServer
from bottle import (
 request,
 response,
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

	def on_javascript_console_message(self, level, content):
		log.warning(f'WKAppWebView - JS - {level.upper()}: {content}')

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
		self.app.run(host=self.host, port=self.port, server=self.server, debug=True)

	def get_id(self):
		if hasattr(self, '_thread_id'):
			return self._thread_id
		for id, thread in threading._active.items():
			if thread is self:
				return id
		return None

	def stop(self):
		log.warning(f'WKApp - Server Stopping...')
		if hasattr(self, 'server') and hasattr(self.server, 'srv'):
			server = self.server.srv
			if hasattr(server, 'shutdown'):
				server.shutdown()
			if hasattr(server, 'close'):
				server.close()
			elif hasattr(server, 'server_close'):
				server.server_close()
		else:
			thread_id = self.get_id()
			if not thread_id is None:
				res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
				 thread_id, ctypes.py_object(KeyboardInterrupt))
				if res > 1:
					ctypes.pythonapi.PyThreadState_SetAsyncExc(thread_id, 0)
		self.join()
		log.warning(f'WKApp - Server Stopped.')


class WKConstants:
	unspecfied = object()


class WKJavascript:

	@staticmethod
	def str_escape(value, delim='`'):
		value = value.replace(delim, f'\\{delim}')
		return value

	@staticmethod
	def value_to_js(value):
		if isinstance(value, str):
			value = WKJavascript.str_escape(value, '`')
			value = f'`{value}`'
		elif isinstance(value, bool):
			value = 'true' if value == True else 'false'
		elif isinstance(value, (int, float, complex)):
			pass
		else:
			obj = json.dumps(value)
			value = f'{obj}'
		return value

	@staticmethod
	def value_to_py(value, typ, default=WKConstants.unspecfied):
		if value is None:
			if default == WKConstants.unspecfied:
				if typ in [str, int, float, complex, bool]:
					return typ()
				return value
			else:
				return default
		return typ(value)

	@staticmethod
	def function_call(name, *args, chain=False):
		code = [f'{name}(']
		first = True
		for arg in args:
			if not first:
				code.append(',')
			code.append(WKJavascript.value_to_js(arg))
			first = False
		code.append(')')
		if not chain:
			code.append(';')
		code = ''.join(code)
		return code

	@staticmethod
	def field(instance, name):
		return f'{instance}.{name}'

	@staticmethod
	def field_get(instance, name):
		return WKJavascript.field(instance, name) + ';'

	@staticmethod
	def field_set(instance, name, value):
		value = WKJavascript.value_to_js(value)
		return WKJavascript.field(instance, name) + f' = {value};'

	@staticmethod
	def instance_call(instance, name, *args, chain=False):
		return WKJavascript.field(
		 instance, WKJavascript.function_call(name, *args, chain=chain))

	@staticmethod
	def jquery(selector):
		return f'$("{selector}")'

	@staticmethod
	def document_get_element_by_id(id):
		return WKJavascript.instance_call('document', 'getElementById', id)


class WKElementsRef:

	def __init__(self, view, selector, js=WKJavascript):
		self.view = view
		self.selector = selector
		self.js = js
		self.elem = js.jquery(self.selector)

	def call(self, name, *args):
		script = self.js.instance_call(self.elem, name, *args)
		return self.view.eval_js(script)

	def get(self, name, typ=str, default=WKConstants.unspecfied):
		value = self.call(name)
		return self.js.value_to_py(value, typ, default)

	def set(self, name, value):
		self.call(name, value)


class WKView:

	def __init__(self, app=None, url='', path='', template=None, js=WKJavascript):
		self.app = app
		self.url = url
		self.path = path
		self.template = template
		self.js = js
		self.event('on_init')

	def webview(self):
		return self.app.app_webview

	def eval_js(self, script):
		return self.webview().eval_js(script)

	def eval_js_async(self, script):
		return self.webview().eval_js_async(script)

	def elements(self, selector):
		return WKElementsRef(self, selector, self.js)

	def element(self, id):
		return WKElementsRef(self, f'#{id}', self.js)

	def event(self, name, *args, **kwargs):
		if hasattr(self, name):
			func = getattr(self, name)
			func(*args, **kwargs)


class WKViews:

	def __init__(self, app, app_path, app_views_path, module_path,
	             module_views_path):
		bottle.TEMPLATE_PATH.clear()
		bottle.TEMPLATE_PATH.append(app_views_path)
		bottle.TEMPLATE_PATH.append(module_views_path)
		imports = []
		self.lookup = TemplateLookup(
		 directories=bottle.TEMPLATE_PATH,
		 #module_directory=os.path.join(app_path,'views-cache'),
		 imports=imports,
		)
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

	def get_url_path(self, url=None, path=None):
		if url is None and path is None:
			raise Exception('Must specify one of url or path')
		if url == 'about:blank':
			return url, url
		if not path is None and not path.startswith('/'):
			path = '/' + path
		if url is None and not path is None:
			url = self.base_url + path
		elif path is None and not url is None:
			parsed_url = urlparse(url)
			path = parsed_url.path
		if url == self.base_url + '/' or path == '/':
			path = '/index.html'
			url = self.base_url + path
		return url, path

	def get_view(self, url=None, path=None, create=False):
		view = None
		url, path = self.get_url_path(url, path)
		if url == 'about:blank':
			return self.about_blank_view
		if create and not url in self.views:
			try:
				view_template = self.lookup.get_template(path)
				if view_template is None:
					raise Exception("Mako template not found.")
				log.warning(f'WKViewState - Template found for {path} {view_template}')
			except:
				log.warning(
				 f'WKViewState - No template found for path {path} {view_template}')
			if not view_template is None and hasattr(view_template.module,
			                                         'view_class'):
				view_class = view_template.module.view_class

				class view_class_mixin(view_class, WKView):
					pass

				view = view_class_mixin(self.app, url, path, view_template)
				if view is None:
					raise Exception(
					 f"view_class is defined but returned None or not an object value = '{view}'"
					)
			else:
				view = WKView(self.app, url, path, view_template)
			self.views[path] = view
			self.views[url] = view
			return view
		if not url is None:
			view = self.views[url]
		elif not path is None:
			view = self.views[path]
		return view

	def prepare_load_view(self, url, scheme, nav_type):
		log.warning(f'WKViewState - Preparing load {url}')
		view = self.get_view(url=url, create=True)
		self.load_view = view
		view.event('on_prepare')
		return True

	def start_load_view(self, url):
		log.warning(f'WKViewState - Start load {url}')
		url, path = self.get_url_path(url=url)
		if self.load_url != url:
			raise Exception(f'Unexpected view url "{url}" expected "{self.load_url}"')
		self.load_view = None
		view = self.get_view(url=url)
		self.next_view = view
		view.event('on_loading')

	def finish_load_view(self, url):
		log.warning(f'WKViewState - Finish load {url}')
		url, path = self.get_url_path(url)
		if self.next_url != url:
			raise Exception(f'Unexpected view url "{url}" expected "{self.next_url}"')
		self.next_view = None
		view = self.get_view(url=url)
		self.view = view
		view.event('on_loaded')


class WKAppPlugin:

	def __init__(self, app):
		self.app = app
		self.callbacks = {}
		pass

	def setup(self, app):
		pass

	def has_args(self, callback, *args):
		spec = self.callbacks.get(callback, None)
		if spec is None:
			spec = inspect.getfullargspec(callback)
			spec = spec[0]
			self.callbacks[callback] = spec
		for arg in args:
			if not arg in spec:
				return False
		return True

	def apply(self, callback, route):
		# Enable cross origin isolation for browser to consider context secure enough for full web assembly and webgl support
		# https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/SharedArrayBuffer#security_requirements
		response.add_header('Cross-Origin-Opener-Policy', 'same-origin')
		response.add_header('Cross-Origin-Embedder-Policy', 'require-corp')
		if not self.has_args(callback, 'view'):
			return callback

		def wrapper(*args, **kwargs):
			view = self.app.get_view(url=request.url, create=True)
			kwargs['view'] = view
			return callback(*args, **kwargs)

		return wrapper


class WKApp:

	def __init__(self,
	             root=None,
	             port=8080,
	             host='localhost',
	             app=None,
	             server=None,
	             app_views_path='views',
	             app_static_path='static',
	             module_views_path='views',
	             module_static_path='static'):
		self.module_path = os.path.dirname(__file__)
		self.module_static_path = os.path.join(self.module_path, module_static_path)
		self.module_views_path = os.path.join(self.module_path, module_views_path)
		self._app_path = ''
		if root is None:
			root = self.module_static_path
		if os.path.isfile(root):
			root = os.path.dirname(root)
		self._app_path = root
		self.app_static_path = os.path.join(self.app_path, app_static_path)
		self.app_views_path = os.path.join(self.app_path, app_views_path)

		if app is None:
			self._app = Bottle()
			default_app.push(self.app)
		else:
			self._app = app

		self._app_view = None
		self._views = WKViews(self, self.app_path, self.app_views_path,
		                      self.module_path, self.module_views_path)
		self.host = host
		self.port = port
		self.server = server
		self.server_internal = self.server is None

		self.plugin = WKAppPlugin(self)
		self.app.install(self.plugin)
		with self.app:
			self.setup_server_routes()

		log.warning(f"WKApp - Init\n" + f"      - Module path: {self.module_path}\n"
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

	def start_server(self):
		if self.server is None and self.server_internal:
			self.server = WKAppServer(self.app, self.host, self.port)
			self.server.start()

	def stop_server(self):
		if not self.server is None and self.server_internal:
			self.server.stop()
			self.server = None

	def present(self, mode='fullscreen', **kwargs):
		self._app_view = ui.load_view(os.path.join(self.module_path, 'WKApp.pyui'))
		self.app_view.load(self)
		self.app_view.present(mode, **kwargs)

	def run(self, mode='fullscreen', **kwargs):
		log.warning(f'WKApp - Run')
		self.start_server()
		self.present(mode, **kwargs)

	def exit(self):
		if not self.app_view:
			return
		self.app_view.close()

	def cleanup(self):
		self.stop_server()

	def static_file(self, filepath, root='/'):
		if root == '/':
			root = self.app_path
		if root != self.module_static_path and not os.path.exists(
		  os.path.join(root, filepath)):
			root = self.module_static_path
		return static_file(filepath, root=root)

	def template(self, path, **kwargs):
		return template(path, lookup=self.views.lookup, **kwargs)

	def get_view(self, url=None, path=None, create=False):
		view = self.views.get_view(url=url, path=path, create=create)
		if view is None:
			return view
		values = {}
		query = {}
		kwargs = {'request': request, 'values': values, 'query': query}
		method = request.method
		for k, v in request.query.iteritems():
			query[k] = v
			values[k] = v
			if hasattr(view, k):
				setattr(view, k, v)
		if method == 'POST':
			for k, v in request.forms.iteritems():
				values[k] = v
				if hasattr(view, k):
					setattr(view, k, v)
		view.event('on_' + method, **kwargs)
		return view

	def setup_server_routes(self):

		@route('/static/<filepath:path>')
		def server_static(filepath):
			return self.static_file(filepath)

		@route('/<filepath:path>')
		def server_template_get(filepath, view):
			return self.template(filepath, view=view)

		@route('/<filepath:path>', method='POST')
		def server_template_post(filepath, view):
			return self.template(filepath, view=view)

		@route('/')
		def server_index_get(view):
			return server_template_get('index.html', view)

		@route('/', method='POST')
		def server_index_post(view):
			return server_template_post('index.html', view)

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
		url, path = self.views.get_url_path(url=url)
		log.warning(
		 f'WKApp - INVOKE "{url}" "{typ}" "{context}" "{target}" "{args}" "{kwargs}"'
		)
		pycontext = None
		if typ == "WKApp":
			pycontext = self
		elif typ == "WKView":
			if url == self.view.url:
				pycontext = self.view
			else:
				pycontext = self.views.get_view(url=url, path=path)
		else:
			raise Exception(f"Context type {typ} unhandled")
		if not hasattr(pycontext, target):
			raise Exception(f"Target '{target}' not found in context {pycontext}")
		pytarget = getattr(pycontext, target)
		if not callable(pytarget):
			raise Exception(
			 f"Target '{target} {pytarget}' in context {pycontext} not callable")
		pytarget(*args, **kwargs)


if __name__ == '__main__':
	app = WKApp(__file__, app_views_path='test/views')
	app.run()

