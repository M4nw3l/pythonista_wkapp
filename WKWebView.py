#coding: utf-8
'''
WKWebView - modern webview for Pythonista
1.0 -	https://github.com/mikaelho/pythonista-webview
1.1 - https://gist.github.com/sbbosco/1290f59d79c6963e62bb678f0f05b035
1.2 - Fixes and improvements by M4nw3l
		 - Improved delegate object support 
		 - Fixed content injection methods misrendering some js
		 - Extended content injection methods to support reading from files
		 - Added dispatcher queue thread to avoid deadlocks in callbacks / script message callbacks
		   e.g eval_js can now be called from on_[script_message_name] handlers, webview_did_finish_load, 
		   webview_did_start_load (if targets loaded)
		 - Added some better handling for being notified when closing
		 - Added some automatic cleanup on close e.g stopping the dispatcher thread
'''

__version__ = '1.2'

from objc_util import *
import ui, console, webbrowser
import queue, weakref, ctypes, functools, time, os, json, re, sys
from types import SimpleNamespace
import threading
import time
import logging

log = logging.getLogger(__name__)
# Helpers for invoking ObjC function blocks with no return value


class _block_descriptor(Structure):
	_fields_ = [('reserved', c_ulong), ('size', c_ulong),
	            ('copy_helper', c_void_p), ('dispose_helper', c_void_p),
	            ('signature', c_char_p)]


def _block_literal_fields(*arg_types):
	return [('isa', c_void_p), ('flags', c_int), ('reserved', c_int),
	        ('invoke', ctypes.CFUNCTYPE(c_void_p, c_void_p, *arg_types)),
	        ('descriptor', _block_descriptor)]


