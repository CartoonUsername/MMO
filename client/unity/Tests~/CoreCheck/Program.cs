// Prüft die UnityEngine-freien Teile des Clients gegen einen echten Server (WebSocket): Anmeldung, Beitritt, jedes Fenster (Abfrage + Darstellung),
// Formulare und einige Befehle. Aufruf: dotnet run -- ws://127.0.0.1:PORT/ws   (siehe scripts/check_unity_core.sh)
using System;
using System.Collections.Generic;
using System.Threading;
using Mmo;
using Newtonsoft.Json.Linq;

static class Program
{
    static int fails;
    static void Check(bool ok, string what) { if (!ok) { fails++; Console.WriteLine("FEHLER: " + what); } else Console.WriteLine("ok: " + what); }

    static JObject Call(NetClient net, string cmd, JObject args)
    {
        JObject reply = null;
        net.Send(cmd, args, r => reply = r);
        for (int i = 0; i < 200 && reply == null; i++) { Thread.Sleep(25); net.Pump(); }
        return reply;
    }

    static int Main(string[] argv)
    {
        var url = "ws://127.0.0.1:7777/ws"; foreach (var a in argv) if (a.StartsWith("ws")) url = a;
        var unknown = Panels.Unknown();
        Check(unknown.Count == 0, "alle Fenster-Befehle stehen im Katalog" + (unknown.Count > 0 ? ": " + string.Join(",", unknown) : ""));

        var net = new NetClient();
        string welcome = null;
        net.OnEvent += ev => { if ((string)ev["ev"] == "welcome") welcome = (string)ev["ev"]; };
        var account = "core" + new Random().Next(100000, 999999);
        net.ConnectWs(url, account, "passwort1234", true);
        for (int i = 0; i < 200 && welcome == null; i++) { Thread.Sleep(25); net.Pump(); }
        Check(welcome != null && net.Token != null, "Anmeldung per WebSocket (welcome + Token)");

        var join = Call(net, "game.join", new JObject());
        Check(join != null && (bool)join["ok"], "game.join");
        var map = Call(net, "game.map", new JObject());
        Check(map != null && (bool)map["ok"] && map["result"]["regions"] != null, "game.map");
        var world = Call(net, "game.world", new JObject());
        Check(world != null && (bool)world["ok"] && world["result"]["regions"] != null, "game.world (Regionen)");

        foreach (var p in Panels.All)
        {
            var r = Call(net, p.Query, new JObject());
            var okq = r != null && (bool)r["ok"];
            Check(okq, "Fenster " + p.Title + ": " + p.Query + (okq ? "" : " -> " + (r == null ? "keine Antwort" : r["error"].ToString())));
            if (okq) { var lines = Panels.Render(r["result"]); Check(lines.Count > 0, "Fenster " + p.Title + " lässt sich darstellen (" + lines.Count + " Zeilen)"); }
        }

        // Formular: Typen, Pflichtfelder, Listen
        var f = new ActionForm("market.place");
        Check(!f.TryBuild(out _, out var e1) && e1.StartsWith("Feld fehlt"), "Formular verlangt Pflichtfelder");
        f.Values["side"] = "buy"; f.Values["item_key"] = "iron_ore@standard"; f.Values["qty"] = "abc"; f.Values["price"] = "5";
        Check(!f.TryBuild(out _, out var e2) && e2.Contains("Zahl"), "Formular prüft Zahlen");
        f.Values["qty"] = "2";
        Check(f.TryBuild(out var args, out _) && (long)args["qty"] == 2 && args["ioc"] == null && args["char"] == null, "Formular baut Argumente (ohne handelnde Figur, ohne leere optionale)");
        var rej = Call(net, "market.place", args);
        Check(rej != null && ActionForm.ErrorText(rej) != null, "Server lehnt ab (kein Geld/keine Ware) und der Text ist lesbar: " + (rej == null ? "-" : ActionForm.ErrorText(rej)));

        // Befehle mit anderem Schlüssel für die handelnde Figur (actor): Server muss das Argument akzeptieren (Ablehnung ist ok, "bad_request" nicht)
        var co = Call(net, "company.close", new JObject { ["company"] = "x" });
        Check(co != null && (co["error"] == null || (string)co["error"]["code"] != "bad_request"), "actor-Befehl wird korrekt gebildet (company.close)");
        var qc = Call(net, "query.chronicle", new JObject());
        Check(qc != null && (bool)qc["ok"] && qc["result"]["total"] != null, "Befehl ohne handelnde Figur (query.chronicle)");

        net.Dispose();
        Console.WriteLine(fails == 0 ? "ALLES OK" : fails + " Fehler");
        return fails == 0 ? 0 : 1;
    }
}
