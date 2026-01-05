class WKApp {
	constructor() {
	}
		
	#postMessage(name,text)
	{
		window.webkit.messageHandlers[name].postMessage(text);
	}
	
	postCommand(text)
	{
		this.#postMessage('command',text);
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
