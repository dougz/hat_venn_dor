/** @type{?function()} */
var puzzle_init;

/** @type{number} */
var waiter_id;

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
        /** @type{?Object<string, Array<string>>} */
        this.chunks;
        /** @type{?Array<Array<string>>} */
        this.targets;
    }
}
