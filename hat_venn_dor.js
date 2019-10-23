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
	    "add_chat": goog.bind(this.add_chat, this),
	    "show_clue": goog.bind(this.show_clue, this),
	    "show_answer": goog.bind(this.show_answer, this),
            "venn_state": goog.bind(this.venn_state, this),
            "venn_complete": goog.bind(this.venn_complete, this),
            "center_complete": goog.bind(this.center_complete, this),
	}

        this.have_chunks = false;
        this.transfer = null;
        this.bank = goog.dom.getElement("bank");

        this.targets = document.querySelectorAll("#puzz .target");
        for (var i = 0; i < this.targets.length; ++i) {
            console.log("target", this.targets[i]);
            goog.events.listen(this.targets[i], goog.events.EventType.DRAGOVER,
                               goog.bind(this.on_drag_over, this));
            goog.events.listen(this.targets[i], goog.events.EventType.DROP,
                               goog.bind(this.on_drop, this, i));
            goog.events.listen(this.targets[i], goog.events.EventType.DRAGLEAVE,
                               goog.bind(this.on_drag_leave, this));
        }

        goog.events.listen(this.bank, goog.events.EventType.DRAGOVER,
                           goog.bind(this.on_drag_over, this));
        goog.events.listen(this.bank, goog.events.EventType.DROP,
                           goog.bind(this.on_drop, this, -1));
        goog.events.listen(this.bank, goog.events.EventType.DRAGLEAVE,
                           goog.bind(this.on_drag_leave, this));
    }

    /** @param{Message} msg */
    dispatch(msg) {
	this.methods[msg.method](msg);
    }

    /** @param{Message} msg */
    show_clue(msg) {
        hat_venn_dor.entry.style.display = "initial";
        hat_venn_dor.clue.style.display = "initial";
        hat_venn_dor.clueanswer.style.display = "initial";
        hat_venn_dor.venn.style.display = "none";

        hat_venn_dor.clue.innerHTML = msg.clue;
        hat_venn_dor.clueanswer.innerHTML = "\u00a0";

        this.bank.innerHTML = "";
        this.targets.forEach((el) => { el.innerHTML = ""; });
        this.have_chunks = false;
        this.transfer = null;
    }

    /** @param{Message} msg */
    show_answer(msg) {
        hat_venn_dor.clueanswer.innerHTML = msg.answer;
    }

    on_drag_start(e) {
        e.target.style.opacity = 0.4;
        this.transfer = e.target.id;
    }

    on_drag_end(e) {
        e.target.style.opacity = 1.0;
        this.transfer = null;
    }

    on_drag_leave(e) {
        goog.dom.classlist.remove(e.currentTarget, "drag-in");
    }

    on_drag_over(e) {
        console.log(e.currentTarget);
        if (e.currentTarget.id == "bank" ||
            goog.dom.classlist.contains(e.currentTarget, "target")) {
            goog.dom.classlist.add(e.currentTarget, "drag-in");
            e.preventDefault();
        }
    }

    on_drop(t, e) {
        if (!this.transfer) return;
        e.preventDefault();
        goog.dom.classlist.remove(e.currentTarget, "drag-in");
        var chunk = this.transfer.substr(6);
        var el = goog.dom.getElement(this.transfer);
        el.parentNode.removeChild(el);
        e.currentTarget.appendChild(el);
        el.style.opacity = 1.0;

        var target = e.currentTarget.id;
        if (target == "bank") {
            target = "bank";
        } else {
            target = target.substr(1);
        }

        goog.net.XhrIo.send("/hatplace/" + chunk + "/w" + waiter_id + "/" + target, function(e) {
	    var code = e.target.getStatus();
	    if (code != 204) {
	        alert(e.target.getResponseText());
	    }
        });
    }


    /** @param{Message} data */
    venn_state(data) {
        hat_venn_dor.entry.style.display = "none";
        hat_venn_dor.clue.style.display = "none";
        hat_venn_dor.clueanswer.style.display = "none";
        hat_venn_dor.venn.style.display = "initial";
        hat_venn_dor.t6e.style.display = "none";
        hat_venn_dor.t6a.style.display = "none";

        var chunks;

        if (!this.have_chunks) {
            chunks = data.chunks["w" + waiter_id];
            if (chunks) {
                this.have_chunks = true;
                for (var i = 0; i < chunks.length; ++i) {
                    var el = goog.dom.createDom("SPAN", {className: "chunk mine",
                                                         id: "chunk-" + chunks[i],
                                                         draggable: true}, chunks[i]);
                    this.bank.appendChild(el);
                    goog.events.listen(el, goog.events.EventType.DRAGSTART,
                                       goog.bind(this.on_drag_start, this));
                    goog.events.listen(el, goog.events.EventType.DRAGEND,
                                       goog.bind(this.on_drag_end, this));
                }
            }

            console.log(data);
            hat_venn_dor.words.innerHTML = "";
            for (var i = 0; i < data.words.length; ++i) {
                hat_venn_dor.words.appendChild(
                    goog.dom.createDom("DIV", null, data.words[i]));
            }
        }

        document.querySelectorAll("#puzz .notmine").forEach(
            function(el) { el.parentNode.removeChild(el); });
        for (var t = 0; t < 6; ++t) {
            chunks = data.targets[t];
            var tgt = goog.dom.getElement("t" + t);
            for (var i = 0; i < chunks.length; ++i) {
                var c = chunks[i][0];
                var w = chunks[i][1];
                var el;
                if (w == "w" + waiter_id) {
                    el = goog.dom.getElement("chunk-" + c);
                    el.parentNode.removeChild(el);
                } else {
                    el = goog.dom.createDom("SPAN", "chunk notmine", c);
                }
                tgt.appendChild(el);
            }
        }
    }

    /** @param{Message} data */
    venn_complete(data) {
        hat_venn_dor.t6e.style.display = "initial";
        hat_venn_dor.t6a.style.display = "none";

        document.querySelectorAll("#puzz .chunk").forEach(
            function(el) { el.parentNode.removeChild(el); });

        for (var t = 0; t < 6; ++t) {
            var tgt = goog.dom.getElement("t" + t);
            tgt.innerHTML = data.targets[t];
        }

        hat_venn_dor.t6e.focus();
    }

    /** @param{Message} data */
    center_complete(data) {
        hat_venn_dor.t6e.style.display = "none";
        hat_venn_dor.t6a.style.display = "initial";

        for (var t = 0; t < 6; ++t) {
            var tgt = goog.dom.getElement("t" + t);
            tgt.innerHTML = data.targets[t];
        }
        hat_venn_dor.t6a.innerHTML = data.answer;
    }

    /** @param{Message} msg */
    add_chat(msg) {
	var curr = goog.dom.getChildren(hat_venn_dor.chat);
	if (curr.length > 3) {
	    goog.dom.removeNode(curr[0]);
	}
	var el = goog.dom.createDom("P", null, msg.text);
	hat_venn_dor.chat.appendChild(el);
    }

    /** @param{Message} msg */
    another_function(msg) {
	var curr = goog.dom.getChildren(hat_venn_dor.chat);
	if (curr.length > 3) {
	    goog.dom.removeNode(curr[0]);
	}
	var el = goog.dom.createDom("P", null, msg.text + " " + waiter_id);
	hat_venn_dor.chat.appendChild(el);
    }
}

