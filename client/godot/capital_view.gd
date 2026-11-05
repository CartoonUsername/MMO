class_name CapitalView
extends Node3D
## Die Hauptstadt aus `game.capital`: Plaza, Stadtmauer mit Toren, Gebäude je Viertel, Fackeln, NPCs. Nur Darstellung.

const STYLE := {
	"marktplatz": {"wall": Color(0.88, 0.80, 0.62), "roof": Color(0.80, 0.25, 0.20), "h": 2.6, "kind": "market"},
	"handwerksviertel": {"wall": Color(0.62, 0.52, 0.45), "roof": Color(0.30, 0.30, 0.34), "h": 4.2, "kind": "smithy"},
	"gildenhalle": {"wall": Color(0.80, 0.78, 0.74), "roof": Color(0.18, 0.28, 0.55), "h": 6.0, "kind": "hall"},
	"rathaus": {"wall": Color(0.90, 0.88, 0.82), "roof": Color(0.20, 0.45, 0.40), "h": 7.0, "kind": "tower"},
	"kontor": {"wall": Color(0.72, 0.60, 0.42), "roof": Color(0.50, 0.30, 0.16), "h": 4.6, "kind": "house"},
}
const STONE := Color(0.60, 0.58, 0.55)
const COBBLE_SHADER := """
shader_type spatial;
varying vec3 wpos;
float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }
void vertex(){ wpos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz; }
void fragment(){
	vec2 p = wpos.xz * 1.6;
	float row = floor(p.y);
	p.x += mod(row, 2.0) * 0.5;
	vec2 id = floor(p);
	vec2 f = fract(p);
	float joint = smoothstep(0.0, 0.07, min(min(f.x, 1.0 - f.x), min(f.y, 1.0 - f.y)));
	float h = hash(id);
	vec3 stone = mix(vec3(0.46, 0.43, 0.38), vec3(0.62, 0.58, 0.50), h);
	stone *= 0.9 + 0.2 * hash(id + 7.0);
	ALBEDO = mix(vec3(0.16, 0.14, 0.12), stone, joint);
	ROUGHNESS = 0.92;
}
"""

var center := Vector3.ZERO
var radius := 16.5

func build(cap: Dictionary) -> void:
	center = G.p3(cap["center"])
	radius = float(cap["radius"]) * G.S
	name = "Capital"
	_plaza()
	_wall(cap)
	for d in cap["districts"]:
		_district(d)
	for g in cap["gates"]:
		_gate(g, cap)
	for n in cap["npcs"]:
		_npc(n)
	var title := G.label3d(String(cap["name"]).to_upper(), 1.3, Color(1.0, 0.93, 0.7))
	title.position = center + Vector3(0, 12.0, 0)
	add_child(title)

func _plaza() -> void:
	var disc := CylinderMesh.new()
	disc.top_radius = radius
	disc.bottom_radius = radius
	disc.height = 0.08
	disc.radial_segments = 64
	var sh := Shader.new()
	sh.code = COBBLE_SHADER
	var cob := ShaderMaterial.new()
	cob.shader = sh
	add_child(G.mesh_node(disc, cob, center + Vector3(0, 0.04, 0)))
	var inner := CylinderMesh.new()
	inner.top_radius = radius * 0.22
	inner.bottom_radius = radius * 0.22
	inner.height = 0.14
	inner.radial_segments = 40
	add_child(G.mesh_node(inner, cob, center + Vector3(0, 0.07, 0)))
	# Brunnen
	var basin := CylinderMesh.new()
	basin.top_radius = 1.9
	basin.bottom_radius = 2.1
	basin.height = 0.7
	basin.radial_segments = 20
	add_child(G.mesh_node(basin, G.mat(STONE, 0.8), center + Vector3(0, 0.45, 0)))
	var pool := CylinderMesh.new()
	pool.top_radius = 1.65
	pool.bottom_radius = 1.65
	pool.height = 0.05
	pool.radial_segments = 20
	add_child(G.mesh_node(pool, G.mat(Color(0.2, 0.55, 0.75), 0.05, 0.0, Color(0.1, 0.4, 0.6), 0.4), center + Vector3(0, 0.78, 0)))
	var col := CylinderMesh.new()
	col.top_radius = 0.22
	col.bottom_radius = 0.32
	col.height = 1.8
	col.radial_segments = 10
	add_child(G.mesh_node(col, G.mat(STONE, 0.8), center + Vector3(0, 1.5, 0)))
	var top := SphereMesh.new()
	top.radius = 0.5
	top.height = 0.7
	add_child(G.mesh_node(top, G.mat(STONE.lightened(0.1), 0.7), center + Vector3(0, 2.6, 0)))

