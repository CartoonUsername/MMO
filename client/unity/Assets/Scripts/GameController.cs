// Spielsteuerung des Unity-Clients: Anmeldung per WebSocket, Bewegung, Kamera, Sammeln, Kampf mit Fertigkeitsleiste aus dem Klassen-Kit,
// Dungeon-Eingang, Ereignisse und die Fenster (siehe Panels.cs). Oberfläche mit OnGUI (keine Prefabs nötig). Der Server entscheidet alles.
using System.Collections.Generic;
using System.Text;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace Mmo
{
    public class GameController : MonoBehaviour
    {
        public string url = "wss://187.126.26.226.sslip.io/ws";     // gehosteter Test-Server; lokal: ws://127.0.0.1:7777/ws
        public string account = "spieler1";
        public string password = "";                                  // nur für den Test im Editor; ein echter Client fragt das Passwort ab
        public bool register = false;
        public bool autoConnect = false;                              // false: zuerst Anmeldemaske (kein Inspector nötig)

        NetClient net;
        JObject state, fight, world;
        JArray kit = new JArray();
        float kitStamina = 100f;
        readonly Dictionary<string, float> cooldownUntil = new Dictionary<string, float>();
        string lastEnd = "", info = "", warning = ""; float warningUntil;
        readonly List<string> log = new List<string>();
        readonly Dictionary<string, GameObject> views = new Dictionary<string, GameObject>();
        Camera cam;
        Vector2Int lastDir = new Vector2Int(99, 99);
        string inventory = ""; float nextInvPoll;
        const float CmToM = 0.01f;

        // Fenster
        int openPanel = -1; List<string> panelLines = new List<string>(); string panelError = ""; float nextPanelPoll;
        Vector2 panelScroll; string selectedAction; ActionForm form; string formResult = "";

        void Start()
        {
            cam = Camera.main != null ? Camera.main : new GameObject("Camera", typeof(Camera)).GetComponent<Camera>();
            var g = GameObject.CreatePrimitive(PrimitiveType.Plane);
            g.name = "Boden"; g.transform.localScale = new Vector3(6f, 1f, 6f); g.transform.position = new Vector3(30f, 0f, 30f);
            if (autoConnect) StartConnect();
        }

        void StartConnect()
        {
            try
            {
                net = new NetClient();
                net.OnEvent += OnServerEvent;
                net.ConnectWs(url, account, password.Length > 0 ? password : null, register);
            }
            catch (System.Exception e) { info = "Verbindung fehlgeschlagen: " + e.Message; net = null; return; }
            net.Send("game.join", new JObject(), r =>
            {
                if (!Ok(r)) { info = Reply(r); return; }
                net.Send("game.map", new JObject(), BuildMap);
                net.Send("game.world", new JObject(), w => { if (Ok(w)) world = (JObject)w["result"]; });
                RefreshKit();
            });
        }

        void RefreshKit()
        {
            net.Send("game.kit", new JObject(), r =>
            {
                if (!Ok(r)) return;
                kit = (JArray)r["result"]["commands"]; kitStamina = (float)r["result"]["stamina_max"];
            });
        }

        void LoginGui()
        {
            GUILayout.BeginArea(new Rect(Screen.width / 2 - 200, Screen.height / 2 - 140, 400, 280), GUI.skin.box);
            GUILayout.Label("MMO Testclient – Anmeldung");
            GUILayout.Label("Server-Adresse (wss://… oder ws://…)"); url = GUILayout.TextField(url);
            GUILayout.Label("Konto"); account = GUILayout.TextField(account);
            GUILayout.Label("Passwort (mind. 8 Zeichen)"); password = GUILayout.PasswordField(password, '*');
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Anmelden")) { register = false; StartConnect(); }
            if (GUILayout.Button("Konto anlegen")) { register = true; StartConnect(); }
            GUILayout.EndHorizontal();
            if (info.Length > 0) GUILayout.Label(info);
            GUILayout.EndArea();
        }

        // Statische Karte (Darstellung): Gebiete als flache Quader, Hindernisse als Zylinder. Begehbarkeit entscheidet allein der Server.
        void BuildMap(JObject r)
        {
            if (!Ok(r)) { info = "Karte nicht verfügbar"; return; }
            var m = r["result"];
            foreach (var reg in m["regions"])
            {
                var rect = reg["rect"];
                float x1 = (float)rect[0] * CmToM, y1 = (float)rect[1] * CmToM, x2 = (float)rect[2] * CmToM, y2 = (float)rect[3] * CmToM;
                var g = GameObject.CreatePrimitive(PrimitiveType.Cube);
                g.name = "Gelände " + reg["kind"];
                g.transform.position = new Vector3((x1 + x2) / 2f, 0.02f, (y1 + y2) / 2f);
                g.transform.localScale = new Vector3(x2 - x1, 0.04f, y2 - y1);
                Destroy(g.GetComponent<Collider>());
                g.GetComponent<Renderer>().material.color = KindColor((string)reg["kind"]);
            }
            foreach (var o in m["obstacles"])
            {
                var g = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
                float rad = (float)o["r"] * CmToM;
                g.name = "Hindernis";
                g.transform.position = new Vector3((float)o["at"][0] * CmToM, 1f, (float)o["at"][1] * CmToM);
                g.transform.localScale = new Vector3(rad * 2f, 1f, rad * 2f);
                g.GetComponent<Renderer>().material.color = new Color(0.35f, 0.35f, 0.35f);
            }
        }

        static Color KindColor(string kind)
        {
            switch (kind)
            {
                case "road": return new Color(0.75f, 0.65f, 0.45f);
                case "water": return new Color(0.15f, 0.35f, 0.8f);
                case "mud": return new Color(0.4f, 0.3f, 0.2f);
                default: return new Color(0.3f, 0.6f, 0.3f);
            }
        }

        void OnDestroy() { net?.Dispose(); }

        void Say(string s) { log.Add(s); while (log.Count > 8) log.RemoveAt(0); }

        void OnServerEvent(JObject ev)
        {
            switch ((string)ev["ev"])
            {
                case "state": state = ev; break;
                case "fight_start":
                    fight = new JObject(); cooldownUntil.Clear();
                    if (ev["kit"] is JArray k) kit = k;
                    Say("Kampf beginnt gegen " + string.Join(", ", ev["opponents"])); break;
                case "fight": fight = ev; break;
                case "telegraph":                                  // Gegner kündigt eine Fähigkeit an: Vorwarnzeit und mögliche Antworten
                    warning = ev["ability"] + " (" + ev["kind"] + ") in " + ((float)ev["ticks"] / 10f).ToString("0.0") + " s – Antwort: " + string.Join("/", ev["answers"]);
                    warningUntil = Time.time + (float)ev["ticks"] / 10f + 0.5f;
                    break;
                case "enemy_event":
                    if ((string)ev["type"] == "interrupted") Say("Unterbrochen: " + ev["ability"]);
                    else if ((string)ev["type"] == "shield_broken") Say("Schild gebrochen (" + ev["by"] + ")");
                    else if ((string)ev["type"] == "phase") Say("Gegner wechselt in Phase " + ev["phase"]);
                    break;
                case "fight_left": fight = null; Say("Kampf verlassen: " + ev["reason"]); break;
                case "fight_end":
                    fight = null; lastEnd = ev["outcome"] + "  Beute: " + ev["loot"]; Say("Kampf beendet: " + lastEnd); RefreshKit(); break;
                case "region": Say("Region: " + ev["name"]); break;
                case "region_blocked": Say("Zutritt verweigert: " + ev["reason"]); break;
                case "dungeon": Say("Dungeon " + ev["name"] + ": " + ev["state"]); break;
                case "world_boss": Say("Weltboss " + ev["name"] + ": " + ev["state"]); break;
                case "economy_event": Say("Marktnachricht: " + ev["headline"] + " (bis Tag " + ev["until"] + ")"); break;
                case "tech": Say(ev["site"] + " kennt jetzt " + ev["tech"] + ((bool)ev["first"] ? " – Weltneuheit!" : "")); break;
                case "chronicle": Say("Weltchronik: " + string.Join(", ", ev["chars"]) + " – " + ev["name"]); break;
                case "plot_forfeit": Say("Grundstück " + ev["n"] + " in " + ev["site"] + " ist verfallen (Steuer nicht gezahlt)"); break;
                case "notify": Say("Nachricht: " + ev["item"]["kind"]); break;
                case "error": info = "Fehler: " + ev["code"] + " " + ev["message"]; break;
                case "welcome": info = "Angemeldet"; break;
            }
        }

        void Update()
        {
            if (net == null) return;
            net.Pump();
            if (state == null) return;
            SyncViews();
            FollowCamera();
            if (fight == null) HandleWorldInput(); else HandleFightInput();
            if (Time.time > nextInvPoll) { nextInvPoll = Time.time + 1.5f; net.Send("query.inventory", new JObject(), r => inventory = Ok(r) ? r["result"].ToString(Newtonsoft.Json.Formatting.None) : ""); }
            if (openPanel >= 0 && Time.time > nextPanelPoll) RefreshPanel();
        }

        static bool Ok(JObject r) { return r != null && r["ok"] != null && (bool)r["ok"]; }
        static string Reply(JObject r) { return Ok(r) ? "OK" : "Abgelehnt: " + ActionForm.ErrorText(r); }
        static Vector3 ToWorld(JToken pos) { return new Vector3((float)pos[0] * CmToM, 0f, (float)pos[1] * CmToM); }

        void SyncViews()
        {
            var seen = new HashSet<string>();
            Place("ich", PrimitiveType.Capsule, new Color(0.2f, 0.5f, 1f), ToWorld(state["you"]["pos"]), seen, 1f);
            foreach (var p in state["players"]) Place("p:" + p["char"], PrimitiveType.Capsule, new Color(0.2f, 0.9f, 0.4f), ToWorld(p["pos"]), seen, 1f);
            foreach (var e in state["enemies"])
                if ((bool)e["alive"]) Place("e:" + e["id"], PrimitiveType.Capsule, EnemyColor((string)e["type"]), ToWorld(e["pos"]), seen, EnemyScale((string)e["type"]));
            foreach (var n in state["nodes"]) Place("n:" + n["id"], PrimitiveType.Cube, (bool)n["ready"] ? new Color(0.9f, 0.8f, 0.2f) : new Color(0.3f, 0.3f, 0.3f), ToWorld(n["pos"]), seen, 0.6f);
            var gone = new List<string>();
            foreach (var kv in views) if (!seen.Contains(kv.Key)) { Destroy(kv.Value); gone.Add(kv.Key); }
            foreach (var k in gone) views.Remove(k);
        }

        static Color EnemyColor(string type)
        {
            switch (type)
            {
                case "bear": return new Color(0.45f, 0.25f, 0.1f);
                case "stone_golem": return new Color(0.5f, 0.5f, 0.55f);
                default: return new Color(0.6f, 0.6f, 0.6f);
            }
        }

        static float EnemyScale(string type) { return type == "stone_golem" ? 2.2f : type == "bear" ? 1.6f : 0.8f; }

        void Place(string key, PrimitiveType type, Color color, Vector3 pos, HashSet<string> seen, float scale)
        {
            seen.Add(key);
            if (!views.TryGetValue(key, out var go))
            {
                go = GameObject.CreatePrimitive(type);
                go.GetComponent<Renderer>().material.color = color;
                go.transform.localScale = Vector3.one * scale;
                views[key] = go;
            }
            go.transform.position = Vector3.Lerp(go.transform.position, pos + Vector3.up * scale, 0.5f);   // einfache Glättung zwischen Serverständen
        }

        void FollowCamera()
        {
            if (!views.TryGetValue("ich", out var me)) return;
            cam.transform.position = Vector3.Lerp(cam.transform.position, me.transform.position + new Vector3(0f, 9f, -9f), 0.15f);
            cam.transform.LookAt(me.transform.position);
        }

        bool TextFocus() { return openPanel >= 0 && selectedAction != null; }      // beim Tippen in Formularen keine Spielsteuerung

        void HandleWorldInput()
        {
            int dx = 0, dz = 0;
            if (!TextFocus())
            {
                dx = (Input.GetKey(KeyCode.D) ? 1 : 0) - (Input.GetKey(KeyCode.A) ? 1 : 0);
                dz = (Input.GetKey(KeyCode.W) ? 1 : 0) - (Input.GetKey(KeyCode.S) ? 1 : 0);
            }
            var dir = new Vector2Int(dx, dz);
            if (dir != lastDir) { lastDir = dir; net.Send("game.move", new JObject { ["dx"] = dx, ["dy"] = dz }); }     // nur bei Änderung senden
            if (!TextFocus() && Input.GetKeyDown(KeyCode.E)) TryGather();
        }

        void TryGather()
        {
            string best = null; float bestD = 3f;
            var me = state["you"]["pos"];
            foreach (var n in state["nodes"])
            {
                float d = Vector3.Distance(ToWorld(me), ToWorld(n["pos"]));
                if (d < bestD) { bestD = d; best = (string)n["id"]; }
            }
            if (best == null) { info = "Kein Sammelpunkt in der Nähe"; return; }
            net.Send("game.gather", new JObject { ["node"] = best }, r => info = Ok(r) ? "Gesammelt: " + r["result"]["item"] : "Sammeln: " + ActionForm.ErrorText(r));
        }

        // Fertigkeitsleiste aus dem Klassen-Kit: Tasten 1..9 in der Reihenfolge des Servers, Maus links = erster Eintrag. Abklingzeit nur zur Anzeige,
        // der Server prüft Ausdauer, Sperrzeit und Abklingzeit selbst.
        static readonly KeyCode[] SlotKeys = { KeyCode.Alpha1, KeyCode.Alpha2, KeyCode.Alpha3, KeyCode.Alpha4, KeyCode.Alpha5, KeyCode.Alpha6, KeyCode.Alpha7, KeyCode.Alpha8, KeyCode.Alpha9 };

        void UseSkill(string cmd)
        {
            net.Send("game.fight", new JObject { ["input"] = cmd });
            foreach (var c in kit) if ((string)c["cmd"] == cmd) { cooldownUntil[cmd] = Time.time + (float)c["cooldown"] / 10f; break; }
        }

        void HandleFightInput()
        {
            if (TextFocus()) return;
            if (Input.GetMouseButtonDown(0) && kit.Count > 0) UseSkill((string)kit[0]["cmd"]);
            for (int i = 0; i < SlotKeys.Length && i < kit.Count; i++) if (Input.GetKeyDown(SlotKeys[i])) UseSkill((string)kit[i]["cmd"]);
            if (Input.GetKeyDown(KeyCode.Tab)) net.Send("game.fight", new JObject { ["input"] = "target_2" });
            if (Input.GetKeyDown(KeyCode.F)) net.Send("game.fight", new JObject { ["input"] = "flee" });
        }

        // ---------------------------------------------------------------- Fenster ----
        void RefreshPanel()
        {
            nextPanelPoll = Time.time + 3f;
            var p = Panels.All[openPanel];
            net.Send(p.Query, new JObject(), r =>
            {
                if (Ok(r)) { panelLines = Panels.Render(r["result"]); panelError = ""; }
                else panelError = ActionForm.ErrorText(r);
            });
        }

        void OpenPanel(int i)
        {
            openPanel = openPanel == i ? -1 : i; selectedAction = null; form = null; formResult = ""; panelLines = new List<string>(); panelError = "";
            nextPanelPoll = 0f;
        }

        void MenuGui()
        {
            GUILayout.BeginArea(new Rect(10, Screen.height - 215, Screen.width - 20, 28));
            GUILayout.BeginHorizontal();
            for (int i = 0; i < Panels.All.Length; i++)
                if (GUILayout.Toggle(openPanel == i, Panels.All[i].Title, GUI.skin.button) != (openPanel == i)) OpenPanel(i);
            GUILayout.EndHorizontal();
            GUILayout.EndArea();
        }

        void PanelGui()
        {
            if (openPanel < 0) return;
            var p = Panels.All[openPanel];
            GUILayout.BeginArea(new Rect(Screen.width - 460, 10, 450, Screen.height - 240), GUI.skin.box);
            GUILayout.Label(p.Title);
            panelScroll = GUILayout.BeginScrollView(panelScroll, GUILayout.Height(Screen.height - 470));
            if (panelError.Length > 0) GUILayout.Label("Fehler: " + panelError);
            foreach (var l in panelLines) GUILayout.Label(l);
            GUILayout.EndScrollView();
            GUILayout.Label("Aktion");
            GUILayout.BeginHorizontal();
            int col = 0;
            foreach (var c in p.Commands)
            {
                if (GUILayout.Button(c.Substring(c.IndexOf('.') + 1), GUILayout.ExpandWidth(false))) { selectedAction = c; form = new ActionForm(c); formResult = ""; }
                if (++col % 4 == 0) { GUILayout.EndHorizontal(); GUILayout.BeginHorizontal(); }
            }
            GUILayout.EndHorizontal();
            if (selectedAction != null && form != null)
            {
                GUILayout.Label(selectedAction + (form.Cmd.Mutating ? "" : "  (Abfrage)"));
                foreach (var f in form.Fields())
                {
                    GUILayout.BeginHorizontal();
                    GUILayout.Label(f.Name + (f.Optional ? " (optional)" : "") + " [" + TypeHint(f.Type) + "]", GUILayout.Width(190));
                    form.Values[f.Name] = GUILayout.TextField(form.Values[f.Name]);
                    GUILayout.EndHorizontal();
                }
                if (GUILayout.Button("Senden")) SendForm(p);
                if (formResult.Length > 0) GUILayout.Label(formResult);
            }
            GUILayout.EndArea();
        }

        static string TypeHint(char t) { return t == 'i' ? "Zahl" : t == 'b' ? "ja/nein" : t == 'l' ? "a, b, c" : "Text"; }

        void SendForm(PanelDef p)
        {
            if (!form.TryBuild(out var args, out var err)) { formResult = err; return; }
            var cmd = selectedAction;
            net.Send(cmd, args, r =>
            {
                formResult = Ok(r) ? "OK" + (r["result"] != null && r["result"].Type != JTokenType.Null ? ": " + r["result"].ToString(Newtonsoft.Json.Formatting.None) : "") : "Abgelehnt: " + ActionForm.ErrorText(r);
                nextPanelPoll = 0f;                                     // Fenster sofort neu laden
            });
        }

        // Dungeon-Eingang: Knopf, wenn die Figur nahe genug ist (Entscheidung trifft der Server).
        void DungeonGui()
        {
            if (world == null || fight != null || state == null) return;
            foreach (var d in (JObject)world["dungeons"])
            {
                var dist = Vector3.Distance(ToWorld(state["you"]["pos"]), ToWorld(d.Value["entrance"]));
                if (dist > (float)d.Value["radius"] * CmToM + 3f) continue;
                if (GUI.Button(new Rect(Screen.width / 2 - 110, 140, 220, 30), "Dungeon betreten: " + d.Value["name"]))
                    net.Send("game.dungeon_enter", new JObject { ["dungeon"] = d.Key }, r => info = Reply(r));
            }
        }

        void SkillBarGui()
        {
            if (kit.Count == 0) return;
            GUILayout.BeginArea(new Rect(Screen.width / 2 - 330, Screen.height - 120, 660, 100));
            GUILayout.BeginHorizontal();
            for (int i = 0; i < kit.Count; i++)
            {
                var c = kit[i]; var cmd = (string)c["cmd"];
                float left = cooldownUntil.TryGetValue(cmd, out var until) ? Mathf.Max(0f, until - Time.time) : 0f;
                var label = (i < 9 ? (i + 1) + " " : "") + cmd + "\nAusd. " + c["cost"] + (left > 0f ? "  " + left.ToString("0.0") + " s" : "");
                if (GUILayout.Button(label, GUILayout.Height(48), GUILayout.Width(70)) && fight != null) UseSkill(cmd);
            }
            GUILayout.EndHorizontal();
            GUILayout.EndArea();
        }

        void OnGUI()
        {
            if (net == null) { LoginGui(); return; }
            var sb = new StringBuilder();
            sb.AppendLine("Konto: " + account + (net.Connected ? "  (verbunden)" : "  (getrennt: " + net.LastError + ")"));
            if (state != null)
            {
                var reg = state["you"]["region"];
                sb.AppendLine("Tick " + state["tick"] + "  Tag " + state["day"] + "  Position " + state["you"]["pos"] +
                              (reg != null && reg.Type != JTokenType.Null ? "  Region " + reg["name"] + " (Gefahr " + reg["danger"] + ")" : ""));
                var dg = state["you"]["dungeon"];
                if (dg != null && dg.Type != JTokenType.Null) sb.AppendLine("Dungeon " + dg["name"] + ": Etappe " + dg["stage"] + "/" + dg["stages"]);
            }
            sb.AppendLine("Inventar: " + inventory);
            if (info.Length > 0) sb.AppendLine(info);
            GUI.Box(new Rect(10, 10, 560, 120), sb.ToString());
            if (fight != null && fight["players"] != null)
            {
                var f = new StringBuilder("KAMPF  (Tasten 1–9 = Leiste, Maus links = erster Eintrag, Tab Ziel 2, F fliehen)\n");
                foreach (var o in fight["opponents"])
                {
                    var cast = o["casting"] != null && o["casting"].Type != JTokenType.Null ? "  wirkt " + o["casting"]["ability"] + " (" + o["casting"]["ticks"] + ")" : "";
                    var shield = o["shield"] != null && (int)o["shield"] > 0 ? "  Schild " + o["shield"] : "";
                    f.AppendLine(o["type"] + "  LP " + o["hp"] + (bool.Parse(o["alive"].ToString()) ? "" : "  (gefallen)") + cast + shield);
                }
                if (Time.time < warningUntil) f.AppendLine("ACHTUNG: " + warning);
                int i = 0;
                foreach (var p in fight["players"])
                {
                    string st = p["stunned"] != null && (int)p["stunned"] > 0 ? "  BETÄUBT" : "";
                    if (p["slowed"] != null && (int)p["slowed"] > 0) st += "  verlangsamt";
                    if (p["burning"] != null && bool.Parse(p["burning"].ToString())) st += "  brennt";
                    f.AppendLine("Spieler " + (i++) + "  LP " + p["hp"] + "/" + p["max_hp"] + "  Ausdauer " + p["stamina"] + "/" + kitStamina + "  " + p["state"] + st);
                }
                GUI.Box(new Rect(10, 140, 560, 130), f.ToString());
            }
            GUI.Box(new Rect(10, Screen.height - 180, 330, 170), string.Join("\n", log) + "\n" + lastEnd);
            DungeonGui();
            SkillBarGui();
            MenuGui();
            PanelGui();
        }
    }
}
