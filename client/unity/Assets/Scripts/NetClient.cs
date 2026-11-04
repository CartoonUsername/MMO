// Verbindung zum Spielserver (TCP, eine JSON-Nachricht je Zeile). Siehe docs/VERTICAL_SLICE_PROTOCOL.md.
// Abhängigkeit: Paket "com.unity.nuget.newtonsoft-json" (Package Manager, kostenlos).
using System;
using System.Collections.Concurrent;
using System.IO;
using System.Net.Security;
using System.Net.Sockets;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using Newtonsoft.Json.Linq;

namespace Mmo
{
    public class NetClient : IDisposable
    {
        readonly ConcurrentQueue<JObject> inbox = new ConcurrentQueue<JObject>();
        TcpClient tcp; StreamWriter writer; Thread reader; volatile bool running;
        int counter; public string Account { get; private set; }
        public event Action<JObject> OnEvent;                        // Server-Ereignisse (haben "ev")
        readonly System.Collections.Generic.Dictionary<string, Action<JObject>> pending = new System.Collections.Generic.Dictionary<string, Action<JObject>>();

        ClientWebSocket ws; CancellationTokenSource cts;
        public bool Connected => running;
        public string LastError { get; private set; } = "";

        public string Token { get; private set; }                     // Sitzungs-Token für die Wiederanmeldung (kommt mit "welcome")

        // Anmeldung: register = neues Konto anlegen; sonst Passwort oder (nach Verbindungsabbruch) Token. useTls: verschlüsselt (Zertifikat muss dem System vertrauen).
        public void Connect(string host, int port, string account, string password = null, bool register = false, bool useTls = false, string token = null)
        {
            Account = account;
            tcp = new TcpClient { NoDelay = true };
            tcp.Connect(host, port);
            System.IO.Stream stream = tcp.GetStream();
            if (useTls)
            {
                var ssl = new SslStream(stream, false);
                ssl.AuthenticateAsClient(host);
                stream = ssl;
            }
            writer = new StreamWriter(stream, new UTF8Encoding(false)) { AutoFlush = true, NewLine = "\n" };
            running = true;
            reader = new Thread(() =>
            {
                try
                {
                    using (var sr = new StreamReader(stream, Encoding.UTF8))
                    {
                        string line;
                        while (running && (line = sr.ReadLine()) != null)
                            if (line.Length > 0) inbox.Enqueue(JObject.Parse(line));
                    }
                }
                catch (Exception) { /* Verbindung beendet */ }
                running = false;
            }) { IsBackground = true };
            reader.Start();
            var hello = new JObject { ["cmd"] = register ? "register" : "hello", ["account"] = account };
            if (password != null) hello["password"] = password;
            if (token != null) hello["token"] = token;
            writer.WriteLine(hello.ToString(Newtonsoft.Json.Formatting.None));
        }


        // Anmeldung über WebSocket (so erreicht der Client auch den gehosteten Server hinter Caddy/TLS): url z. B. wss://host/ws oder ws://127.0.0.1:7777/ws.
        public void ConnectWs(string url, string account, string password = null, bool register = false, string token = null)
        {
            Account = account;
            ws = new ClientWebSocket();
            cts = new CancellationTokenSource();
            ws.ConnectAsync(new Uri(url), cts.Token).GetAwaiter().GetResult();
            running = true;
            reader = new Thread(() =>
            {
                var buf = new byte[16384];
                try
                {
                    while (running && ws.State == WebSocketState.Open)
                    {
                        var ms = new MemoryStream();
                        WebSocketReceiveResult res;
                        do
                        {
                            res = ws.ReceiveAsync(new ArraySegment<byte>(buf), cts.Token).GetAwaiter().GetResult();
                            if (res.MessageType == WebSocketMessageType.Close) { running = false; return; }
                            ms.Write(buf, 0, res.Count);
                        } while (!res.EndOfMessage);
                        var text = Encoding.UTF8.GetString(ms.ToArray());
                        if (text.Length > 0) inbox.Enqueue(JObject.Parse(text));
                    }
                }
                catch (Exception e) { LastError = e.Message; }
                running = false;
            }) { IsBackground = true };
            reader.Start();
            var hello = new JObject { ["cmd"] = register ? "register" : "hello", ["account"] = account };
            if (password != null) hello["password"] = password;
            if (token != null) hello["token"] = token;
            WriteRaw(hello.ToString(Newtonsoft.Json.Formatting.None));
        }

        void WriteRaw(string line)
        {
            if (ws != null)
            {
                var bytes = Encoding.UTF8.GetBytes(line);
                lock (ws) ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, cts.Token).GetAwaiter().GetResult();
            }
            else lock (writer) writer.WriteLine(line);
        }

        // Befehl senden; der Rückruf läuft im Hauptthread (in Update -> Pump).
        public void Send(string cmd, JObject args, Action<JObject> callback = null)
        {
            if (!running) return;
            var def = Protocol.Find(cmd);                                  // Katalog sagt, welches Argument die handelnde Figur trägt (char, actor, teacher ...)
            var actorKey = def == null ? "char" : def.Actor;                 // game.* sind nicht im Katalog: dort immer "char"
            if (!string.IsNullOrEmpty(actorKey) && args[actorKey] == null) args[actorKey] = Account;
            var id = Account + "-" + (++counter);
            if (callback != null) pending[id] = callback;
            var msg = new JObject { ["v"] = 1, ["id"] = id, ["cmd"] = cmd, ["args"] = args };
            WriteRaw(msg.ToString(Newtonsoft.Json.Formatting.None));
        }

        // Aus Update() aufrufen: verteilt eingegangene Nachrichten im Hauptthread.
        public void Pump()
        {
            while (inbox.TryDequeue(out var msg))
            {
                if (msg["ev"] != null)
                {
                    if ((string)msg["ev"] == "welcome" && msg["token"] != null) Token = (string)msg["token"];
                    OnEvent?.Invoke(msg); continue;
                }
                var id = (string)msg["id"];
                if (id != null && pending.TryGetValue(id, out var cb)) { pending.Remove(id); cb(msg); }
            }
        }

        public void Dispose()
        {
            running = false;
            try { tcp?.Close(); } catch (Exception) { }
            try { cts?.Cancel(); ws?.Dispose(); } catch (Exception) { }
        }
    }
}