func _wall(cap: Dictionary) -> void:
	var gate_angles: Array[float] = []
	for g in cap["gates"]:
		var d: Vector3 = G.p3(g["at"]) - center
		gate_angles.append(atan2(d.z, d.x))
	var segs := 56
	var seg_len := TAU * radius / float(segs)
	var stone := G.mat(Color(0.66, 0.63, 0.58), 0.95)
	var cap_mat := G.mat(Color(0.50, 0.48, 0.45), 0.95)
	for i in range(segs):
		var a := TAU * (float(i) + 0.5) / float(segs)
		var skip := false
		for ga in gate_angles:
			if absf(wrapf(a - ga, -PI, PI)) < 0.13:
				skip = true
				break
		if skip:
			continue
		var pos := center + Vector3(cos(a), 0, sin(a)) * radius
		var wall := G.mesh_node(BoxMesh.new(), stone, pos + Vector3(0, 1.4, 0))
		wall.scale = Vector3(0.9, 2.8, seg_len * 1.08)
		wall.rotation.y = -a
		add_child(wall)
		var top := G.mesh_node(BoxMesh.new(), cap_mat, pos + Vector3(0, 2.95, 0))
		top.scale = Vector3(1.2, 0.3, seg_len * 1.08)
		top.rotation.y = -a
		add_child(top)
		if i % 4 == 0:
			var tower := CylinderMesh.new()
			tower.top_radius = 1.15
			tower.bottom_radius = 1.35
			tower.height = 4.6
			tower.radial_segments = 10
			add_child(G.mesh_node(tower, stone, pos + Vector3(0, 2.3, 0)))
			var roof := CylinderMesh.new()
			roof.top_radius = 0.0
			roof.bottom_radius = 1.6
			roof.height = 1.8
			roof.radial_segments = 10
			add_child(G.mesh_node(roof, G.mat(Color(0.55, 0.20, 0.17), 0.8), pos + Vector3(0, 5.5, 0)))

