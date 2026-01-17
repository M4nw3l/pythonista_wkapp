# pythonista-wkapp
## WKApp - A modern HTML5 UI framework for building iOS apps with Pythonista 3 and WebKit

WKApp is a modern, lightweight and minimal application framework for developing Python applications with desktop-class HTML 5 based user interfaces on Apple iOS devices in the [Pythonista 3 IDE](https://omz-software.com/pythonista/) for iOS. 
It is a comprehensive and fully featured alternative to Pythonista's native app `ui` library, allowing user interfaces to be created with standard web technologies. Using powerful Python templating for dynamic HTML5/CSS/JavaScript views rendering with Mako, simple instanced view state binding supporting auto-wiring GET/POST values and two way Python/JavaScript interop via JSON over thread-safe message handlers. 

Creating user interfaces for Python Apps in Pythonista becomes as simple as adding new .html view template files into your project. Which are then served locally from a Bottle.py HTTP/WSGI server and shown in a native WKWebView browser component. WKApp supports creating user interfaces with anything supported by modern web browsers using HTML5, CSS, JavaScript or even WebAssembly and browser based 2D/3D graphics! 


## Getting started
Pip is the recommended installation method for WKApp. 
Install [StaSh](https://github.com/ywangd/stash) for Pythonista 3 using the installation instructions from its README first.
Then install the `pythonista-wkapp` module with pip.
```
pip install pythonista-wkapp # DRAFT package is not published yet!
```
To create an app, simply add a folder somewhere containing an `app.py` file as follows.

```python

from wkapp import *

app = WKApp(__file__)
app.run()

```

Run this file and you should see a fullscreen browser control and the main view index.html placeholder page shown. 
You can then start making your own views straight away!

To replace the initial main view / index.html placeholder page: 
- Create a `views` folder in the same folder as your `app.py` file.
- Create a file `views/index.html`.
- Then add your html and setup a `view_class` mixin definition like as below. 
	- An instance of this class will be maintained with your view which can be used to store state, bind/manipulate elements, provide functions to be called from Javascript and evaluate Javascript from Python in the view to inspect and alter the DOM or backend state.

A simple `views/index.html` view example:

```python
<%!

class ViewClass:
	def on_init(self):
		self.name = ''
		
	def view_action(self, text,*args):
		print(text,args)
		self.element('header').set('text',f'hello javascript! text was {text} args were {args}')
		

view_class = ViewClass

%>
```
```html
<!-- inherit from the view.html template to render the views content inside the apps customisable base layout and structure -->
<%inherit file="view.html"/>
<!-- Your page content goes here -->
<script type="text/javascript">
  function invoke_view_action() {
  	view.invoke('view_action', 'hello python!', 
      {pass:'any',json:['compatible'], args:{ints:1}, floats:0.5},
      ['lists',{},1,2.2],
      'strings',
      'numbers',1,1.5
    );
  }
</script>
<button onclick="invoke_view_action()">Call Python</button>
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
Note: Code above is one file, it is just shown in two parts here for code highlighting purposes.

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