class WKWebView(ui.View):

	# Data detector constants
	NONE = 0
	PHONE_NUMBER = 1
	LINK = 1 << 1
	ADDRESS = 1 << 2
	CALENDAR_EVENT = 1 << 3
	TRACKING_NUMBER = 1 << 4
	FLIGHT_NUMBER = 1 << 5
	LOOKUP_SUGGESTION = 1 << 6
	ALL = 18446744073709551615  # NSUIntegerMax

	# Global webview index for console
	webviews = []
	console_view = UIApplication.sharedApplication().\
     keyWindow().rootViewController().\
     accessoryViewController().\
     consoleViewController()

	def __init__(self,
	             swipe_navigation=False,
	             data_detectors=NONE,
	             log_js_evals=False,
	             respect_safe_areas=False,
	             inline_media=None,
	             airplay_media=True,
	             pip_media=True,
	             **kwargs):

		self.init_webview()

		WKWebView.webviews.append(self)
		self.delegate = None
		self.log_js_evals = log_js_evals
		self.respect_safe_areas = respect_safe_areas
		super().__init__(**kwargs)
		self.request_url = ''
		self.requested_url = ''
		self.current_url = ''
		self.eval_js_queue = queue.Queue()

		self.dispatcher = WKWebView._webviewDispatcher()
		self.dispatcher.daemon = True

		custom_message_handler = WKWebView.CustomMessageHandler.\
      new().autorelease()
		retain_global(custom_message_handler)
		custom_message_handler._pythonistawebview = weakref.ref(self)
		self.custom_message_handler = custom_message_handler

		user_content_controller = WKWebView.WKUserContentController.\
      new().autorelease()
		self.user_content_controller = user_content_controller
		for key in dir(self):
			if key.startswith('on_'):
				message_name = key[3:]
				user_content_controller.addScriptMessageHandler_name_(
				 custom_message_handler, message_name)

		webview_config = WKWebView.WKWebViewConfiguration.new().autorelease()
		webview_config.userContentController = user_content_controller

		data_detectors = sum(data_detectors) if type(data_detectors) is tuple \
      else data_detectors
		webview_config.setDataDetectorTypes_(data_detectors)

		# Must be set to True to get real js
		# errors, in combination with setting a
		# base directory in the case of load_html
		webview_config.preferences().setValue_forKey_(True,
		                                              'allowFileAccessFromFileURLs')

		if inline_media is not None:
			webview_config.allowsInlineMediaPlayback = inline_media
		webview_config.allowsAirPlayForMediaPlayback = airplay_media
		webview_config.allowsPictureInPictureMediaPlayback = pip_media

		nav_delegate = WKWebView.CustomNavigationDelegate.new()
		retain_global(nav_delegate)
		nav_delegate._pythonistawebview = weakref.ref(self)

		ui_delegate = WKWebView.CustomUIDelegate.new()
		retain_global(ui_delegate)
		ui_delegate._pythonistawebview = weakref.ref(self)
		
		url_scheme_handler = WKWebView.CustomURLSchemeHandler.new()
		retain_global(url_scheme_handler)
		url_scheme_handler._pythonistawebview = weakref.ref(self)
		self.url_scheme_handlers = {}
		for key in dir(self):
			if key.startswith('scheme_'):
				scheme = key[7:]
				if not scheme in self.url_scheme_handlers:
					if WKWebView.WKWebView.handlesURLScheme_(scheme):
						raise Exception("WKURLSchemeHandler cannot create custom scheme for '{scheme}'")
					self.url_scheme_handlers[scheme] = getattr(self,key)
					webview_config.setURLSchemeHandler_forURLScheme_(url_scheme_handler,scheme)
		self.url_scheme_task_pool = WKWebView._urlSchemeTaskPool(self.url_scheme_handlers)
		self._create_webview(webview_config, nav_delegate, ui_delegate)

		self.swipe_navigation = swipe_navigation
		self.add_script(WKWebView.js_logging_script, add_to_end=False, all_frames=True)
		self.dispatcher.start()

	def will_close(self):
		self.dispatcher.stop(join=False)

	@on_main_thread
	def close(self):
		self.will_close()
		self.dispatcher.stop(join=False)
		super().close()

	@on_main_thread
	def _create_webview(self, webview_config, nav_delegate, ui_delegate):
		self.webview = WKWebView.WKWebView.alloc().\
      initWithFrame_configuration_(
		    ((0,0), (self.width, self.height)), webview_config).autorelease()
		self.webview.autoresizingMask = 2 + 16  # WH
		self.webview.setNavigationDelegate_(nav_delegate)
		self.webview.setUIDelegate_(ui_delegate)
		self.objc_instance.addSubview_(self.webview)

	@on_main_thread
	def init_webview(self):
		# This work around appears to prevent a pythonista app crash
		# it is probably initialising some memory / handles somewhere in UIKit
		# before _create_webview sets up the real WKWebView instance
		webview = WKWebView.WKWebView.alloc().initWithFrame_(
		 ((0, 0), (0, 0))).autorelease()
		del webview

	def layout(self):
		if self.respect_safe_areas:
			self.update_safe_area_insets()

	@on_main_thread
	def load_url(self, url, no_cache=False, timeout=10):
		""" Loads the contents of the given url
        asynchronously.

        If the url starts with `file://`, loads a local file. If the remaining
        url starts with `/`, path starts from Pythonista root.

        For remote (non-file) requests, there are
        two additional options:

          * Set `no_cache` to `True` to skip the local cache, default is `False`
          * Set `timeout` to a specific timeout value, default is 10 (seconds)
        """
		self.request_url = url
		if url.startswith('file://'):
			file_path = url[7:]
			if file_path.startswith('/'):
				root = os.path.expanduser('~')
				if not file_path.startswith(root):
					file_path = os.path.join(root, file_path[1:])
			else:
				current_working_directory = os.path.dirname(os.getcwd())
				file_path = os.path.join(current_working_directory, file_path)
			dir_only = os.path.dirname(file_path)
			file_path = NSURL.fileURLWithPath_(file_path)
			dir_only = NSURL.fileURLWithPath_(dir_only)
			self.webview.loadFileURL_allowingReadAccessToURL_(file_path, dir_only)
		else:
			cache_policy = 1 if no_cache else 0
			self.webview.loadRequest_(
			 WKWebView.NSURLRequest.requestWithURL_cachePolicy_timeoutInterval_(
			  nsurl(url), cache_policy, timeout))

	@on_main_thread
	def load_html(self, html):
		# Need to set a base directory to get
		# real js errors
		self.request_url = 'html:raw'
		current_working_directory = os.path.dirname(os.getcwd())
		root_dir = NSURL.fileURLWithPath_(current_working_directory)
		self.webview.loadHTMLString_baseURL_(html, root_dir)

	@on_main_thread
	def load_file(self, path, root='/'):
		if root == '/':
			root = __file__
		elif not os.path.isabs(root):
			root = os.path.join(os.path.dirname(__file__), root)
		if os.path.isfile(root):
			root = os.path.dirname(root)
		self.load_url('file://' + os.path.join(root, path), no_cache=True)

	def eval_js(self, js):
		self.eval_js_async(js, self._eval_js_sync_callback)
		value = self.eval_js_queue.get()
		return value

	evaluate_javascript = eval_js

	@on_main_thread
	def _eval_js_sync_callback(self, value):
		self.eval_js_queue.put(value)

	@ui.in_background
	def eval_js_async(self, js, callback=None):
		if self.log_js_evals:
			self.console.message({'level': 'code', 'content': js})
		handler = functools.partial(WKWebView._handle_completion, callback, self)
		block = ObjCBlock(handler,
		                  restype=None,
		                  argtypes=[c_void_p, c_void_p, c_void_p])
		retain_global(block)
		self.webview.evaluateJavaScript_completionHandler_(js, block)

	@ui.in_background
	def clear_cache(self, completion_handler=None):
		store = WKWebView.WKWebsiteDataStore.defaultDataStore()
		data_types = WKWebView.WKWebsiteDataStore.allWebsiteDataTypes()
		from_start = WKWebView.NSDate.dateWithTimeIntervalSince1970_(0)

		def dummy_completion_handler():
			pass

		store.removeDataOfTypes_modifiedSince_completionHandler_(
		 data_types, from_start, completion_handler or dummy_completion_handler)

	# Javascript evaluation completion handler

	def _handle_completion(callback, webview, _cmd, _obj, _err):
		result = str(ObjCInstance(_obj)) if _obj else None
		if webview.log_js_evals:
			webview._message({'level': 'raw', 'content': str(result)})
		if callback:
			callback(result)

	def add_script(self, js_script, add_to_end=True, all_frames=False):
		location = 1 if add_to_end else 0
		wk_script = WKWebView.WKUserScript.alloc().\
      initWithSource_injectionTime_forMainFrameOnly_(
		        js_script, location, all_frames)
		self.user_content_controller.addUserScript_(wk_script)

	def add_style(self, css, add_to_end=True):
		"""
        Convenience method to add a style tag with the given css, to every
        page loaded by the view.
        """
		css = css.replace("'", "\'")
		js = "var style = document.createElement('style');\n"
		js = js + f"style.innerHTML = `{css}`;\n"
		js = js + "document.getElementsByTagName('head')[0].appendChild(style);"
		self.add_script(js, add_to_end)

	def add_user_content_file(self, filename, root='/', add_to_end=True):
		if root == '/':
			root = __file__
		if os.path.isfile(root):
			root = os.path.dirname(root)
		content = ''
		with open(os.path.join(root, filename), 'r') as content_file:
			content = content_file.read()
		if filename.endswith(".js"):
			self.add_script(content, add_to_end)
		elif filename.endswith(".css"):
			self.add_style(content)

	def add_meta(self, name, content):
		"""
        Convenience method to add a meta tag with the given name and content,
        to every page loaded by the view."
        """
		name = name.replace("'", "\'")
		content = content.replace("'", "\'")
		js = "var meta = document.createElement('meta');"
		js = js + f"meta.setAttribute('name', '{name}');"
		js = js + f"meta.setAttribute('content', '{content}');"
		js = js + "document.getElementsByTagName('head')[0].appendChild(meta);"
		self.add_script(js, add_to_end=True)

	def add_script_message_handler_name(self, name):
		self.user_content_controller.addScriptMessageHandler_name_(
		 self.custom_message_handler, name)

	def disable_zoom(self):
		name = 'viewport'
		content = 'width=device-width, initial-scale=1.0,'
		'maximum-scale=1.0, user-scalable=no'
		self.add_meta(name, content)

	def disable_user_selection(self):
		css = '* { -webkit-user-select: none; }'
		self.add_style(css)

	def disable_font_resizing(self):
		css = 'body { -webkit-text-size-adjust: none; }'
		self.add_style(css)

	def disable_scrolling(self):
		"""
        Included for consistency with the other `disable_x` methods, this is
        equivalent to setting `scroll_enabled` to false."
        """
		self.scroll_enabled = False

	def disable_all(self):
		"""
        Convenience method that calls all the `disable_x` methods to make the
        loaded pages act more like an app."
        """
		self.disable_zoom()
		self.disable_scrolling()
		self.disable_user_selection()
		self.disable_font_resizing()

	@property
	def delegate(self):
		return self._delegate

	@delegate.setter
	def delegate(self, value):
		self._delegate = value
		if not self._delegate is None:
			for key in dir(self._delegate):
				if key.startswith('webview_on_'):
					message_name = key[11:]
					self.add_script_message_handler_name(message_name)

	@property
	def user_agent(self):
		"Must be called outside main thread"
		return self.eval_js('navigator.userAgent')

	@on_main_thread
	def _get_user_agent2(self):
		return str(self.webview.customUserAgent())

	@user_agent.setter
	def user_agent(self, value):
		value = str(value)
		self._set_user_agent(value)

	@on_main_thread
	def _set_user_agent(self, value):
		self.webview.setCustomUserAgent_(value)

	@on_main_thread
	def go_back(self):
		self.webview.goBack()

	@on_main_thread
	def go_forward(self):
		self.webview.goForward()

	@on_main_thread
	def reload(self):
		self.webview.reload()

	@on_main_thread
	def stop(self):
		self.webview.stopLoading()

	@property
	def scales_page_to_fit(self):
		raise NotImplementedError(
		 'Not supported on iOS. Use the "disable_" methods instead.')

	@scales_page_to_fit.setter
	def scales_page_to_fit(self, value):
		raise NotImplementedError(
		 'Not supported on iOS. Use the "disable_" methods instead.')

	@property
	def swipe_navigation(self):
		return self.webview.allowsBackForwardNavigationGestures()

	@swipe_navigation.setter
	def swipe_navigation(self, value):
		self.webview.setAllowsBackForwardNavigationGestures_(value == True)

	@property
	def scroll_enabled(self):
		"""
        Controls whether scrolling is enabled.
        Disabling scrolling is applicable for pages that need to look like an
        app.
        """
		return self.webview.scrollView().scrollEnabled()

	@scroll_enabled.setter
	def scroll_enabled(self, value):
		self.webview.scrollView().setScrollEnabled_(value == True)

	def update_safe_area_insets(self):
		insets = self.objc_instance.safeAreaInsets()
		self.frame = self.frame.inset(insets.top, insets.left, insets.bottom,
		                              insets.right)

	def _javascript_alert(self, host, message):
		console.alert(host, message, 'OK', hide_cancel_button=True)

	def _javascript_confirm(self, host, message):
		try:
			console.alert(host, message, 'OK')
			return True
		except KeyboardInterrupt:
			return False

	def _javascript_prompt(self, host, prompt, default_text):
		try:
			return console.input_alert(host, prompt, default_text, 'OK')
		except KeyboardInterrupt:
			return None

	js_logging_script = '''console = new Object();
    console.info = function(message) { 
     window.webkit.messageHandlers.javascript_console_message.postMessage(
      JSON.stringify({ level: "info", content: message})
     ); return false; };
    console.log = function(message) { 
     window.webkit.messageHandlers.javascript_console_message.postMessage(
      JSON.stringify({ level: "log", content: message})
     ); return false; };
    console.warn = function(message) { 
     window.webkit.messageHandlers.javascript_console_message.postMessage(
      JSON.stringify({ level: "warn", content: message})
     ); return false; };
    console.error = function(message) {
     window.webkit.messageHandlers.javascript_console_message.postMessage(
      JSON.stringify({ level: "error", content: message})
     ); return false; };
    window.onerror = function(error, url, line, col, errorobj) {
     console.error(
      "" + error + " (" + url + ", line: " + line + ", column: " + col + ")"
     );
    };'''

	def on_javascript_console_message(self, level, content):
		log_message = {'level':level,'content':content}
		self._message(log_message)

	def _message(self, message):
		level, content = message['level'], message['content']
		if level == 'code':
			print('>>> ' + content)
		elif level == 'raw':
			print(content)
		else:
			#print(level.upper() + ': ' + content)
			print(level.upper() + ': ' + str(content))

	class Theme:

		@classmethod
		def get_theme(cls):
			theme_dict = json.loads(cls.clean_json(cls.get_theme_data()))
			theme = SimpleNamespace(**theme_dict)
			theme.dict = theme_dict
			return theme

		@classmethod
		def get_theme_data(cls):
			# Name of current theme
			defaults = ObjCClass("NSUserDefaults").standardUserDefaults()
			name = str(defaults.objectForKey_("ThemeName"))
			# Theme is user-created
			if name.startswith("User:"):
				home = os.getenv("CFFIXED_USER_HOME")
				user_themes_path = os.path.join(home, "Library/Application Support/Themes")
				theme_path = os.path.join(user_themes_path, name[5:] + ".json")
			# Theme is built-in
			else:
				res_path = str(ObjCClass("NSBundle").mainBundle().resourcePath())
				theme_path = os.path.join(res_path, "Themes2/%s.json" % name)
			# Read theme file
			with open(theme_path, "r") as f:
				data = f.read()
			# Return contents
			return data

		@classmethod
		def clean_json(cls, string):
			# From http://stackoverflow.com/questions/23705304
			string = re.sub(r',[ \t\r\n]+}', "}", string)
			string = re.sub(r',[ \t\r\n]+\]', "]", string)
			return string

	@classmethod
	def console(self, webview_index=0):
		webview = WKWebView.webviews[webview_index]
		theme = WKWebView.Theme.get_theme()

		print('Welcome to WKWebView console.')
		print('Evaluate javascript in any active WKWebView.')
		print('Special commands: list, switch #, load <url>, quit')
		console.set_color(*ui.parse_color(theme.tint)[:3])
		while True:
			value = input('js> ').strip()
			self.console_view.history().insertObject_atIndex_(ns(value + '\n'), 0)
			if value == 'quit':
				break
			if value == 'list':
				for i in range(len(WKWebView.webviews)):
					wv = WKWebView.webviews[i]
					print(i, '-', wv.name, '-', wv.eval_js('document.title'))
			elif value.startswith('switch '):
				i = int(value[len('switch '):])
				webview = WKWebView.webviews[i]
			elif value.startswith('load '):
				url = value[len('load '):]
				webview.load_url(url)
			else:
				print(webview.eval_js(value))
		console.set_color(*ui.parse_color(theme.default_text)[:3])

	# MAIN OBJC SECTION

	WKWebView = ObjCClass('WKWebView')
	UIViewController = ObjCClass('UIViewController')
	WKWebViewConfiguration = ObjCClass('WKWebViewConfiguration')
	WKUserContentController = ObjCClass('WKUserContentController')
	NSURLRequest = ObjCClass('NSURLRequest')
	WKUserScript = ObjCClass('WKUserScript')
	WKWebsiteDataStore = ObjCClass('WKWebsiteDataStore')
	NSDate = ObjCClass('NSDate')

	# Navigation delegate

	class _block_decision_handler(Structure):
		_fields_ = _block_literal_fields(ctypes.c_long)

	#@ui.in_background
	def webView_decidePolicyForNavigationAction_decisionHandler_(
	  _self, _cmd, _webview, _navigation_action, _decision_handler):
		delegate_instance = ObjCInstance(_self)
		webview = delegate_instance._pythonistawebview()
		deleg = webview.delegate
		nav_action = ObjCInstance(_navigation_action)
		ns_url = nav_action.request().URL()
		url = str(ns_url)
		nav_type = int(nav_action.navigationType())

		allow = True
		scheme = str(ns_url.scheme())
		webview.requested_url = url
		if url != 'about:blank':
			try:
				if allow and hasattr(webview, "webview_should_start_load"):
					allow = webview.webview_should_start_load(url, scheme, nav_type)
				if allow and deleg is not None:
					if hasattr(deleg, 'webview_should_start_load'):
						allow = deleg.webview_should_start_load(webview, url, scheme, nav_type)
				if allow and not scheme in webview.url_scheme_handlers and not WKWebView.WKWebView.handlesURLScheme_(scheme):
					allow = False
					webview.current_url = url
					webbrowser.open(url)
			except Exception as e:
				log.error(f'WKWebView exception in should_start_load handler', e)
		log.warning(f'WKWebView {url} {allow}')
		allow_or_cancel = 1 if allow else 0
		decision_handler = ObjCInstance(_decision_handler)
		retain_global(decision_handler)
		blk = WKWebView._block_decision_handler.from_address(_decision_handler)
		blk.invoke(_decision_handler,
		           1)  #allow_or_cancel - dissallowing seems to break closing
		if not allow:

			def reload_blank(webview):
				webview.stop()
				webview.load_url('about:blank')

			webview.dispatcher.dispatch(reload_blank, webview)

	f = webView_decidePolicyForNavigationAction_decisionHandler_
	f.argtypes = [c_void_p] * 3
	f.restype = None
	f.encoding = b'v@:@@@?'

	# thread dispatcher
	class _webviewDispatcher(threading.Thread):

		def __init__(self):
			threading.Thread.__init__(self)
			self.running = False
			self.queue = []

		class _dispatchMessage:

			def __init__(self, func, *args, **kwargs):
				self.func = func
				self.args = args
				self.kwargs = kwargs

		def dispatch(self, func, *args, **kwargs):
			self.queue.append(self._dispatchMessage(func, *args, **kwargs))

		def invoke(self, instance, name, *args, **kwargs):

			def _instance_invoke(instance, name, *args, **kwargs):
				func = getattr(instance, name) if hasattr(instance, name) else None
				if func:
					func(*args, **kwargs)
				deleg = instance.delegate if hasattr(instance, 'delegate') else None
				func = getattr(deleg, name) if deleg and hasattr(deleg, name) else None
				if func:
					func(instance, *args, **kwargs)

			self.dispatch(_instance_invoke, instance, name, *args, **kwargs)

		def run(self):
			self.running = True
			while self.running:
				if len(self.queue) < 1:
					time.sleep(0.01)
				else:
					while len(self.queue) > 0 and self.running:
						msg = self.queue.pop(0)
						func = msg.func
						args = msg.args
						kwargs = msg.kwargs
						if func:
							try:
								func(*args, **kwargs)
							except Exception as e:
								log.error(f"WKWebView dispatch error {e}, {func}, {args}, {kwargs}")

		def stop(self, join=True):
			self.running = False
			if join:
				self.join()

	# https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/ObjCRuntimeGuide/Articles/ocrtTypeEncodings.html
	def webView_didCommitNavigation_(_self, _cmd, _webview, _navigation):
		delegate_instance = ObjCInstance(_self)
		webview = delegate_instance._pythonistawebview()
		webview.dispatcher.invoke(webview, 'webview_did_start_load',
		                          webview.requested_url)

	def webView_didFinishNavigation_(_self, _cmd, _webview, _navigation):
		delegate_instance = ObjCInstance(_self)
		webview = delegate_instance._pythonistawebview()
		webview.current_url = webview.requested_url
		webview.dispatcher.invoke(webview, 'webview_did_finish_load',
		                          webview.current_url)

	def webView_didFailNavigation_withError_(_self, _cmd, _webview, _navigation,
	                                         _error):
		delegate_instance = ObjCInstance(_self)
		webview = delegate_instance._pythonistawebview()
		deleg = webview.delegate
		err = ObjCInstance(_error)
		error_code = int(err.code())
		error_msg = str(err.localizedDescription())
		url = webview.requested_url if not webview.requested_url is None else webview.request_url
		handle = False
		if hasattr(webview, 'webview_did_fail_load'):
			handle = True
		if deleg is not None and hasattr(deleg, 'webview_did_fail_load'):
			handle = True
		if handle:
			webview.dispatcher.invoke(webview, 'webview_did_fail_load', url, error_code,
			                          error_msg)
		else:
			log.exception(
			 RuntimeError(
			  f'WKWebView load failed to load {url} with code {error_code}: {error_msg}'
			 ))

	def webView_didFailProvisionalNavigation_withError_(_self, _cmd, _webview,
	                                                    _navigation, _error):
		WKWebView.webView_didFailNavigation_withError_(_self, _cmd, _webview,
		                                               _navigation, _error)

	CustomNavigationDelegate = create_objc_class(
	 'CustomNavigationDelegate',
	 superclass=NSObject,
	 methods=[
	  webView_didCommitNavigation_, webView_didFinishNavigation_,
	  webView_didFailNavigation_withError_,
	  webView_didFailProvisionalNavigation_withError_,
	  webView_decidePolicyForNavigationAction_decisionHandler_
	 ],
	 protocols=['WKNavigationDelegate'])

	# Script message handler
	def userContentController_didReceiveScriptMessage_(_self, _cmd,
	                                                   _userContentController,
	                                                   _message):
		controller_instance = ObjCInstance(_self)
		webview = controller_instance._pythonistawebview()
		wk_message = ObjCInstance(_message)
		name = str(wk_message.name())
		content = str(wk_message.body())
		handler = getattr(webview, 'on_' + name, None)
		deleg = webview.delegate
		deleg_handler = getattr(deleg, 'webview_on_' + name, None) if deleg else None
		def handle_script_message(webview, name, content, handler, deleg_handler):
			#print("script message handler ",name,content,handler,deleg_handler)
			args = []
			kwargs = {}
			try:
				data = json.loads(content)
				if 'args' in data or 'kwargs' in data:
					args = data['args'] if 'args' in data else args
					kwargs = data['kwargs'] if 'kwargs' in data else kwargs
				else:
					kwargs = data
			except:
				args.append(content)

			handled = False
			if handler:
				handler(*args, **kwargs)
				handled = True
			if deleg_handler:
				deleg_handler(webview, *args, **kwargs)
				handled = True
			if not handled:
				raise Exception(
				 f'Unhandled message from script - name: {name}, content: {content}')

		webview.dispatcher.dispatch(handle_script_message, webview, name, content,
		                            handler, deleg_handler)

	CustomMessageHandler = create_objc_class(
	 'CustomMessageHandler',
	 UIViewController,
	 methods=[userContentController_didReceiveScriptMessage_],
	 protocols=['WKScriptMessageHandler'])

	# UI delegate (for alerts etc.)
	class _block_alert_completion(Structure):
		_fields_ = _block_literal_fields()

	def webView_runJavaScriptAlertPanelWithMessage_initiatedByFrame_completionHandler_(
	  _self, _cmd, _webview, _message, _frame, _completion_handler):
		delegate_instance = ObjCInstance(_self)
		webview = delegate_instance._pythonistawebview()
		message = str(ObjCInstance(_message))
		host = str(ObjCInstance(_frame).request().URL().host())
		webview._javascript_alert(host, message)
		#console.alert(host, message, 'OK', hide_cancel_button=True)
		completion_handler = ObjCInstance(_completion_handler)
		retain_global(completion_handler)
		blk = WKWebView._block_alert_completion.from_address(_completion_handler)
		blk.invoke(_completion_handler)

	f = webView_runJavaScriptAlertPanelWithMessage_initiatedByFrame_completionHandler_
	f.argtypes = [c_void_p] * 4
	f.restype = None
	f.encoding = b'v@:@@@@?'

	class _block_confirm_completion(Structure):
		_fields_ = _block_literal_fields(ctypes.c_bool)

	def webView_runJavaScriptConfirmPanelWithMessage_initiatedByFrame_completionHandler_(
	  _self, _cmd, _webview, _message, _frame, _completion_handler):
		delegate_instance = ObjCInstance(_self)
		webview = delegate_instance._pythonistawebview()
		message = str(ObjCInstance(_message))
		host = str(ObjCInstance(_frame).request().URL().host())
		result = webview._javascript_confirm(host, message)
		completion_handler = ObjCInstance(_completion_handler)
		retain_global(completion_handler)
		blk = WKWebView._block_confirm_completion.from_address(_completion_handler)
		blk.invoke(_completion_handler, result)

	f = webView_runJavaScriptConfirmPanelWithMessage_initiatedByFrame_completionHandler_
	f.argtypes = [c_void_p] * 4
	f.restype = None
	f.encoding = b'v@:@@@@?'

	class _block_text_completion(Structure):
		_fields_ = _block_literal_fields(c_void_p)

	def webView_runJavaScriptTextInputPanelWithPrompt_defaultText_initiatedByFrame_completionHandler_(
	  _self, _cmd, _webview, _prompt, _default_text, _frame, _completion_handler):
		delegate_instance = ObjCInstance(_self)
		webview = delegate_instance._pythonistawebview()
		prompt = str(ObjCInstance(_prompt))
		default_text = str(ObjCInstance(_default_text))
		host = str(ObjCInstance(_frame).request().URL().host())
		result = webview._javascript_prompt(host, prompt, default_text)
		completion_handler = ObjCInstance(_completion_handler)
		retain_global(completion_handler)
		blk = WKWebView._block_text_completion.from_address(_completion_handler)
		blk.invoke(_completion_handler, ns(result))

	f = webView_runJavaScriptTextInputPanelWithPrompt_defaultText_initiatedByFrame_completionHandler_
	f.argtypes = [c_void_p] * 5
	f.restype = None
	f.encoding = b'v@:@@@@@?'

	CustomUIDelegate = create_objc_class(
	 'CustomUIDelegate',
	 superclass=NSObject,
	 methods=[
	  webView_runJavaScriptAlertPanelWithMessage_initiatedByFrame_completionHandler_,
	  webView_runJavaScriptConfirmPanelWithMessage_initiatedByFrame_completionHandler_,
	  webView_runJavaScriptTextInputPanelWithPrompt_defaultText_initiatedByFrame_completionHandler_
	 ],
	 protocols=['WKUIDelegate'])
	 
	class _urlSchemeTaskPool:
		class _urlSchemeTask:
			def __init__(self, id, task, request):
				self.id = id
				self.task = task
				self.request = request
				self.request_url = self.request.URL()
				self.url = str(self.request_url.absoluteString())
				self.scheme = str(self.request_url.scheme())
				self.handler = None
				self.running = False
				self.cancel = False
				self.successful = False
				self.started = False
				self.terminated = False
				self.error = None
				
			def run(self):
				self.started = True
				self.running = True
				try:
					self.handler(self)
					self.successful = True
				except Exception as e:
					self.error = e
					log.error(f"WKWebView WKURLSchemeTask error processing '{self.url}' {e}")
				finally:
					self.running = False
					self.terminated = True

		class _urlSchemeTaskWorker(threading.Thread):
			def __init__(self, pool):
				super().__init__()
				self.daemon = True
				self.pool = pool
				self.running = False
				self.idle = 0
				self.max_idle = 10
				
			def run(self):
				self.running = True
				while self.running:
					if len(self.pool.queue) > 0:
						self.idle = 0
						task = self.pool.queue.pop()
						task.run()
						del self.pool.tasks[task.id]
					elif self.idle < self.max_idle:
						sleep = time.time()
						time.sleep(0.1)
						sleep = time.time() - sleep
						self.idle = self.idle + sleep
					else:
						break
				self.running = False
				
			def stop(self, join=True):
				self.running = False
				if join:
					self.join()
					
		def __init__(self, handlers):
			self.handlers = handlers
			self.workers = []
			self.queue = []
			self.tasks = {}
			self.max_workers = 4

		def task_start(self, id, task, request):
			pool_task = self._urlSchemeTask(id, task,request)
			pool_task.handler = self.handlers[pool_task.scheme]
			self.tasks[id] = pool_task
			self.queue.append(pool_task)
			task_count = len(self.tasks) + 1
			worker_count = len(self.workers)
			avail = worker_count / task_count
			if avail < 1 and worker_count < self.max_workers:
				worker = self._urlSchemeTaskWorker(self)
				self.workers.append(worker)
				worker.start()
			
		def task_stop(self, id, task, request):
			if not id in self.tasks:
				return
			pool_task = self.tasks[id]
			pool_task.cancel = True
			del self.tasks[id]
	
	
	def webView_startURLSchemeTask_(_self,_cmd,_webview,_task):
		delegate_instance = ObjCInstance(_self)
		webview = delegate_instance._pythonistawebview()
		task_instance = ObjCInstance(_task)
		task_request = task_instance.request()
		webview.url_scheme_task_pool.task_start(_task, task_instance, task_request)
		
	f = webView_startURLSchemeTask_
	f.argtypes = [c_void_p] * 2
	f.restype = None
	f.encoding = b'v@:@@?'

	def webView_stopURLSchemeTask_(_self,_cmd,_webview,_task):
		delegate_instance = ObjCInstance(_self)
		webview = delegate_instance._pythonistawebview()
		task_instance = ObjCInstance(_task)
		task_request = task_instance.request()
		webview.url_scheme_task_pool.task_stop(_task, task_instance, task_request)

	f = webView_stopURLSchemeTask_
	f.argtypes = [c_void_p] * 2
	f.restype = None
	f.encoding = b'v@:@@?'

	# WKURLSchemeHandler - custom url schemes handler for proxying assets
	CustomURLSchemeHandler = create_objc_class(
	 'CustomURLSchemeHandler',
	 superclass=NSObject,
	 methods=[
	  webView_startURLSchemeTask_,
	  webView_stopURLSchemeTask_
	 ],
	 protocols=['WKURLSchemeHandler'])

	
