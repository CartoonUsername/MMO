// Verbindung zum Spielserver (TCP, eine JSON-Nachricht je Zeile). Siehe docs/VERTICAL_SLICE_PROTOCOL.md.
// Abhängigkeit: Paket "com.unity.nuget.newtonsoft-json" (Package Manager, kostenlos).
using System;
using System.Collections.Concurrent;
using System.IO;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace Mmo
{
    public class NetClient : IDisposable
    {
        readonly ConcurrentQueue<JObject> inbox = new ConcurrentQueue<JObject>();
        TcpClient tcp; StreamWriter writer; Thread reader; volatile bool running;
        int counter; public string Account { get; private set; }
        public event Action<JObject> OnEvent;                        // Server-Ereignisse (haben "ev")
        readonly System.Collections.Generic.Dictionary<string, Action<JObject>> pending = new System.Collections.Generic.Dictionary<string, Action<JObject>>();

        public bool Connected => running;

        public void Connect(string host, int port, string account)
        {
            Account = account;
            tcp = new TcpClient { NoDelay = true };
            tcp.Connect(host, port);
            var stream = tcp.GetStream();
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
            writer.WriteLine(new JObject { ["cmd"] = "hello", ["account"] = account }.ToString(Newtonsoft.Json.Formatting.None));
        }

        // Befehl senden; der Rückruf läuft im Hauptthread (in Update -> Pump).
        public void Send(string cmd, JObject args, Action<JObject> callback = null)
        {
            if (!running) return;
            args["char"] = Account;
            var id = Account + "-" + (++counter);
            if (callback != null) pending[id] = callback;
            var msg = new JObject { ["v"] = 1, ["id"] = id, ["cmd"] = cmd, ["args"] = args };
            lock (writer) writer.WriteLine(msg.ToString(Newtonsoft.Json.Formatting.None));
        }

        // Aus Update() aufrufen: verteilt eingegangene Nachrichten im Hauptthread.
        public void Pump()
        {
            while (inbox.TryDequeue(out var msg))
            {
                if (msg["ev"] != null) { OnEvent?.Invoke(msg); continue; }
                var id = (string)msg["id"];
                if (id != null && pending.TryGetValue(id, out var cb)) { pending.Remove(id); cb(msg); }
            }
        }

        public void Dispose()
        {
            running = false;
            try { tcp?.Close(); } catch (Exception) { }
        }
    }
}