func _district(d: Dictionary) -> void:
	var st: Dictionary = STYLE.get(d["id"], STYLE["kontor"])
	var rc: Array = d["rect"]
	var a := G.p3([rc[0], rc[1]])
	var b := G.p3([rc[2], rc[3]])
	var mid := (a + b) * 0.5
	var size := Vector2(b.x - a.x, b.z - a.z)
	var h: float = st["h"]
	# Gebäude schaut zur Stadtmitte
	var to_center := center - mid
	var yaw := atan2(to_center.x, to_center.z)
	var root := Node3D.new()
	root.position = mid
	root.rotation.y = yaw
	root.name = String(d["id"])
	add_child(root)
	var wall_mat := G.mat(st["wall"], 0.9)
	var roof_mat := G.mat(st["roof"], 0.75)
	var wood := G.mat(Color(0.35, 0.22, 0.12), 0.9)
	var kind: String = st["kind"]
	var model_path := "res://assets/models/%s.glb" % String(d["id"])
	if ResourceLoader.exists(model_path):
		h = _place_model(root, model_path, Vector2(size.x * 0.9, size.y * 0.9))
		kind = "model"
	elif kind == "market":
		for i in range(6):
			var ang := TAU * float(i) / 6.0
			var p := Vector3(cos(ang) * size.x * 0.40, 0, sin(ang) * size.y * 0.40)
			_stall(root, p, ang, i)
	else:
		var w := size.x * 0.62
		var dpt := size.y * 0.55
		var body := G.mesh_node(BoxMesh.new(), wall_mat, Vector3(0, h * 0.5, 0))
		body.scale = Vector3(w, h, dpt)
		root.add_child(body)
		var prism := PrismMesh.new()
		prism.left_to_right = 0.5
		var roof := G.mesh_node(prism, roof_mat, Vector3(0, h + h * 0.22, 0))
		roof.scale = Vector3(w * 1.14, h * 0.44, dpt * 1.14)
		root.add_child(roof)
		# Fachwerk-Balken an der Vorderseite
		for k in range(-2, 3):
			var beam := G.mesh_node(BoxMesh.new(), wood, Vector3(float(k) * w * 0.22, h * 0.5, dpt * 0.5 + 0.02))
			beam.scale = Vector3(0.22, h, 0.12)
			root.add_child(beam)
		# Tür und beleuchtete Fenster
		var door := G.mesh_node(BoxMesh.new(), G.mat(Color(0.22, 0.13, 0.08), 0.8), Vector3(0, 1.25, dpt * 0.5 + 0.05))
		door.scale = Vector3(1.5, 2.5, 0.14)
		root.add_child(door)
		for k in [-1, 1]:
			var win := G.mesh_node(BoxMesh.new(), G.mat(Color(0.95, 0.80, 0.45), 0.4, 0.0, Color(1.0, 0.75, 0.3), 1.6), Vector3(float(k) * w * 0.31, h * 0.58, dpt * 0.5 + 0.06))
			win.scale = Vector3(1.0, 1.2, 0.1)
			root.add_child(win)
		if kind == "smithy":
			var chim := G.mesh_node(BoxMesh.new(), G.mat(Color(0.40, 0.36, 0.34), 0.95), Vector3(w * 0.3, h + 1.6, -dpt * 0.2))
			chim.scale = Vector3(0.9, 3.0, 0.9)
			root.add_child(chim)
			var fire := OmniLight3D.new()
			fire.light_color = Color(1.0, 0.55, 0.2)
			fire.light_energy = 1.6
			fire.omni_range = 7.0
			fire.position = Vector3(0, 1.6, dpt * 0.5 + 1.0)
			root.add_child(fire)
			var anvil := G.mesh_node(BoxMesh.new(), G.mat(Color(0.18, 0.18, 0.2), 0.5, 0.8), Vector3(-w * 0.3, 0.45, dpt * 0.5 + 1.3))
			anvil.scale = Vector3(0.9, 0.9, 0.5)
			root.add_child(anvil)
		elif kind == "tower":
			var tw := CylinderMesh.new()
			tw.top_radius = 1.4
			tw.bottom_radius = 1.7
			tw.height = h + 4.0
			tw.radial_segments = 12
			root.add_child(G.mesh_node(tw, wall_mat, Vector3(w * 0.38, (h + 4.0) * 0.5, -dpt * 0.2)))
			var tr := CylinderMesh.new()
			tr.top_radius = 0.0
			tr.bottom_radius = 2.1
			tr.height = 3.4
			tr.radial_segments = 12
			root.add_child(G.mesh_node(tr, roof_mat, Vector3(w * 0.38, h + 4.0 + 1.7, -dpt * 0.2)))
			var clock := G.mesh_node(CylinderMesh.new(), G.mat(Color(0.95, 0.92, 0.8), 0.5, 0.0, Color(1, 0.9, 0.6), 0.5), Vector3(w * 0.38, h + 1.4, -dpt * 0.2 + 1.45))
			(clock.mesh as CylinderMesh).top_radius = 0.7
			(clock.mesh as CylinderMesh).bottom_radius = 0.7
			(clock.mesh as CylinderMesh).height = 0.1
			clock.rotation.x = PI * 0.5
			root.add_child(clock)
		elif kind == "hall":
			for k in [-1, 1]:
				var banner := G.mesh_node(BoxMesh.new(), G.mat(Color(0.75, 0.15, 0.18), 0.9), Vector3(float(k) * w * 0.5, h * 0.62, dpt * 0.5 + 0.1))
				banner.scale = Vector3(0.9, 3.0, 0.06)
				root.add_child(banner)
			for k in range(-2, 3):
				var pillar := CylinderMesh.new()
				pillar.top_radius = 0.28
				pillar.bottom_radius = 0.32
				pillar.height = 3.2
				pillar.radial_segments = 8
				root.add_child(G.mesh_node(pillar, G.mat(Color(0.82, 0.80, 0.76), 0.8), Vector3(float(k) * w * 0.22, 1.6, dpt * 0.5 + 1.1)))
			var porch := G.mesh_node(BoxMesh.new(), G.mat(Color(0.70, 0.68, 0.64), 0.9), Vector3(0, 3.3, dpt * 0.5 + 1.1))
			porch.scale = Vector3(w * 0.98, 0.3, 2.4)
			root.add_child(porch)
	# Schild über dem Eingang
	var lab := G.label3d(String(d["name"]), 0.5, Color(1, 0.95, 0.8), 30.0)
	lab.position = Vector3(0, h + (h * 0.5 if kind == "house" or kind == "smithy" or kind == "hall" or kind == "tower" else (1.6 if kind == "model" else 2.4)), 0)
	root.add_child(lab)

