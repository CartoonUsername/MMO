extends Node
## Gemeinsame Hilfen. Der Server rechnet in Zentimetern; sichtbar wird die Welt mit dem Faktor S vergrößert,
## damit Figuren (ca. 1,8 m) und Gebäude ein stimmiges Verhältnis haben. Reine Darstellung, der Server bleibt maßgeblich.

const S := 0.03

func p3(p, y: float = 0.0) -> Vector3:
	return Vector3(float(p[0]) * S, y, float(p[1]) * S)

func hash_color(s: String, sat: float = 0.55, val: float = 0.85) -> Color:
	var h := float(absi(s.hash()) % 1000) / 1000.0
	return Color.from_hsv(h, sat, val)

func mat(c: Color, rough: float = 0.9, metal: float = 0.0, emit: Color = Color.BLACK, emit_energy: float = 0.0) -> StandardMaterial3D:
	var m := StandardMaterial3D.new()
	m.albedo_color = c
	m.roughness = rough
	m.metallic = metal
	if emit_energy > 0.0:
		m.emission_enabled = true
		m.emission = emit
		m.emission_energy_multiplier = emit_energy
	return m

func mesh_node(mesh: Mesh, material: Material, pos: Vector3 = Vector3.ZERO) -> MeshInstance3D:
	var n := MeshInstance3D.new()
	n.mesh = mesh
	n.material_override = material
	n.position = pos
	return n

func label3d(text: String, size: float = 0.5, color: Color = Color.WHITE, fade_end: float = 0.0) -> Label3D:
	var l := Label3D.new()
	l.text = text
	l.pixel_size = 0.01
	l.font_size = int(size * 100.0)
	l.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	l.no_depth_test = false
	l.fixed_size = false
	l.outline_size = 14
	l.modulate = color
	l.outline_modulate = Color(0, 0, 0, 0.9)
	if fade_end > 0.0:
		l.visibility_range_end = fade_end
		l.visibility_range_end_margin = fade_end * 0.25
		l.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
	return l
