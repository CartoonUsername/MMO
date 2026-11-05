class_name TerrainView
extends Node3D
## Gelände aus den Kartendaten des Servers (`game.map`): Boden mit Wegen/Matsch (Splat-Textur), Wasser, Felsen, Bäume.
## Nur Darstellung. Begehbarkeit entscheidet der Server.

const TEX := 512
const GROUND_SHADER := """
shader_type spatial;
uniform sampler2D splat : filter_linear, repeat_disable;
uniform vec2 world_size;
varying vec3 wpos;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p){ vec2 i = floor(p); vec2 f = fract(p); f = f*f*(3.0-2.0*f);
	return mix(mix(hash(i), hash(i+vec2(1,0)), f.x), mix(hash(i+vec2(0,1)), hash(i+vec2(1,1)), f.x), f.y); }
float fbm(vec2 p){ float v = 0.0; float a = 0.5; for(int i=0;i<4;i++){ v += a*noise(p); p *= 2.03; a *= 0.5; } return v; }
void vertex(){ wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }
void fragment(){
	vec2 uv = wpos.xz / world_size;
	vec4 s = texture(splat, uv);
	float n = fbm(wpos.xz * 0.22);
	float n2 = noise(wpos.xz * 1.7);
	float edge = (fbm(wpos.xz * 0.9) - 0.5) * 0.35;
	vec3 grass = mix(vec3(0.20, 0.46, 0.13), vec3(0.42, 0.62, 0.20), n);
	grass = mix(grass, vec3(0.55, 0.60, 0.22), smoothstep(0.6, 0.9, fbm(wpos.xz * 0.07)) * 0.5);
	grass *= 0.92 + 0.16 * n2;
	vec3 road = mix(vec3(0.55, 0.45, 0.31), vec3(0.67, 0.57, 0.40), n2);
	vec3 mud = mix(vec3(0.27, 0.19, 0.12), vec3(0.36, 0.26, 0.16), n);
	vec3 bed = mix(vec3(0.10, 0.25, 0.28), vec3(0.18, 0.34, 0.33), n);
	vec3 c = grass;
	c = mix(c, mud, smoothstep(0.45, 0.6, s.g + edge));
	c = mix(c, road, smoothstep(0.45, 0.6, s.r + edge * 0.6));
	c = mix(c, bed, smoothstep(0.4, 0.6, s.b + edge));
	ALBEDO = c;
	ROUGHNESS = 0.95;
}
"""
const WATER_SHADER := """
shader_type spatial;
render_mode blend_mix, depth_draw_opaque, specular_schlick_ggx;
uniform sampler2D splat : filter_linear, repeat_disable;
uniform vec2 world_size;
varying vec3 wpos;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
float noise(vec2 p){ vec2 i = floor(p); vec2 f = fract(p); f = f*f*(3.0-2.0*f);
	return mix(mix(hash(i), hash(i+vec2(1,0)), f.x), mix(hash(i+vec2(0,1)), hash(i+vec2(1,1)), f.x), f.y); }
void vertex(){ wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }
void fragment(){
	vec2 uv = wpos.xz / world_size;
	float w = texture(splat, uv).b;
	float t = TIME;
	float r1 = noise(wpos.xz * 1.3 + vec2(t * 0.35, t * 0.2));
	float r2 = noise(wpos.xz * 2.7 - vec2(t * 0.25, t * 0.4));
	float ripple = (r1 + r2) * 0.5;
	float fres = pow(1.0 - clamp(dot(normalize(NORMAL), normalize(VIEW)), 0.0, 1.0), 3.0);
	vec3 deep = vec3(0.04, 0.22, 0.34);
	vec3 shallow = vec3(0.12, 0.50, 0.58);
	vec3 col = mix(deep, shallow, ripple * 0.7 + fres * 0.3);
	float foam = smoothstep(0.30, 0.50, w) * (1.0 - smoothstep(0.50, 0.66, w));
	foam *= 0.6 + 0.8 * noise(wpos.xz * 3.0 + vec2(t * 0.5, 0.0));
	col = mix(col, vec3(0.92, 0.97, 1.0), clamp(foam, 0.0, 1.0));
	ALBEDO = col;
	ALPHA = smoothstep(0.30, 0.52, w) * (0.80 + 0.15 * fres);
	ROUGHNESS = 0.08;
	METALLIC = 0.0;
	SPECULAR = 0.9;
	NORMAL = normalize(NORMAL + vec3((ripple - 0.5) * 0.25, 0.0, (noise(wpos.xz * 2.1 + t * 0.3) - 0.5) * 0.25));
}
"""

