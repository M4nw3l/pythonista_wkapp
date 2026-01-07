class WKApp {
	constructor() {
	}
		
	postHandler(handler, args = [], kwargs = {})
	{
		const message = JSON.stringify({
		  href: window.location.href,
			args: args,
			kwargs: kwargs,
		});
		window.webkit.messageHandlers[handler].postMessage(message);
	}
	
	invoke(context, target, args = [], kwargs = {})
	{
		var type = context.constructor.name;
		this.postHandler('invoke', [type, context, target, args, kwargs]);
	}
	
	exit() {
		this.invoke(this,'exit');
	}
}

class WKView {
	constructor(app) {
		this.app = app;
	}
	
	invoke(name, ...args) {
		this.app.invoke(this, name, args)
	}
}

app = new WKApp();
view = new WKView(app);
