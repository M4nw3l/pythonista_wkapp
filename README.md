# pythonista-wkapp
## WKApp - A modern HTML5 UI framework for building iOS apps with Pythonista 3 and WebKit

WKApp is a modern, lightweight and minimal application framework for developing Python applications with desktop-class HTML 5 user interfaces on Apple iOS devices in the[Pythonista 3 IDE](https://omz-software.com/pythonista/) for iOS.
It provides a simple basis to start creating browser based applications in Pythonista quickly while offering wide customisability capable of developing from simple single page applications through to sophisticated multi-view mobile applications supporting anything you can do in HTML 5 with WebKit support including canvases, browser gaming, media playback, file editing and more. Use any Python libraries from the pip ecosysten that can be installed and supported by Pythonista. And/or use any WebKit/Safafi in browser compatible javascript for client side functionality too. Supporting bi-directional and asyncronous interop between both, Python and JavaScript which can work together to produce compelling experiences. Handling styling of your application and concerns like device orientation, screen size and scaling in the same way as any other responsive website using css's powerful, mature and well known feature set. Web frontend libraries Bootstrap 5, for out of the box responsive styling, and JQuery, to ease, extend and perform DOM manipulation, are bundled to help streamline, and give options focused on rapidly developing apps. Instead of getting lost down areas such as drawing an apps ui more traditionally for example. The whole of the included base app ui templates and static files are however also customiable and replacable too, so these may be overriden, removed or expanded with plugins etc depending on your applications requirements and needs.

### Installation and Quick start
Pip is the recommended installation method for WKApp. 
Install [StaSh](https://github.com/ywangd/stash) for Pythonista 3 using the installation instructions from its README first.
Then install the `pythonista-wkapp` module with pip.
```
pip install pythonista-wkapp
```
To create the basis of an app, simply create the root folder somewhere and add an `app.py` file as follows.

```python

from wkapp import *

app = WKApp(__file__)
app.run()

```

Run this file and you should see a fullscreen browser control and placeholder page shown. You can then just start making your own views straight away with Mako templates!

To create your apps main view simply add a file `views/index.html`.

```html
<%!

class IndexView:
	def test_action(self, text):
		print(text)
		self.eval_js(f"$('header').text(`hello javascript! text was {text}`);") # TODO: replace with better binding 
		

view_class = IndexView

%>

<!-- inherit from the view.html template to render the views content inside the apps customisable base layout and structure -->
<%inherit file="view.html"/>
<!-- Your page content goes here -->
<button onclick="view.invoke('test_action', 'hello python!')">Call Python</button>
<button onclick="app.exit()">Exit Application</button>
<div>
  <h1 id="header">Hello World!</h1>
</div>
```

### Dependencies
WKApp requires the Pythonista 3 app on iOS to run but otherwise uses a minimal set of dependencies:

- [Bottle.py 0.13.4](https://github.com/bottlepy/bottle)
- [Mako 1.13.10](https://github.com/sqlalchemy/mako)
- WKWebView 1.2 (Bundled)
	- 1.2 is a customised extended version which has been updated for WKApp, to implement displaying apps in UIKits WKWebView WebKit browser control. Changes consist mostly of fixes, improvments to reliability, simplifying threading concerns, avoiding/removing the odd crash and deadlock in handling objective-c, python, js interactions here and there and adding a few more helper methods.
	- 1.1 [Gist (@sbbosco)](https://gist.github.com/sbbosco/1290f59d79c6963e62bb678f0f05b035)
	- 1.0 [Github (@mikaelho)](https://github.com/mikaelho/pythonista-webview)

### Bundled Web frontend libraries:
The base app html template bundles with it Bootstrap and JQuery to offer a way to just start developing apps rapidly right away straight out of the box. However if you prefer other frameworks rest assured the `base/app.html` template can be replaced. Its as simple as creating your own version of the template using the same directory structure in your apps views folder. 

- [Bootstrap 5.3.8](https://getbootstrap.com/docs/5.3/getting-started/introduction/)
- [JQuery 3.7.1](https://jquery.com)