var splat_img: Image
var world_size := Vector2(180, 180)

func build(map: Dictionary, capital: Dictionary) -> void:
	var w := float(map["w"])
	var h := float(map["h"])
	world_size = Vector2(w * G.S, h * G.S)
	_make_splat(map, w, h)
	var tex := ImageTexture.create_from_image(splat_img)
	# Boden: die Welt plus ein großer Rand bis zum Horizont (gleiche Grundfarbe)
	var ground := G.mesh_node(_plane(world_size * 1.0, 64), _ground_mat(tex))
	ground.position = Vector3(world_size.x * 0.5, 0, world_size.y * 0.5)
	ground.name = "Ground"
	add_child(ground)
	var rim := G.mesh_node(_plane(Vector2(2400, 2400), 1), G.mat(Color(0.20, 0.42, 0.14), 1.0))
	rim.position = Vector3(world_size.x * 0.5, -0.04, world_size.y * 0.5)
	add_child(rim)
	var water := G.mesh_node(_plane(world_size, 128), _water_mat(tex))
	water.position = Vector3(world_size.x * 0.5, -0.12, world_size.y * 0.5)
	water.name = "Water"
	water.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	add_child(water)
	_rocks(map)
	_trees(map, capital)
	_bridges(map)

func _plane(size: Vector2, subdiv: int) -> PlaneMesh:
	var pm := PlaneMesh.new()
	pm.size = size
	pm.subdivide_width = subdiv
	pm.subdivide_depth = subdiv
	return pm

func _ground_mat(tex: Texture2D) -> ShaderMaterial:
	var sh := Shader.new()
	sh.code = GROUND_SHADER
	var m := ShaderMaterial.new()
	m.shader = sh
	m.set_shader_parameter("splat", tex)
	m.set_shader_parameter("world_size", world_size)
	return m

func _water_mat(tex: Texture2D) -> ShaderMaterial:
	var sh := Shader.new()
	sh.code = WATER_SHADER
	var m := ShaderMaterial.new()
	m.shader = sh
	m.set_shader_parameter("splat", tex)
	m.set_shader_parameter("world_size", world_size)
	return m

func _make_splat(map: Dictionary, w: float, h: float) -> void:
	splat_img = Image.create(TEX, TEX, false, Image.FORMAT_RGBA8)
	splat_img.fill(Color(0, 0, 0, 1))
	for r in map["regions"]:
		var rc: Array = r["rect"]
		var col := Color(0, 0, 0, 1)
		match r["kind"]:
			"road": col = Color(1, 0, 0, 1)
			"mud": col = Color(0, 1, 0, 1)
			"water": col = Color(0, 0, 1, 1)
			_: continue
		var x0 := int(floor(float(rc[0]) / w * TEX))
		var y0 := int(floor(float(rc[1]) / h * TEX))
		var x1 := int(ceil(float(rc[2]) / w * TEX))
		var y1 := int(ceil(float(rc[3]) / h * TEX))
		splat_img.fill_rect(Rect2i(x0, y0, x1 - x0, y1 - y0), col)

func _kind_at(cm: Vector2) -> Color:
	var px := clampi(int(cm.x / 6000.0 * TEX), 0, TEX - 1)
	var py := clampi(int(cm.y / 6000.0 * TEX), 0, TEX - 1)
	return splat_img.get_pixel(px, py)