func _stall(root: Node3D, p: Vector3, ang: float, i: int) -> void:
	var s := Node3D.new()
	s.position = p
	s.rotation.y = -ang + PI * 0.5
	root.add_child(s)
	var table := G.mesh_node(BoxMesh.new(), G.mat(Color(0.40, 0.27, 0.15), 0.9), Vector3(0, 0.55, 0))
	table.scale = Vector3(2.2, 1.1, 1.0)
	s.add_child(table)
	for sx in [-1.0, 1.0]:
		var pole := G.mesh_node(BoxMesh.new(), G.mat(Color(0.32, 0.20, 0.11), 0.9), Vector3(sx * 1.1, 1.3, -0.5))
		pole.scale = Vector3(0.12, 2.6, 0.12)
		s.add_child(pole)
	var colors := [Color(0.82, 0.22, 0.20), Color(0.22, 0.45, 0.78), Color(0.88, 0.72, 0.18)]
	var awn := G.mesh_node(BoxMesh.new(), G.mat(colors[i % 3], 0.85), Vector3(0, 2.55, -0.2))
	awn.scale = Vector3(2.7, 0.12, 1.7)
	awn.rotation.x = 0.18
	s.add_child(awn)
	var goods := [Color(0.85, 0.2, 0.15), Color(0.9, 0.7, 0.2), Color(0.35, 0.6, 0.25)]
	for k in range(3):
		var g := G.mesh_node(SphereMesh.new(), G.mat(goods[(i + k) % 3], 0.6), Vector3(-0.7 + 0.7 * float(k), 1.3, 0.05))
		g.scale = Vector3(0.36, 0.36, 0.36)
		s.add_child(g)

func _gate(g: Dictionary, cap: Dictionary) -> void:
	var pos: Vector3 = G.p3(g["at"])
	var out := (pos - center)
	out.y = 0.0
	var yaw := atan2(out.x, out.z)
	var root := Node3D.new()
	root.position = pos
	root.rotation.y = yaw
	root.name = "Tor_" + String(g["id"])
	add_child(root)
	var stone := G.mat(Color(0.62, 0.60, 0.57), 0.9)
	for sx in [-1.0, 1.0]:
		var pillar := G.mesh_node(BoxMesh.new(), stone, Vector3(sx * 2.2, 2.6, 0))
		pillar.scale = Vector3(1.5, 5.2, 1.7)
		root.add_child(pillar)
		var cap_ := G.mesh_node(BoxMesh.new(), G.mat(Color(0.48, 0.46, 0.43), 0.9), Vector3(sx * 2.2, 5.35, 0))
		cap_.scale = Vector3(1.9, 0.4, 2.1)
		root.add_child(cap_)
		# Fackel
		var torch := G.mesh_node(SphereMesh.new(), G.mat(Color(1.0, 0.65, 0.2), 0.4, 0.0, Color(1.0, 0.55, 0.15), 4.0), Vector3(sx * 2.2, 3.4, 1.05))
		torch.scale = Vector3(0.22, 0.34, 0.22)
		root.add_child(torch)
		var light := OmniLight3D.new()
		light.light_color = Color(1.0, 0.6, 0.25)
		light.light_energy = 2.2
		light.omni_range = 9.0
		light.position = Vector3(sx * 2.2, 3.5, 1.4)
		root.add_child(light)
	var lintel := G.mesh_node(BoxMesh.new(), stone, Vector3(0, 5.0, 0))
	lintel.scale = Vector3(6.4, 1.1, 1.7)
	root.add_child(lintel)
	# Wappenbanner
	var banner := G.mesh_node(BoxMesh.new(), G.mat(Color(0.70, 0.14, 0.16), 0.9), Vector3(0, 3.7, 0.92))
	banner.scale = Vector3(1.2, 2.2, 0.05)
	root.add_child(banner)
	var lab := G.label3d(String(g["name"]), 0.55, Color(1, 0.93, 0.7), 34.0)
	lab.position = Vector3(0, 7.2, 0)
	root.add_child(lab)

