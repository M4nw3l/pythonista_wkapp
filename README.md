# pythonista-wkapp
## WKApp - A modern HTML5 UI framework for building iOS apps with Pythonista 3 and WebKit

WKApp is a modern, lightweight and minimal application framework for developing Python applications with desktop-class HTML 5 based user interfaces on Apple iOS devices in the [Pythonista 3 IDE](https://omz-software.com/pythonista/) for iOS. 
It is a comprehensive and fully featured alternative to Pythonista's native app `ui` library, allowing user interfaces to be created with standard web technologies. 
Providing a straightforward basis to create web based UI for your Python iOS applications quickly, easily and from entirely within Pythonista. 
Supporting almost anything you can make in a browser with HTML5, CSS, JavaScript even WebAssembly and browser based 2D/3D graphics! 
Using powerful Python templating for dynamic views HTML/CSS/JavaScript rendering with Mako, instanced view state binding supporting arbitarry GET and POST values and, bi-directional interop from Python to JavaScript and JavaScript to Python via JSON over thread-safe browser message handlers. 
Making creating user interfaces for Pythonista based Python Apps as simple as adding a new .html view template file into your projects views folder. Templated application views are then served locally from a Bottle.py HTTP/WSGI server and shown in the bundled WKWebView component.

As Views are just plain HTML5, CSS and JavaScript, high levels of richness and sophistication can be achieved in user interfaces, relatively faster and more robustly, by comparison, due to how versatile and mature web and browser technologies ecosystems are.
WKApp should support almost any html5 markup, css, javascript, libraries, stylesheets, canvases, forms and input components etc that are generally supported by Safari/WebKit. 
WKWebView on iOS is also referenced specifically by the browser compatibility tables in [Mozilla's Docs](https://developer.mozilla.org/en-US/docs/Web) which should be used as the main guidance to determine if a html/css/javascript feature will work in the underlying iOS WKWebView browser component or not. 
jQuery and Bootstrap are bundled into the module embedded default application template to provide for ease of DOM manipulation and a predictable responsive styling scheme out of the box. 
However, Bootstrap may be replaced with another responsive styling / display library if preferred, along with the whole default application template may be overidden too. 
As the default template is meant as only a basic starting point to start with being able to show something on the screen and be customised as desired or wanted. 


## Getting started
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

Run this file and you should see a fullscreen browser control and placeholder page shown. You can then just start making your own views with Mako templates straight away!

To replace the main view / index placeholder: 
- Create a file `views/index.html`, 
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


