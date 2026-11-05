extends Node3D
## Godot-Client (AP 96, ADR-0082): verbindet sich mit dem Spielserver, baut die Welt aus den Serverdaten auf und zeigt sie.
## Start:  godot --path client/godot -- --url=wss://host/ws --account=anna --password=geheim [--register]
## Screenshots (headless auf GPU):  ... -- --shots=capital,gate:18.5 --out=/pfad
## Bedienung: WASD laufen (relativ zur Kamera), Rechtsklick+Maus drehen, Mausrad zoomen, Q/E drehen.

var args := {}
var terrain: TerrainView
var capital_view: CapitalView
var map_data := {}
var cap_data := {}
var world_ready := false
var me: Node3D
var me_target := Vector3.ZERO
var ents := {}
var sun: DirectionalLight3D
var env: Environment
var cam: Camera3D
var cam_yaw := 0.0
var cam_pitch := deg_to_rad(-38.0)
var cam_dist := 11.0
var cam_focus := Vector3.ZERO
var free_cam := false
var hud_label: Label
var banner_label: Label
var log_label: Label
var log_lines: Array[String] = []
var last_dir := Vector2i.ZERO
var hours := 10.5
var banner_until := 0.0
var shot_queue: Array = []
var shot_out := "/root/shots"
var first_state_at := -1.0
var shot_busy := false
var region_name := ""
var in_capital := false
var elapsed := 0.0

const ENEMY_SCALE := {"bear": 1.5, "alpha_wolf": 1.3, "stone_golem": 2.0, "stone_warden": 2.2, "stone_heart_colossus": 4.0, "wisp_healer": 0.6, "wolf": 0.9}

func _ready() -> void:
	for a in OS.get_cmdline_user_args():
		var kv: PackedStringArray = a.trim_prefix("--").split("=", true, 1)
		args[kv[0]] = kv[1] if kv.size() > 1 else "1"
	hours = float(args.get("time", hours))
	shot_out = String(args.get("out", shot_out))
	if args.has("shots"):
		shot_queue = String(args["shots"]).split(",")
	_setup_environment()
	_setup_camera()
	_setup_hud()
	Net.event.connect(_on_event)
	Net.closed.connect(func(): _banner("Verbindung getrennt", 99999.0))
	Net.connect_to(String(args.get("url", "ws://127.0.0.1:7777/ws")), String(args.get("account", "anna")),
		String(args.get("password", "")), args.has("register"))

# ------------------------------------------------------------------ Umgebung ----
func _setup_environment() -> void:
	var we := WorldEnvironment.new()
	env = Environment.new()
	var sky := Sky.new()
	var psm := ProceduralSkyMaterial.new()
	sky.sky_material = psm
	env.background_mode = Environment.BG_SKY
	env.sky = sky
	env.ambient_light_source = Environment.AMBIENT_SOURCE_SKY
	env.reflected_light_source = Environment.REFLECTION_SOURCE_SKY
	env.tonemap_mode = Environment.TONE_MAPPER_FILMIC
	env.tonemap_white = 6.0
	env.glow_enabled = true
	env.glow_intensity = 0.55
	env.glow_bloom = 0.08
	env.glow_hdr_threshold = 1.3
	env.ssao_enabled = true
	env.ssao_radius = 1.6
	env.ssao_intensity = 2.8
	env.ssil_enabled = false
	env.fog_enabled = true
	env.fog_light_color = Color(0.70, 0.78, 0.88)
	env.fog_density = 0.0016
	env.fog_sky_affect = 0.25
	env.fog_aerial_perspective = 0.12
	env.adjustment_enabled = true
	env.adjustment_saturation = 1.28
	env.adjustment_contrast = 1.12
	we.environment = env
	add_child(we)
	sun = DirectionalLight3D.new()
	sun.shadow_enabled = true
	sun.directional_shadow_mode = DirectionalLight3D.SHADOW_PARALLEL_4_SPLITS
	sun.directional_shadow_max_distance = 140.0
	sun.shadow_bias = 0.04
	sun.shadow_blur = 1.4
	add_child(sun)
	_apply_time()