func _rocks(map: Dictionary) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	var rock_mesh := SphereMesh.new()
	rock_mesh.radial_segments = 7
	rock_mesh.rings = 4
	for o in map.get("obstacles", []):
		var base: Vector3 = G.p3(o["at"])
		var r: float = float(o["r"]) * G.S
		for i in range(4):
			var n := G.mesh_node(rock_mesh, G.mat(Color(0.46, 0.46, 0.48).lerp(Color(0.30, 0.30, 0.33), rng.randf()), 0.95))
			var s := r * rng.randf_range(0.5, 1.0)
			n.scale = Vector3(s, s * rng.randf_range(0.6, 0.95), s * rng.randf_range(0.8, 1.1))
			n.position = base + Vector3(rng.randf_range(-r, r) * 0.5, s * 0.35, rng.randf_range(-r, r) * 0.5)
			n.rotation.y = rng.randf() * TAU
			add_child(n)

func _trees(map: Dictionary, capital: Dictionary) -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = 42
	var trunk_mesh := CylinderMesh.new()
	trunk_mesh.top_radius = 0.10
	trunk_mesh.bottom_radius = 0.18
	trunk_mesh.height = 1.6
	trunk_mesh.radial_segments = 6
	trunk_mesh.rings = 1
	var cone := CylinderMesh.new()
	cone.top_radius = 0.0
	cone.bottom_radius = 1.0
	cone.height = 1.0
	cone.radial_segments = 7
	cone.rings = 1
	var pts: Array[Transform3D] = []
	var cols: Array[Color] = []
	var cap_c: Vector2 = Vector2(float(capital["center"][0]), float(capital["center"][1])) if not capital.is_empty() else Vector2(-9999, -9999)
	var cap_r: float = float(capital["radius"]) if not capital.is_empty() else 0.0
	var tries := 0
	while pts.size() < 900 and tries < 20000:
		tries += 1
		var cm := Vector2(rng.randf_range(100, 5900), rng.randf_range(100, 5900))
		var k := _kind_at(cm)
		if k.r > 0.1 or k.g > 0.1 or k.b > 0.1:
			continue
		# Nähe zu Wegen, Wasser und Matsch meiden (Unschärfe der Textur)
		var clear := true
		for d in [Vector2(40, 0), Vector2(-40, 0), Vector2(0, 40), Vector2(0, -40), Vector2(90, 90), Vector2(-90, -90)]:
			var kk := _kind_at(cm + d)
			if kk.r > 0.1 or kk.b > 0.1:
				clear = false
				break
		if not clear:
			continue
		if cm.distance_to(cap_c) < cap_r + 260.0 or cm.distance_to(Vector2(500, 500)) < 320.0:
			continue
		var near_rock := false
		for o in map.get("obstacles", []):
			if cm.distance_to(Vector2(float(o["at"][0]), float(o["at"][1]))) < float(o["r"]) + 120.0:
				near_rock = true
				break
		if near_rock:
			continue
		var s := rng.randf_range(0.7, 1.6)
		var t := Transform3D(Basis.from_euler(Vector3(0, rng.randf() * TAU, 0)).scaled(Vector3(s, s * rng.randf_range(0.9, 1.3), s)), G.p3([cm.x, cm.y]))
		pts.append(t)
		var pine := rng.randf() < 0.45
		cols.append(Color(0.13, 0.38, 0.20).lerp(Color(0.05, 0.25, 0.16), rng.randf()) if pine else Color(0.30, 0.55, 0.16).lerp(Color(0.62, 0.62, 0.18), rng.randf() * 0.7))
	# Stamm
	var mm_trunk := MultiMesh.new()
	mm_trunk.transform_format = MultiMesh.TRANSFORM_3D
	mm_trunk.mesh = trunk_mesh
	mm_trunk.instance_count = pts.size()
	# Krone: zwei übereinander gestapelte Kegel je Baum
	var mm_a := MultiMesh.new()
	mm_a.transform_format = MultiMesh.TRANSFORM_3D
	mm_a.use_colors = true
	mm_a.mesh = cone
	mm_a.instance_count = pts.size()
	var mm_b := MultiMesh.new()
	mm_b.transform_format = MultiMesh.TRANSFORM_3D
	mm_b.use_colors = true
	mm_b.mesh = cone
	mm_b.instance_count = pts.size()
	for i in range(pts.size()):
		var t: Transform3D = pts[i]
		var s: float = t.basis.get_scale().x
		mm_trunk.set_instance_transform(i, Transform3D(t.basis, t.origin + Vector3(0, 0.8 * t.basis.get_scale().y, 0)))
		mm_a.set_instance_transform(i, Transform3D(t.basis.scaled(Vector3(1.5, 2.4, 1.5)), t.origin + Vector3(0, 1.0 * t.basis.get_scale().y + 1.0 * s, 0)))
		mm_b.set_instance_transform(i, Transform3D(t.basis.scaled(Vector3(1.1, 2.0, 1.1)), t.origin + Vector3(0, 2.2 * t.basis.get_scale().y + 0.6 * s, 0)))
		mm_a.set_instance_color(i, cols[i])
		mm_b.set_instance_color(i, cols[i].lightened(0.12))
	var vm := StandardMaterial3D.new()
	vm.vertex_color_use_as_albedo = true
	vm.roughness = 0.9
	for pair in [[mm_trunk, G.mat(Color(0.30, 0.20, 0.12))], [mm_a, vm], [mm_b, vm]]:
		var inst := MultiMeshInstance3D.new()
		inst.multimesh = pair[0]
		inst.material_override = pair[1]
		add_child(inst)

