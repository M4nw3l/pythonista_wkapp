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
	
	postCommand(text)
	{
		this.postHandler('command', [text]);
	}
	
	exit() {
		this.postCommand('exit');
	}
}

class WKView {
  constructor(app) {
	}
}

app = new WKApp();
view = new WKView(app);
