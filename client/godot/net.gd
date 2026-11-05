extends Node
## WebSocket-Verbindung zum Spielserver (Protokoll: docs/VERTICAL_SLICE_PROTOCOL.md). Eine JSON-Nachricht je Text-Nachricht.

signal event(ev: Dictionary)
signal closed

var ws := WebSocketPeer.new()
var char_name := ""
var open := false
var _hello: Dictionary = {}
var _hello_sent := false
var _n := 0
var _pending := {}

func connect_to(url: String, account: String, password: String, register: bool) -> void:
	_hello = {"cmd": "register" if register else "hello", "account": account}
	if password != "":
		_hello["password"] = password
	var err := ws.connect_to_url(url)
	if err != OK:
		push_error("WebSocket: Verbindung nicht möglich (%s)" % error_string(err))

func call_cmd(cmd: String, args: Dictionary = {}, cb: Callable = Callable()) -> void:
	if not open:
		return
	_n += 1
	var id := "c%d" % _n
	var a := args.duplicate()
	a["char"] = char_name
	if cb.is_valid():
		_pending[id] = cb
	ws.send_text(JSON.stringify({"v": 1, "id": id, "cmd": cmd, "args": a}))

func _process(_d: float) -> void:
	ws.poll()
	var st := ws.get_ready_state()
	if st == WebSocketPeer.STATE_OPEN:
		if not _hello_sent:
			_hello_sent = true
			open = true
			ws.send_text(JSON.stringify(_hello))
		while ws.get_available_packet_count() > 0:
			var txt := ws.get_packet().get_string_from_utf8()
			var msg = JSON.parse_string(txt)
			if typeof(msg) != TYPE_DICTIONARY:
				continue
			if msg.has("ev"):
				if msg["ev"] == "welcome" and msg.get("characters", []).size() > 0:
					char_name = msg["characters"][0]
				event.emit(msg)
			elif msg.has("id") and _pending.has(msg["id"]):
				var cb: Callable = _pending[msg["id"]]
				_pending.erase(msg["id"])
				cb.call(msg)
	elif st == WebSocketPeer.STATE_CLOSED and open:
		open = false
		closed.emit()