func _apply_time() -> void:
	var elev := sin((hours - 6.0) / 12.0 * PI)
	var day := clampf(elev * 2.2, 0.0, 1.0)
	var yaw := -100.0 + (hours - 6.0) / 12.0 * 200.0
	var pitch := -(8.0 + maxf(elev, 0.0) * 62.0)
	sun.rotation_degrees = Vector3(pitch, yaw, 0.0)
	var warm := Color(1.0, 0.58, 0.30)
	var noon := Color(1.0, 0.96, 0.88)
	var night := Color(0.45, 0.55, 0.95)
	sun.light_color = (warm.lerp(noon, clampf(elev * 1.7, 0.0, 1.0)) if elev > 0.0 else night)
	sun.light_energy = 2.1 * day + 0.18 * (1.0 - day)
	var psm := (env.sky.sky_material as ProceduralSkyMaterial)
	psm.sky_top_color = Color(0.20, 0.42, 0.80).lerp(Color(0.02, 0.04, 0.14), 1.0 - day)
	psm.sky_horizon_color = Color(0.68, 0.80, 0.92).lerp(Color(0.95, 0.50, 0.30), clampf(1.0 - elev * 2.0, 0.0, 1.0) * day).lerp(Color(0.05, 0.07, 0.18), 1.0 - day)
	psm.ground_horizon_color = psm.sky_horizon_color
	psm.ground_bottom_color = Color(0.22, 0.30, 0.20).lerp(Color(0.02, 0.03, 0.05), 1.0 - day)
	psm.sun_angle_max = 40.0
	env.ambient_light_energy = 0.30 + 0.35 * day
	env.fog_light_color = psm.sky_horizon_color.lerp(Color(0.8, 0.85, 0.9), 0.3)
	env.volumetric_fog_enabled = true
	env.volumetric_fog_density = 0.004 * day
	env.volumetric_fog_albedo = Color(1.0, 0.93, 0.80)
	env.volumetric_fog_length = 90.0

func _setup_camera() -> void:
	cam = Camera3D.new()
	cam.fov = 55.0
	cam.near = 0.1
	cam.far = 1500.0
	cam.current = true
	add_child(cam)

func _setup_hud() -> void:
	var layer := CanvasLayer.new()
	add_child(layer)
	hud_label = Label.new()
	hud_label.position = Vector2(16, 12)
	hud_label.add_theme_font_size_override("font_size", 18)
	hud_label.add_theme_color_override("font_outline_color", Color.BLACK)
	hud_label.add_theme_constant_override("outline_size", 6)
	layer.add_child(hud_label)
	banner_label = Label.new()
	banner_label.set_anchors_preset(Control.PRESET_CENTER_TOP)
	banner_label.position = Vector2(-300, 60)
	banner_label.size = Vector2(600, 60)
	banner_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	banner_label.add_theme_font_size_override("font_size", 34)
	banner_label.add_theme_color_override("font_color", Color(1, 0.93, 0.7))
	banner_label.add_theme_color_override("font_outline_color", Color.BLACK)
	banner_label.add_theme_constant_override("outline_size", 10)
	layer.add_child(banner_label)
	log_label = Label.new()
	log_label.position = Vector2(16, 560)
	log_label.add_theme_font_size_override("font_size", 15)
	log_label.add_theme_color_override("font_outline_color", Color.BLACK)
	log_label.add_theme_constant_override("outline_size", 5)
	layer.add_child(log_label)

func _banner(text: String, secs: float = 3.0) -> void:
	banner_label.text = text
	banner_until = elapsed + secs

func _log(text: String) -> void:
	log_lines.append(text)
	if log_lines.size() > 6:
		log_lines.pop_front()
	log_label.text = "\n".join(log_lines)

# ------------------------------------------------------------------ Verbindung ----
func _on_event(ev: Dictionary) -> void:
	match ev.get("ev", ""):
		"welcome":
			_log("Angemeldet als %s" % Net.char_name)
			Net.call_cmd("game.join", {}, _on_joined)
		"error":
			_banner("Fehler: %s" % str(ev.get("message", ev)), 8.0)
			print("SERVERFEHLER: ", ev)
		"state":
			_on_state(ev)
		"region":
			region_name = String(ev.get("name", ""))
			if not in_capital:
				_banner(region_name, 2.5)
		"capital":
			in_capital = ev.get("state", "") == "enter"
			_banner(("Betreten: %s" % ev.get("name", "")) + (" (sicher)" if ev.get("safe", false) else "") if in_capital else "Verlassen: %s" % ev.get("name", ""), 3.0)
		"fight_start":
			_log("Kampf beginnt gegen %s" % ", ".join(ev.get("opponents", [])))
		"fight_end":
			_log("Kampf vorbei: %s" % str(ev.get("outcome", "")))

func _on_joined(msg: Dictionary) -> void:
	if not msg.get("ok", false):
		_banner("Beitritt fehlgeschlagen: %s" % str(msg.get("error", {}).get("message", "")), 8.0)
		return
	Net.call_cmd("game.map", {}, func(m: Dictionary):
		map_data = m.get("result", {})
		Net.call_cmd("game.capital", {}, func(c: Dictionary):
			cap_data = c.get("result", {}) if c.get("ok", false) else {}
			_build_world()))

