// Spielsteuerung des Vertical Slice: Bewegung, Kamera, Sammeln, Kampf und einfache Oberfläche (OnGUI, keine Prefabs nötig).
// Szene: leere Szene mit diesem Skript an einem leeren GameObject (siehe client/unity/README.md).
using System.Collections.Generic;
using System.Text;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace Mmo
{
    public class GameController : MonoBehaviour
    {
        public string host = "127.0.0.1";
        public int port = 7777;
        public string account = "spieler1";
        public string password = "";                       // nur für den Test im Editor; ein echter Client fragt das Passwort ab
        public bool register = false;                      // beim ersten Start einmal anhaken, danach wieder aus
        public bool useTls = false;

        NetClient net;
        JObject state;                                   // letzter "state"-Ereignisinhalt
        JObject fight;                                   // letzter "fight"-Zustand (null außerhalb des Kampfes)
        string fightLeft = "", lastEnd = "", info = "";
        readonly List<string> log = new List<string>();
        readonly Dictionary<string, GameObject> views = new Dictionary<string, GameObject>();
        Transform ground; Camera cam;
        Vector2Int lastDir = new Vector2Int(99, 99);
        string inventory = "";
        float nextInvPoll;
        string warning = ""; float warningUntil;
        string partyTarget = "", tradeTo = "", tradeItem = "iron_ingot@common", recipe = "iron_ingot";

        const float CmToM = 0.01f;

        void Start()
        {
            cam = Camera.main != null ? Camera.main : new GameObject("Camera", typeof(Camera)).GetComponent<Camera>();
            var g = GameObject.CreatePrimitive(PrimitiveType.Plane);
            g.name = "Boden"; g.transform.localScale = new Vector3(6f, 1f, 6f); g.transform.position = new Vector3(30f, 0f, 30f);
            ground = g.transform;
            if (autoConnect) StartConnect();
        }

        public bool autoConnect = false;                   // false: zuerst Anmeldemaske (kein Inspector nötig)

        void StartConnect()
        {
            try
            {
                net = new NetClient();
                net.OnEvent += OnServerEvent;
                net.Connect(host, port, account, password.Length > 0 ? password : null, register, useTls);
            }
            catch (System.Exception e) { info = "Verbindung fehlgeschlagen: " + e.Message; net = null; return; }
            net.Send("game.join", new JObject(), r => net.Send("game.map", new JObject(), BuildMap));
        }

        void LoginGui()
        {
            GUILayout.BeginArea(new Rect(Screen.width / 2 - 160, Screen.height / 2 - 130, 320, 260), GUI.skin.box);
            GUILayout.Label("MMO Testclient – Anmeldung");
            GUILayout.Label("Server (Adresse)"); host = GUILayout.TextField(host);
            GUILayout.Label("Port"); int.TryParse(GUILayout.TextField(port.ToString()), out port);
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
            if (r["ok"] == null || !(bool)r["ok"]) { info = "Karte nicht verfügbar"; return; }
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

        void OnServerEvent(JObject ev)
        {
            switch ((string)ev["ev"])
            {
                case "state": state = ev; break;
                case "fight_start": fight = new JObject(); log.Add("Kampf beginnt gegen " + string.Join(", ", ev["opponents"])); break;
                case "fight": fight = ev; break;
                case "telegraph":                                  // Gegner kündigt eine Fähigkeit an: Vorwarnzeit und mögliche Antworten
                    warning = ev["ability"] + " (" + ev["kind"] + ") in " + ((float)ev["ticks"] / 10f).ToString("0.0") + " s – Antwort: " + string.Join("/", ev["answers"]);
                    warningUntil = Time.time + (float)ev["ticks"] / 10f + 0.5f;
                    break;
                case "enemy_event":
                    if ((string)ev["type"] == "interrupted") log.Add("Unterbrochen: " + ev["ability"]);
                    else if ((string)ev["type"] == "shield_broken") log.Add("Schild gebrochen (" + ev["by"] + ")");
                    else if ((string)ev["type"] == "phase") log.Add("Gegner wechselt in Phase " + ev["phase"]);
                    break;
                case "fight_left": fight = null; log.Add("Kampf verlassen: " + ev["reason"]); break;
                case "fight_end":
                    fight = null;
                    lastEnd = ev["outcome"] + "  Beute: " + ev["loot"]; log.Add("Kampf beendet: " + lastEnd); break;
                case "notify": log.Add("Nachricht: " + ev["item"]["kind"]); break;
                case "error": info = "Fehler: " + ev["code"] + " " + ev["message"]; break;
                case "welcome": info = "Angemeldet"; break;
            }
            while (log.Count > 8) log.RemoveAt(0);
        }

        void Update()
        {
            if (net == null) return;
            net.Pump();
            if (state == null) return;
            SyncViews();
            FollowCamera();
            if (fight == null) HandleWorldInput(); else HandleFightInput();
            if (Time.time > nextInvPoll) { nextInvPoll = Time.time + 1.5f; net.Send("query.inventory", new JObject(), r => inventory = r["ok"] != null && (bool)r["ok"] ? r["result"].ToString(Newtonsoft.Json.Formatting.None) : ""); }
        }

        static Vector3 ToWorld(JToken pos) { return new Vector3((float)pos[0] * CmToM, 0f, (float)pos[1] * CmToM); }

        void SyncViews()
        {
            var seen = new HashSet<string>();
            Place("ich", PrimitiveType.Capsule, new Color(0.2f, 0.5f, 1f), ToWorld(state["you"]["pos"]), seen, 1f);
            foreach (var p in state["players"]) Place("p:" + p["char"], PrimitiveType.Capsule, new Color(0.2f, 0.9f, 0.4f), ToWorld(p["pos"]), seen, 1f);
            foreach (var e in state["enemies"])
                if ((bool)e["alive"]) Place("e:" + e["id"], PrimitiveType.Capsule, (string)e["type"] == "bear" ? new Color(0.45f, 0.25f, 0.1f) : new Color(0.6f, 0.6f, 0.6f), ToWorld(e["pos"]), seen, (string)e["type"] == "bear" ? 1.6f : 0.8f);
            foreach (var n in state["nodes"]) Place("n:" + n["id"], PrimitiveType.Cube, (bool)n["ready"] ? new Color(0.9f, 0.8f, 0.2f) : new Color(0.3f, 0.3f, 0.3f), ToWorld(n["pos"]), seen, 0.6f);
            var gone = new List<string>();
            foreach (var kv in views) if (!seen.Contains(kv.Key)) { Destroy(kv.Value); gone.Add(kv.Key); }
            foreach (var k in gone) views.Remove(k);
        }

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

        void HandleWorldInput()
        {
            int dx = (Input.GetKey(KeyCode.D) ? 1 : 0) - (Input.GetKey(KeyCode.A) ? 1 : 0);
            int dz = (Input.GetKey(KeyCode.W) ? 1 : 0) - (Input.GetKey(KeyCode.S) ? 1 : 0);
            var dir = new Vector2Int(dx, dz);
            if (dir != lastDir) { lastDir = dir; net.Send("game.move", new JObject { ["dx"] = dx, ["dy"] = dz }); }     // nur bei Änderung senden
            if (Input.GetKeyDown(KeyCode.E)) TryGather();
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
            net.Send("game.gather", new JObject { ["node"] = best }, r => info = (bool)r["ok"] ? "Gesammelt: " + r["result"]["item"] : "Sammeln: " + r["error"]["message"]);
        }

        void SendFight(string cmd) { net.Send("game.fight", new JObject { ["input"] = cmd }); }

        void HandleFightInput()
        {
            if (Input.GetMouseButtonDown(0)) SendFight("light");
            if (Input.GetMouseButtonDown(1)) SendFight("heavy");
            if (Input.GetKeyDown(KeyCode.Space)) SendFight("dodge");
            if (Input.GetKeyDown(KeyCode.Q)) SendFight("block");
            if (Input.GetKeyDown(KeyCode.Alpha1)) SendFight("stun");
            if (Input.GetKeyDown(KeyCode.Alpha2)) SendFight("slow");
            if (Input.GetKeyDown(KeyCode.Alpha3)) SendFight("sweep");
            if (Input.GetKeyDown(KeyCode.Alpha4)) SendFight("heal");
            if (Input.GetKeyDown(KeyCode.Alpha5)) SendFight("shield");
            if (Input.GetKeyDown(KeyCode.Tab)) SendFight("target_2");
            if (Input.GetKeyDown(KeyCode.F)) SendFight("flee");
            if (Input.GetKeyDown(KeyCode.R)) SendFight("cast_ember");
            if (Input.GetKeyDown(KeyCode.C)) SendFight("dash");
            if (Input.GetKeyDown(KeyCode.V)) SendFight("veil");
        }

        void OnGUI()
        {
            if (net == null) { LoginGui(); return; }
            var sb = new StringBuilder();
            sb.AppendLine("Konto: " + account + (net != null && net.Connected ? "  (verbunden)" : "  (getrennt)"));
            if (state != null) sb.AppendLine("Tick " + state["tick"] + "  Tag " + state["day"] + "  Position " + state["you"]["pos"]);
            sb.AppendLine("Inventar: " + inventory);
            if (info.Length > 0) sb.AppendLine(info);
            GUI.Box(new Rect(10, 10, 560, 120), sb.ToString());
            if (fight != null && fight["players"] != null)
            {
                var f = new StringBuilder("KAMPF  (LMB leicht, RMB schwer, Leertaste ausweichen, Q blocken, 1 betäuben, 2 verlangsamen, 3 Rundumschlag, 4 heilen, 5 Schild, Tab Ziel 2, F fliehen, R/C/V Fähigkeiten)\n");
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
                    f.AppendLine("Spieler " + (i++) + "  LP " + p["hp"] + "/" + p["max_hp"] + "  Ausdauer " + p["stamina"] + "  " + p["state"] + st);
                }
                GUI.Box(new Rect(10, 140, 560, 130), f.ToString());
            }
            GUI.Box(new Rect(10, Screen.height - 180, 560, 170), string.Join("\n", log) + "\n" + lastEnd);
            // Handel und Gruppe (Weltbefehle laufen unverändert durch das Gateway)
            GUILayout.BeginArea(new Rect(Screen.width - 330, 10, 320, 330), GUI.skin.box);
            GUILayout.Label("Gruppe / Handel / Herstellen");
            partyTarget = GUILayout.TextField(partyTarget);
            if (GUILayout.Button("Gruppe gründen")) net.Send("party.form", new JObject(), r => info = Reply(r));
            if (GUILayout.Button("Einladen")) net.Send("party.invite", new JObject { ["target"] = partyTarget }, r => info = Reply(r));
            if (GUILayout.Button("Einladungen anzeigen")) net.Send("query.party_invites", new JObject(), r => info = r.ToString(Newtonsoft.Json.Formatting.None));
            if (GUILayout.Button("Erste Einladung annehmen")) net.Send("query.party_invites", new JObject(), r => { var l = r["result"] as JArray; if (l != null && l.Count > 0) net.Send("party.accept", new JObject { ["invite"] = l[0]["id"] }, r2 => info = Reply(r2)); });
            recipe = GUILayout.TextField(recipe);
            if (GUILayout.Button("Herstellen (3x, Güte standard)")) net.Send("craft", new JObject { ["recipe"] = recipe, ["qty"] = 3, ["grade"] = "standard" }, r => info = Reply(r));
            tradeTo = GUILayout.TextField(tradeTo);
            tradeItem = GUILayout.TextField(tradeItem);
            if (GUILayout.Button("Verkaufsangebot (1 Stück, Preis 20)")) net.Send("trade.offer", new JObject { ["to"] = tradeTo, ["side"] = "sell", ["item_key"] = tradeItem, ["qty"] = 1, ["price"] = 20 }, r => info = Reply(r));
            if (GUILayout.Button("Angebote anzeigen")) net.Send("query.offers", new JObject(), r => info = r.ToString(Newtonsoft.Json.Formatting.None));
            GUILayout.EndArea();
        }

        static string Reply(JObject r) { return (bool)r["ok"] ? "OK: " + r["result"] : "Abgelehnt: " + r["error"]["message"]; }
    }
}