if __name__ == '__main__':
	html = '''
  <html>
  <head>
    <title>WKWebView tests</title>
    <script>
      function initialize() {
      	//alert('init');
        //result = prompt('Initialized', 'Yes, indeed');
        //if (result) {
          //window.webkit.messageHandlers.greeting.postMessage(
          //    result ? result : "<Dialog cancelled>");
        //}
        let wasmer = import("wkwebview://"+encodeURIComponent("https://app.unpkg.com/@wasmer/sdk@latest/files/dist/index.mjs"));
      }
    </script>
  </head>
  <body onload="" style="font-size: xx-large; text-align: center">
    <p>
      Hello world
    </p>
    <p>
      <a href="http://omz-software.com/pythonista/">Pythonista home page</a>
    </p>
    <p>
      +358 40 1234567
    </p>
    <p>
      http://omz-software.com/pythonista/
    </p>
    <img src="wkwebview://image" />-->
    <a href="wkwebview://hello">Custom Scheme</a>
    <script defer type="module">
      initialize();
    </script>
  </body>
  '''

	class MyWebView(WKWebView):

		def on_greeting(self, message):
			console.alert(message,
			              'Message passed to Python',
			              'OK',
			              hide_cancel_button=True)
		
		def scheme_wkwebview(self,task):
			print(f"wkwebview scheme: {task.url}")

	class MyView(ui.View):

		def __init__(self, *args, **kwargs):
			super().__init__(self, *args, **kwargs)
			print("view init")
			self.webview = MyWebView(name='DemoWKWebView',
			                         delegate=self,
			                         swipe_navigation=True,
			                         data_detectors=(WKWebView.PHONE_NUMBER,
			                                         WKWebView.LINK),
			                         frame=self.bounds,
			                         flex='WH')
			self.add_subview(self.webview)
				
			self.webview.load_url('http://omz-software.com/pythonista/',no_cache=False, timeout=5)
			#self.webview.load_html(html)
			#self.webview.load_file('layout.html','views-test/base')
			#self.webview.load_file('views-test/base/layout.html','/')

		def did_load(self):
			print('view load')  # only called when loaded as .pyui

		def will_close(self):
			self.webview.close()  # only called at top level view
			print('view closing')

		def webview_should_start_load(self, webview, url, scheme, nav_type):
			""" See nav_type options at https://developer.apple.com/documentation/webkit/wknavigationtype?language=objc """
			print('Will start loading ', url, scheme, nav_type)
			return True

		def webview_did_start_load(self, webview, url):
			print('Start loading ', url)

		def webview_did_finish_load(self, webview, url):
			print('Finish loading ', url)
			print('Title: ' + str(webview.eval_js('document.title')))

	app = MyView(background_color='black')
	app.present()