func _build_world() -> void:
	terrain = TerrainView.new()
	add_child(terrain)
	terrain.build(map_data, cap_data)
	if not cap_data.is_empty():
		capital_view = CapitalView.new()
		add_child(capital_view)
		capital_view.build(cap_data)
	world_ready = true
	print("WELT FERTIG: Kapitale=", not cap_data.is_empty())

func _make_character(c: Color, label: String, scale_f: float = 1.0, ring: bool = false) -> Node3D:
	var n := Node3D.new()
	var body := CapsuleMesh.new()
	body.radius = 0.34
	body.height = 1.7
	n.add_child(G.mesh_node(body, G.mat(c, 0.7), Vector3(0, 0.85, 0)))
	var head := SphereMesh.new()
	head.radius = 0.25
	head.height = 0.5
	n.add_child(G.mesh_node(head, G.mat(Color(0.94, 0.78, 0.64), 0.7), Vector3(0, 1.92, 0)))
	n.scale = Vector3.ONE * scale_f
	var lab := G.label3d(label, 0.32 / maxf(scale_f, 0.01), Color.WHITE, 26.0)
	lab.position = Vector3(0, 2.55, 0)
	n.add_child(lab)
	if ring:
		var rm := TorusMesh.new()
		rm.inner_radius = 0.55
		rm.outer_radius = 0.7
		var r := G.mesh_node(rm, G.mat(Color(1.0, 0.85, 0.3), 0.3, 0.0, Color(1.0, 0.8, 0.2), 2.5), Vector3(0, 0.05, 0))
		r.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		n.add_child(r)
	return n

# ------------------------------------------------------------------ Zustand ----
func _on_state(st: Dictionary) -> void:
	if not world_ready:
		return
	if first_state_at < 0.0:
		first_state_at = elapsed
	var you: Dictionary = st["you"]
	me_target = G.p3(you["pos"])
	if me == null:
		me = _make_character(Color(0.25, 0.55, 0.95), Net.char_name, 1.0, true)
		me.position = me_target
		add_child(me)
		cam_focus = me_target
	var seen := {}
	for p in st.get("players", []):
		var k := "p:" + String(p["char"])
		seen[k] = true
		_upsert(k, G.p3(p["pos"]), func(): return _make_character(G.hash_color(String(p["char"])), String(p["char"])))
	for e in st.get("enemies", []):
		var k := "e:" + String(e["id"])
		if not e.get("alive", true):
			continue
		seen[k] = true
		var t := String(e["type"])
		_upsert(k, G.p3(e["pos"]), func(): return _make_character(Color(0.78, 0.22, 0.20).lerp(G.hash_color(t, 0.6, 0.7), 0.35), t, float(ENEMY_SCALE.get(t, 1.0))))
	for nd in st.get("nodes", []):
		var k := "n:" + String(nd["id"])
		seen[k] = true
		_upsert(k, G.p3(nd["pos"]), func():
			var gem := G.mesh_node(SphereMesh.new(), G.mat(Color(0.4, 0.9, 0.9), 0.2, 0.0, Color(0.3, 0.9, 1.0), 2.5), Vector3(0, 0.6, 0))
			gem.scale = Vector3(0.35, 0.6, 0.35)
			var holder := Node3D.new()
			holder.add_child(gem)
			var l := G.label3d(String(nd["item"]), 0.3, Color(0.7, 1, 1))
			l.position = Vector3(0, 1.4, 0)
			holder.add_child(l)
			return holder)
	for k in ents.keys():
		if not seen.has(k):
			ents[k]["node"].queue_free()
			ents.erase(k)

func _upsert(key: String, pos: Vector3, factory: Callable) -> void:
	if not ents.has(key):
		var n: Node3D = factory.call()
		n.position = pos
		add_child(n)
		ents[key] = {"node": n, "target": pos}
	else:
		ents[key]["target"] = pos

# ------------------------------------------------------------------ Bild ----
func _process(delta: float) -> void:
	elapsed += delta
	if banner_until > 0.0 and elapsed > banner_until:
		banner_label.text = ""
		banner_until = 0.0
	var k := 1.0 - exp(-12.0 * delta)
	for key in ents:
		var n: Node3D = ents[key]["node"]
		var t: Vector3 = ents[key]["target"]
		var d := t - n.position
		if d.length() > 0.02:
			n.rotation.y = lerp_angle(n.rotation.y, atan2(d.x, d.z), k)
		n.position = n.position.lerp(t, k)
	if me != null:
		var d2 := me_target - me.position
		if d2.length() > 0.02:
			me.rotation.y = lerp_angle(me.rotation.y, atan2(d2.x, d2.z), k)
		me.position = me.position.lerp(me_target, k)
		if not free_cam:
			cam_focus = cam_focus.lerp(me.position + Vector3(0, 1.2, 0), 1.0 - exp(-8.0 * delta))
	if not free_cam:
		var off := Vector3(0, 0, cam_dist).rotated(Vector3.RIGHT, cam_pitch).rotated(Vector3.UP, cam_yaw)
		cam.position = cam_focus + off
		cam.look_at(cam_focus, Vector3.UP)
	_input_move()
	_update_hud()
	_run_shots()

