// Fenster-Katalog und Formularlogik - bewusst ohne UnityEngine, damit sie außerhalb von Unity getestet werden kann (client/unity/Tests~).
// Jedes Fenster zeigt das Ergebnis einer Abfrage und bietet Befehle aus dem generierten Katalog (Protocol.g.cs) als Formular an.
// Der Server entscheidet alles; der Client zeigt nur an und schickt Absichten.
using System;
using System.Collections.Generic;
using System.Text;
using Newtonsoft.Json.Linq;

namespace Mmo
{
    public sealed class PanelDef
    {
        public readonly string Title, Query; public readonly string[] Commands; public readonly string[] QueryArgs;
        public PanelDef(string title, string query, string[] commands, string[] queryArgs = null) { Title = title; Query = query; Commands = commands; QueryArgs = queryArgs ?? new string[0]; }
    }

    public static class Panels
    {
        static readonly System.Collections.Generic.Dictionary<string, string> ElementNames = new System.Collections.Generic.Dictionary<string, string>
        {
            { "fire", "Feuer" }, { "water", "Wasser" }, { "shadow", "Schatten" }, { "light", "Licht" }, { "wind", "Wind" },
            { "earth", "Erde" }, { "electric", "Elektro" }, { "ice", "Eis" }, { "nature", "Natur" },
        };

        /// <summary>Anzeigename eines Kampfbefehls: Kombinationszauber (combo_a_b[_c]) als "Erde+Wasser", sonst der Befehl selbst (AP 27/28).</summary>
        public static string SkillLabel(string cmd)
        {
            if (cmd == null || !cmd.StartsWith("combo_")) return cmd;
            var parts = cmd.Substring(6).Split('_');
            for (int i = 0; i < parts.Length; i++) parts[i] = ElementNames.TryGetValue(parts[i], out var n) ? n : parts[i];
            return string.Join("+", parts);
        }

        public static readonly PanelDef[] All = new PanelDef[]
        {
            new PanelDef("Figur", "query.character", new[] { "character.choose_class", "essence.decide", "essence.trial", "essence.adopt", "combat.set_loadout" }),
            new PanelDef("Ausrüstung", "query.equipment", new[] { "equip.wear", "equip.remove", "equip.look" }),
            new PanelDef("Echos", "query.echoes", new[] { "echo.activate", "echo.release", "echo.equip", "echo.unequip", "echo.upgrade", "echo.list", "echo.cancel", "echo.buy" }),
            new PanelDef("Markt", "query.market", new[] { "market.place", "market.cancel", "maker.buy", "maker.sell", "query.market_quote" }),
            new PanelDef("Herstellen", "query.economic_profile", new[] { "craft", "discovery.complete", "discovery.teach" }),
            new PanelDef("Gruppe", "query.party", new[] { "party.form", "party.invite", "party.accept", "party.decline", "party.leave", "party.kick", "party.promote", "party.set_loot", "party.disband" }),
            new PanelDef("Handel", "query.offers", new[] { "trade.offer", "trade.accept", "trade.decline", "trade.cancel" }),
            new PanelDef("Firma", "query.my_companies", new[] { "company.found", "company.hire", "company.fire", "company.upgrade", "company.close", "production.stock_in", "production.stock_out", "production.start", "production.cancel", "production.sell", "company.branch_open", "company.branch_close", "company.branch_reopen" }),
            new PanelDef("Siedlung", "query.settlements", new[] { "settlement.found", "plot.buy", "plot.build", "plot.stash_in", "plot.stash_out", "plot.abandon", "project.contribute" }),
            new PanelDef("Forschung", "query.research", new[] { "research.start", "research.contribute", "research.license" }),
            new PanelDef("Gilde", "query.guild", new[] { "guild.found", "guild.invite", "guild.accept", "guild.decline", "guild.leave", "guild.kick", "guild.role", "guild.stash", "guild.take", "guild.contribute", "guild.research", "guild.disband" }),
            new PanelDef("Chronik", "query.chronicle", new[] { "query.prestige" }),
        };

        // Alle Befehle der Fenster müssen im Katalog stehen - sonst weicht der Client vom Server ab (wird im Test geprüft).
        public static List<string> Unknown()
        {
            var bad = new List<string>();
            foreach (var p in All)
            {
                if (Protocol.Find(p.Query) == null) bad.Add(p.Query);
                foreach (var c in p.Commands) if (Protocol.Find(c) == null) bad.Add(c);
            }
            return bad;
        }