func _npc(n: Dictionary) -> void:
	var pos: Vector3 = G.p3(n["at"])
	var root := Node3D.new()
	root.position = pos
	root.name = "NPC_" + String(n["id"])
	add_child(root)
	var c := G.hash_color(String(n["id"]), 0.45, 0.8)
	var body := CapsuleMesh.new()
	body.radius = 0.32
	body.height = 1.7
	root.add_child(G.mesh_node(body, G.mat(c, 0.8), Vector3(0, 0.85, 0)))
	var head := SphereMesh.new()
	head.radius = 0.24
	head.height = 0.48
	root.add_child(G.mesh_node(head, G.mat(Color(0.93, 0.76, 0.62), 0.8), Vector3(0, 1.85, 0)))
	var mark := G.mesh_node(PrismMesh.new(), G.mat(Color(1.0, 0.85, 0.2), 0.3, 0.0, Color(1.0, 0.8, 0.1), 2.0), Vector3(0, 2.9, 0))
	mark.scale = Vector3(0.4, 0.5, 0.2)
	mark.rotation.z = PI
	root.add_child(mark)
	var lab := G.label3d("%s\n%s" % [n["name"], n["role"]], 0.30, Color(0.85, 1.0, 0.85), 14.0)
	lab.position = Vector3(0, 3.5, 0)
	root.add_child(lab)

## Lädt ein Modell (GLB) und stellt es auf den Boden, passend skaliert in die Fläche `fit` (Meter). Vorderseite = +Z.
## Gibt die Höhe des Modells nach der Skalierung zurück.
func _place_model(root: Node3D, path: String, fit: Vector2) -> float:
	var scene := load(path) as PackedScene
	var inst := scene.instantiate() as Node3D
	var box := _aabb_of(inst)
	var sc := minf(fit.x / maxf(box.size.x, 0.001), fit.y / maxf(box.size.z, 0.001))
	var holder := Node3D.new()
	holder.scale = Vector3.ONE * sc
	# Mitte des Grundrisses auf den Ursprung, Unterkante auf den Boden
	inst.position = Vector3(-(box.position.x + box.size.x * 0.5), -box.position.y, -(box.position.z + box.size.z * 0.5))
	holder.add_child(inst)
	root.add_child(holder)
	return box.size.y * sc

func _aabb_of(n: Node) -> AABB:
	var total := AABB()
	var first := true
	var stack: Array = [n]
	while not stack.is_empty():
		var cur: Node = stack.pop_back()
		for c in cur.get_children():
			stack.append(c)
		if cur is MeshInstance3D:
			var mi := cur as MeshInstance3D
			var local := _xform_to(mi, n) * mi.get_aabb()
			total = local if first else total.merge(local)
			first = false
	return total

func _xform_to(node: Node3D, ancestor: Node) -> Transform3D:
	var t := Transform3D.IDENTITY
	var cur: Node = node
	while cur != null and cur != ancestor:
		if cur is Node3D:
			t = (cur as Node3D).transform * t
		cur = cur.get_parent()
	return t