func _input_move() -> void:
	if not world_ready or not Net.open:
		return
	var f := 0.0
	var s := 0.0
	if Input.is_physical_key_pressed(KEY_W): f += 1.0
	if Input.is_physical_key_pressed(KEY_S): f -= 1.0
	if Input.is_physical_key_pressed(KEY_D): s += 1.0
	if Input.is_physical_key_pressed(KEY_A): s -= 1.0
	if Input.is_physical_key_pressed(KEY_Q): cam_yaw += 0.03
	if Input.is_physical_key_pressed(KEY_E): cam_yaw -= 0.03
	var dir := Vector2i.ZERO
	if f != 0.0 or s != 0.0:
		# Kamera blickt entlang -Z (gedreht um cam_yaw); Eingabe in Weltrichtung umrechnen und auf 8 Richtungen runden
		var v := Vector3(s, 0, -f).rotated(Vector3.UP, cam_yaw)
		var ang := atan2(v.z, v.x)
		var step := int(round(ang / (PI / 4.0)))
		var a := float(step) * PI / 4.0
		dir = Vector2i(int(round(cos(a))), int(round(sin(a))))
	if dir != last_dir:
		last_dir = dir
		Net.call_cmd("game.move", {"dx": dir.x, "dy": dir.y})

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.is_mouse_button_pressed(MOUSE_BUTTON_RIGHT):
		cam_yaw -= event.relative.x * 0.006
		cam_pitch = clampf(cam_pitch - event.relative.y * 0.004, deg_to_rad(-80.0), deg_to_rad(-8.0))
	elif event is InputEventMouseButton and event.pressed:
		if event.button_index == MOUSE_BUTTON_WHEEL_UP:
			cam_dist = clampf(cam_dist - 0.8, 3.0, 40.0)
		elif event.button_index == MOUSE_BUTTON_WHEEL_DOWN:
			cam_dist = clampf(cam_dist + 0.8, 3.0, 40.0)

func _update_hud() -> void:
	var where := region_name
	if in_capital:
		where = "Hauptstadt (sicher)"
	hud_label.text = "%s   |   %s   |   %02d:%02d   |   %d FPS" % [Net.char_name, where, int(hours), int((hours - floor(hours)) * 60.0), Engine.get_frames_per_second()]

# ------------------------------------------------------------------ Screenshot-Modus ----
func _shot_pose(preset: String) -> Array:
	var c: Vector3 = capital_view.center if capital_view != null else Vector3(87, 0, 39)
	match preset:
		"capital": return [c + Vector3(-2, 22, 31), c + Vector3(0, 1.0, -1.0)]
		"capital_high": return [c + Vector3(0, 48, 40), c]
		"gate": return [c + Vector3(-26, 5.5, 31.0), c + Vector3(-15.0, 3.0, 20.5)]
		"market": return [c + Vector3(1.0, 3.2, 9.5), c + Vector3(0, 1.6, 1.0)]
		"rathaus": return [c + Vector3(0.5, 7.0, 4.0), c + Vector3(0, 3.6, -8.2)]
		"hall": return [c + Vector3(15, 6.0, -3.0), c + Vector3(9.0, 3.5, -7.0)]
		"world": return [Vector3(90, 160, 215), Vector3(90, 0, 70)]
		"bridge": return [Vector3(48, 6, 63), Vector3(54, 0.5, 54)]
		_: return [cam.position, cam_focus]

func _run_shots() -> void:
	if shot_busy or shot_queue.is_empty() or not world_ready or first_state_at < 0.0 or elapsed - first_state_at < 3.0:
		return
	shot_busy = true
	var spec := String(shot_queue.pop_front())
	var parts := spec.split(":")
	if parts.size() > 1:
		hours = float(parts[1])
		_apply_time()
	var pose := _shot_pose(parts[0])
	free_cam = true
	cam.position = pose[0]
	cam.look_at(pose[1], Vector3.UP)
	_save_shot.call_deferred(parts[0] + ("_" + parts[1] if parts.size() > 1 else ""))

func _save_shot(tag: String) -> void:
	await get_tree().create_timer(0.8).timeout
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(shot_out)
	var img := get_viewport().get_texture().get_image()
	var path := "%s/%s.png" % [shot_out, tag]
	img.save_png(path)
	print("SCREENSHOT ", path)
	shot_busy = false
	if shot_queue.is_empty():
		get_tree().quit()