func _bridges(map: Dictionary) -> void:
	# Wo ein Weg über Wasser führt, liegen Holzplanken und Geländer darauf.
	var waters: Array = []
	var roads: Array = []
	for r in map["regions"]:
		if r["kind"] == "water":
			waters.append(r["rect"])
		elif r["kind"] == "road":
			roads.append(r["rect"])
	for rd in roads:
		for wt in waters:
			var x0 := maxf(float(rd[0]), float(wt[0]))
			var y0 := maxf(float(rd[1]), float(wt[1]))
			var x1 := minf(float(rd[2]), float(wt[2]))
			var y1 := minf(float(rd[3]), float(wt[3]))
			if x1 - x0 < 20.0 or y1 - y0 < 20.0:
				continue
			var a := G.p3([x0, y0])
			var b := G.p3([x1, y1])
			var size := Vector3(b.x - a.x, 0.25, b.z - a.z)
			var deck := G.mesh_node(BoxMesh.new(), G.mat(Color(0.46, 0.31, 0.18), 0.9), (a + b) * 0.5 + Vector3(0, 0.05, 0))
			deck.scale = size
			add_child(deck)
			# Geländer an den beiden Längsseiten
			var along_x := size.x > size.z
			for side in [-1.0, 1.0]:
				var rail := G.mesh_node(BoxMesh.new(), G.mat(Color(0.35, 0.23, 0.13), 0.9))
				if along_x:
					rail.scale = Vector3(size.x, 0.12, 0.12)
					rail.position = (a + b) * 0.5 + Vector3(0, 0.95, side * (size.z * 0.5 - 0.1))
				else:
					rail.scale = Vector3(0.12, 0.12, size.z)
					rail.position = (a + b) * 0.5 + Vector3(side * (size.x * 0.5 - 0.1), 0.95, 0)
				add_child(rail)
				for k in range(5):
					var post := G.mesh_node(BoxMesh.new(), G.mat(Color(0.35, 0.23, 0.13), 0.9))
					post.scale = Vector3(0.14, 1.0, 0.14)
					var f := (float(k) / 4.0 - 0.5)
					if along_x:
						post.position = (a + b) * 0.5 + Vector3(f * (size.x - 0.3), 0.5, side * (size.z * 0.5 - 0.1))
					else:
						post.position = (a + b) * 0.5 + Vector3(side * (size.x * 0.5 - 0.1), 0.5, f * (size.z - 0.3))
					add_child(post)
