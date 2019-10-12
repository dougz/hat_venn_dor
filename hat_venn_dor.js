goog.require('goog.dom');
goog.require('goog.dom.classlist');
goog.require('goog.dom.TagName');
goog.require('goog.events');
goog.require('goog.events.KeyCodes');
goog.require('goog.net.XhrIo');
goog.require("goog.json.Serializer");

class HatVennDorWaiter {
    constructor(dispatcher) {
	/** @type{goog.net.XhrIo} */
	this.xhr = new goog.net.XhrIo();
	/** @type{number} */
	this.serial = 0;
	/** @type{number} */
	this.backoff = 100;

	/** @type{HatVennDorDispatcher} */
	this.dispatcher = dispatcher;
    }

    waitcomplete() {
        if (this.xhr.getStatus() == 401) {
            return;
        }

        if (this.xhr.getStatus() != 200) {
            this.backoff = Math.min(10000, Math.floor(this.backoff*1.5));

	    // XXX cancel early for development
	    //if (this.backoff > 1000) {
	    //console.log("aborting retries");
	    //return;
	    //}

            setTimeout(goog.bind(this.xhr.send, this.xhr, "/hatwait/" + waiter_id + "/" + this.serial),
                       this.backoff);
            return;
        }

        this.backoff = 100;

	var msgs = /** @type{Array<Array<Message|number>>} */ (this.xhr.getResponseJson());
	for (var i = 0; i < msgs.length; ++i) {
	    this.serial = /** @type{number} */ (msgs[i][0]);
	    var msg = /** @type{Message} */ (msgs[i][1]);
	    this.dispatcher.dispatch(msg);
	}

        setTimeout(goog.bind(this.xhr.send, this.xhr,
			     "/hatwait/" + waiter_id + "/" + this.serial),
		   Math.random() * 250);
    }

    start() {
	goog.events.listen(this.xhr, goog.net.EventType.COMPLETE,
			   goog.bind(this.waitcomplete, this));
	this.xhr.send("/hatwait/" + waiter_id + "/" + this.serial);
    }
}

class HatVennDorDispatcher {
    constructor() {
	this.methods = {
	    "show_clue": this.show_clue,
	    "add_chat": this.add_chat,
	}
    }

    /** @param{Message} msg */
    dispatch(msg) {
	this.methods[msg.method](msg);
    }

    /** @param{Message} msg */
    show_clue(msg) {
        hat_venn_dor.entry.style.display = "block";
        hat_venn_dor.clue.style.display = "block";

        hat_venn_dor.clue.innerHTML = msg.html;
    }

    /** @param{Message} msg */
    add_chat(msg) {
	var curr = goog.dom.getChildren(hat_venn_dor.chat);
	if (curr.length > 3) {
	    goog.dom.removeNode(curr[0]);
	}
	var el = goog.dom.createDom("P", null, msg.text + " " + waiter_id);
	hat_venn_dor.chat.appendChild(el);
    }
}

function hat_venn_dor_submit(e) {
    var answer = hat_venn_dor.text.value;
    if (answer == "") return;
    hat_venn_dor.text.value = "";
    var username = hat_venn_dor.who.value;
    localStorage.setItem("name", username);
    var msg = hat_venn_dor.serializer.serialize({"answer": answer, "who": username});
    goog.net.XhrIo.send("/hatsubmit", function(e) {
	var code = e.target.getStatus();
	if (code != 204) {
	    alert(e.target.getResponseText());
	}
    }, "POST", msg);
    e.preventDefault();
}


function hat_venn_dor_onkeydown(e) {
    if (e.keyCode == goog.events.KeyCodes.ENTER) {
	hat_venn_dor_submit(e);
    }
}


var hat_venn_dor = {
    waiter: null,
    entry: null,
    text: null,
    who: null,
    chat: null,
    clue: null,
}

puzzle_init = function() {
    hat_venn_dor.serializer = new goog.json.Serializer();

    hat_venn_dor.body = goog.dom.getElement("puzz");
    hat_venn_dor.entry = goog.dom.getElement("entry");
    hat_venn_dor.text = goog.dom.getElement("text");
    hat_venn_dor.who = goog.dom.getElement("who");
    hat_venn_dor.who.value = localStorage.getItem("name");
    hat_venn_dor.chat = goog.dom.getElement("chat");
    hat_venn_dor.clue = goog.dom.getElement("clue");

    goog.events.listen(goog.dom.getElement("text"),
		       goog.events.EventType.KEYDOWN,
		       hat_venn_dor_onkeydown);
    goog.events.listen(goog.dom.getElement("hatsubmit"),
		       goog.events.EventType.CLICK,
		       hat_venn_dor_submit);

    hat_venn_dor.waiter = new HatVennDorWaiter(new HatVennDorDispatcher());
    hat_venn_dor.waiter.start();
}

