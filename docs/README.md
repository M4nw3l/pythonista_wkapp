# WKApp Pythonista Development Guide

## Contents
- Overview
- Setup
- Views
	- Overview
	- View classes
		- Form data and query string parameter binding
		- Accessing Elements and evaluating JavaScript
		- Lifecycle Events
	- Templates
		- Expresion escaping
- Base application template
	- base/app.html
	- base/layout.html
	- base/view.html
	- app.css
	- app.js
	- view.html
	- index.html


## Overview
WKApp is an application framework for Pythonista to easily create iOS apps with rich desktop-class HTML5 user interfaces completely within Pythonista's environment. It is intended to completely replace the default `ui` library with web based user interface, while also not being too overly restrictive or opinionated about how the app itself is developed otherwise. Providing a minimal infrastructure for creating HTML5 frontend  view templates with interweaved Python for rendering, auto-wireup of Python backend model instances and javascript integration. 

The entire application is displayed using a fullscreen WKWebView WebKit browser control, showing HTML5 views rendered through a Bottle.py http/WSGI server and Mako templating. Aiming to be as simple as possible to get started, requiring only a single pip package with few dependencies to install, and just three lines of code to run and show the app on the screen.

```python
from wkapp import *

app = WKApp(__file__)
app.run()
```

Views are then created in the project by simply adding html file templates inside a `views` root folder and navigated between as normal with interactions such as clicking links, scripted actions and redirection. Mako's templating allows Python alongside any of it its powerful templating syntax to be interweaved into the same HTML files as well as any other served text resources such as CSS and Javascript/TypeScript scripts. Enabling programatic generation and injection of scripts and styles dynamically. 

As views simply end up as Python modules through Mako, a view class can be created inline in a templates module header or assigned to a view template from another module elsewhere. Instances will be created and injected into the template automatically allowing custom variables and state to be stored, accessed and rendered as well as functions which can be called from the page.

View class instances are also combined with a mixin base class which allows page elements to be manipulated as well as general JavaScript evaluation. A straighforward mechanism for Javascript to Python inter-communication is provided, allowing for JavaScript to cross-invoke function calls with arbitrary parameter passing to Python via message handlers and json, alongside full JavaScript access, calling and DOM manipulation capabilities from Python via JavaScript evalution and a loose jQuery wrapping.

## Setup

Getting started is as simple as outlined in the main README.md in the repository root. 
Install [StaSh](https://github.com/ywangd/stash) for Pythonista 3 using the installation instructions from its README first.
Then open a StaSh terminal and install the `pythonista-wkapp` module with pip.
```
pip install pythonista-wkapp # DRAFT package is not published yet!
```
Then to create the basis of an app, simply create the root folder somewhere and add an `app.py` file as follows.

```python
from wkapp import *

app = WKApp(__file__)
app.run()

```
Run this file and you should see a fullscreen browser control and placeholder page shown. 

## Views
### Overview
All HTML5 application views are placed inside a `views` folder relative to the `app.py` file. A base set of templates allow just the views HTML5 content to be written into the views html page template. The surrounding static html structure, headers and footers etc are all handled by the base template found in the pythonista-wkapp modules `views` and `views/base` folders.

The basic structure of a view consists of a view class and a Mako template with mixed HTML, CSS, JavaScript and Python in Mako template syntax as follows, contained in an single .html file.

```python
<%!

class ViewClass:
	def on_init(self):
		self.name = ''
		
	def view_action(self, text, *args):
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
The apps views folder is effectively the `wwwRoot` folder it is shown in combination with the modules views folder such that 
the modules views folder acts as base. WKApp provides default routes to serve templates from the views folder and
static content from `static` folder relative to `app.py`.
Any file template served/rendered from the views folder via default routes or `app.template` is considered a view and can have a backing python class which can be assigned by specifying it as the `view_class` member in the templates module header. Then the first time a view is shown it will be instantiated before rendering and the same instance is then subsequently passed through each time the template is rendered as a template variable named `view`. 

### View classes
View classes are in essence just plain Python classes, which when instantiated are created with a base view class mixin. Providing an element accessors and javascript evalution functions.

- `element('any_jquery_selector')`
- `elements('any_jquery_selector')`
- `eval_js('any_javascript')`

#### Form data and query string parameter binding

Any form values and query string parameters are automatically assigned from the request into in view class instances for both GET and POST if attributes of the same name exist in the Python backend view class. 

### Templates

#### Expressions Escaping
A slighly customised lexer for Mako is used to offer better integration and escaping options for Mako's standard `${}` expression, as JavaScript now too supports this notation. Additionaly adding a `$${}` escaped expression which renders the entire expression as a literal `${}`, as if typed in html/js, and an equivalent alternative expression construct `%{}` which feels like an oversight from Makos general definition consistently using `%` elsewhere for other constructs. A `%%{}` literal escape for `%{}` is additionaly included for completeness. 