function hat_venn_dor_submit(textel, e) {
    var answer = textel.value;
    if (answer == "") return;
    textel.value = "";
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

function hat_venn_dor_onkeydown(textel, e) {
    if (e.keyCode == goog.events.KeyCodes.ENTER) {
	hat_venn_dor_submit(textel, e);
    }
}

var hat_venn_dor = {
    waiter: null,
    entry: null,
    text: null,
    who: null,
    chat: null,
    clue: null,
    clueanswer: null,
    venn: null,
    t6e: null,
    t6a: null,
    words: null,
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
    hat_venn_dor.clueanswer = goog.dom.getElement("clueanswer");
    hat_venn_dor.venn = goog.dom.getElement("venn");
    hat_venn_dor.t6e = goog.dom.getElement("t6e");
    hat_venn_dor.t6a = goog.dom.getElement("t6a");
    hat_venn_dor.words = goog.dom.getElement("words");

    goog.events.listen(goog.dom.getElement("text"),
		       goog.events.EventType.KEYDOWN,
		       goog.bind(hat_venn_dor_onkeydown, null, hat_venn_dor.text));
    goog.events.listen(goog.dom.getElement("hatsubmit"),
		       goog.events.EventType.CLICK,
                       goog.bind(hat_venn_dor_submit, null, hat_venn_dor.text));

    goog.events.listen(hat_venn_dor.t6e,
		       goog.events.EventType.KEYDOWN,
		       goog.bind(hat_venn_dor_onkeydown, null, hat_venn_dor.t6e));


    hat_venn_dor.waiter = new HatVennDorWaiter(new HatVennDorDispatcher());
    hat_venn_dor.waiter.start();
}