        // Ergebnis lesbar machen: Schlüssel/Wert mit Einrückung, Listen nummeriert, Tiefe und Länge begrenzt (Oberfläche, keine Rohdaten-Flut).
        public static List<string> Render(JToken t, int maxDepth = 4, int maxLines = 160)
        {
            var lines = new List<string>();
            Walk(t, "", 0, maxDepth, lines, maxLines);
            if (lines.Count >= maxLines) lines.Add("… (gekürzt)");
            return lines;
        }

        static void Walk(JToken t, string key, int depth, int maxDepth, List<string> lines, int maxLines)
        {
            if (lines.Count >= maxLines) return;
            var pad = new string(' ', depth * 2);
            switch (t.Type)
            {
                case JTokenType.Object:
                    if (key.Length > 0) lines.Add(pad + key + ":");
                    if (depth >= maxDepth) { lines.Add(pad + "  …"); return; }
                    foreach (var kv in (JObject)t) Walk(kv.Value, kv.Key, key.Length > 0 ? depth + 1 : depth, maxDepth, lines, maxLines);
                    break;
                case JTokenType.Array:
                    var arr = (JArray)t;
                    if (arr.Count == 0) { lines.Add(pad + (key.Length > 0 ? key + ": " : "") + "–"); break; }
                    if (IsScalarList(arr)) { lines.Add(pad + (key.Length > 0 ? key + ": " : "") + string.Join(", ", ScalarStrings(arr))); break; }
                    if (key.Length > 0) lines.Add(pad + key + ":");
                    if (depth >= maxDepth) { lines.Add(pad + "  …"); return; }
                    int i = 1;
                    foreach (var e in arr) { Walk(e, "#" + (i++), depth + 1, maxDepth, lines, maxLines); }
                    break;
                case JTokenType.Null:
                    lines.Add(pad + key + ": –"); break;
                default:
                    lines.Add(pad + (key.Length > 0 ? key + ": " : "") + t.ToString());
                    break;
            }
        }

        static bool IsScalarList(JArray a) { foreach (var e in a) if (e.Type == JTokenType.Object || e.Type == JTokenType.Array) return false; return true; }
        static IEnumerable<string> ScalarStrings(JArray a) { foreach (var e in a) yield return e.ToString(); }
    }

    // Formular zu einem Befehl: Felder aus dem Katalog, Eingaben als Text, Umwandlung nach Typ. Die handelnde Figur setzt NetClient.Send.
    public sealed class ActionForm
    {
        public readonly Protocol.Cmd Cmd; public readonly Dictionary<string, string> Values = new Dictionary<string, string>();
        public ActionForm(string cmd)
        {
            Cmd = Protocol.Find(cmd) ?? throw new ArgumentException("Unbekannter Befehl: " + cmd);
            foreach (var a in Cmd.Args) if (a.Name != Cmd.Actor) Values[a.Name] = "";
        }

        public IEnumerable<Protocol.Arg> Fields() { foreach (var a in Cmd.Args) if (a.Name != Cmd.Actor) yield return a; }

        // Baut die Argumente; Fehlertext statt Ausnahme, damit die Oberfläche ihn anzeigen kann. Leere optionale Felder entfallen.
        public bool TryBuild(out JObject args, out string error)
        {
            args = new JObject(); error = null;
            foreach (var a in Fields())
            {
                var raw = (Values.TryGetValue(a.Name, out var v) ? v : "").Trim();
                if (raw.Length == 0)
                {
                    if (a.Optional) continue;
                    error = "Feld fehlt: " + a.Name; return false;
                }
                switch (a.Type)
                {
                    case 'i':
                        if (!long.TryParse(raw, out var n)) { error = a.Name + " muss eine Zahl sein"; return false; }
                        args[a.Name] = n; break;
                    case 'b':
                        var low = raw.ToLowerInvariant();
                        if (low != "ja" && low != "nein" && low != "true" && low != "false") { error = a.Name + ": ja oder nein"; return false; }
                        args[a.Name] = low == "ja" || low == "true"; break;
                    case 'l':
                        var arr = new JArray();
                        foreach (var part in raw.Split(',')) if (part.Trim().Length > 0) arr.Add(part.Trim());
                        args[a.Name] = arr; break;
                    default:
                        args[a.Name] = raw; break;
                }
            }
            return true;
        }

        public static string ErrorText(JObject reply)
        {
            if (reply["ok"] != null && (bool)reply["ok"]) return null;
            var e = reply["error"];
            return e == null ? "Unbekannter Fehler" : (string)e["message"] ?? (string)e["code"];
        }
    }
}
