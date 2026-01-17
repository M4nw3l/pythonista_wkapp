__version__ = '0.0.1'

from .WKWebView import *
from .WKApp import *

# mostly convenience includes for bottle
# besides its implementation specific includes for the mako templating integration
from bottle import (
 request,
 response,
 route,
 static_file,
)

