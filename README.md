# pythonista-wkapp
## WKApp - A modern HTML5 UI framework for building iOS apps with Pythonista 3 and WebKit

WKApp is a modern, lightweight and minimal application framework for developing Python applications with desktop-class HTML 5 user interfaces on Apple iOS devices in the [Pythonista 3 IDE](https://omz-software.com/pythonista/) for iOS.

It provides a simple basis to start creating browser based applications in Pythonista quickly while offering wide customisability capable of developing from simple single page applications through to sophisticated multi-view mobile applications supporting anything you can do in HTML 5 in a web browser/WebKit.

### Getting started
Pip is the recommended installation method for WKApp. 
Install [StaSh](https://github.com/ywangd/stash) for Pythonista 3 using the installation instructions from its README first.
Then install the `pythonista-wkapp` module with pip.
```
pip install pythonista-wkapp # DRAFT package is not published yet!
```
Then to create the basis of an app, simply create the root folder somewhere and add an `app.py` file as follows.

```python

from wkapp import *

app = WKApp(__file__)
app.run()

```

Run this file and you should see a fullscreen browser control and placeholder page shown. You can then just start making your own views straight away with Mako templates!

To replace the main view / index placeholder simply create a file `views/index.html`, then add your html and setup a `view_class` mixin. An instance is created and maintained automatically for holding state, listening on view lifecycle events and two way interop between python and client-side javascript, providing element/DOM manipulation and wide flexibility to customise view/page behaviour. 

A simple view example:

```html
<%!

class MyFirstView:
	def on_init(self):
		self.name = ''
		
	def test_action(self, text,*args):
		print(text,args)
		self.element('header').set('text',f'hello javascript! text was {text} args were {args}')
		

view_class = MyFirstView

%>

<!-- inherit from the view.html template to render the views content inside the apps customisable base layout and structure -->
<%inherit file="view.html"/>
<!-- Your page content goes here -->
<button onclick="view.invoke('test_action', 'hello python!', 'pass','any','args',{},1,1.5)">Call Python</button>
<button onclick="app.exit()">Exit Application</button>
<div>
  <h1 id="header">Hello World!</h1>
  <form method="POST">
    <label>Enter your name:</label>
    <input name="name" type="text" value="${view.name}" />
    <br />
    <input type="submit" value="Submit" />
  </form>
% if view.name != '': 
    <h2> Hello ${view.name}! </h2>
% endif
</div>
```

### Dependencies
WKApp requires the Pythonista 3 app on iOS to run but otherwise uses a minimal set of dependencies:

- [Bottle.py 0.13.4](https://github.com/bottlepy/bottle)
- [Mako 1.13.10](https://github.com/sqlalchemy/mako)
- pythonista-wkwebview 1.2 (Bundled)
	- 1.2 is an extended version for WKApp, updated with fixes and new features for using the native WKWebView from UIKit on iOS. Including a WKURLSchemeHandler implementation allowing creating custom url schemes with a single handler in a subclass, simplified javascript handlers threading concerns with a Dispatcher, arbitrary arguments passing from javascript to python via json. 
	- 1.1 [Gist (@sbbosco)](https://gist.github.com/sbbosco/1290f59d79c6963e62bb678f0f05b035)
	- 1.0 [Github (@mikaelho)](https://github.com/mikaelho/pythonista-webview)

### Bundled Web frontend libraries:
The base app html template bundles with it Bootstrap and JQuery to offer a way to just start developing apps rapidly right away straight out of the box. However if you prefer other frameworks rest assured the `base/app.html` template can be replaced. Its as simple as creating your own version of the template using the same directory structure in your apps views folder. 

- [Bootstrap 5.3.8](https://getbootstrap.com/docs/5.3/getting-started/introduction/)
- [JQuery 3.7.1](https://jquery.com)


