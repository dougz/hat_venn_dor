/** @type{?function()} */
var puzzle_init;

/** @type{number} */
var wid;

/** @type{Storage} */
var localStorage;

class Message {
    constructor() {
	/** @type{string} */
	this.method;
	/** @type{?string} */
	this.text;
	/** @type{?string} */
	this.clue;
	/** @type{?string} */
	this.answer;
        /** @type{?Object<string, Array<string>>} */
        this.chunks;
        /** @type{?Array<Array<Array<string>>>} */
        this.targets;
        /** @type{?Array<string>} */
        this.words;
    }
}
