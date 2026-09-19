// ═══════════════════════════════════════════════════════════════════════════════════════════
// ModFlow Bridge — the NinjaTrader 8 side of the MODDYS OrderFlow Analysis suite integration.
//
// It republishes what the running platform already receives — level-1 quotes, trades, level-2
// market depth — plus instrument look-ups and historical bars, on a loopback TCP port using the
// same wire convention as the suite's Bookmap bridge: NUL-terminated JSON frames, UTF-8.
//
//   {"Type":"hello", ...}                                     sent on accept
//   {"Type":"quote","Instrument":..,"Last":..,"Bid":..,..}
//   {"Type":"trade","Instrument":..,"Price":..,"Size":..,"Aggressor":"buy"}
//   {"Type":"depth","Instrument":..,"Side":"bid","Price":..,"Size":..,"Operation":"add"}
//   {"Type":"depthsnapshot","Instrument":..,"Bids":[[p,s],..],"Asks":[[p,s],..]}
//   {"Type":"heartbeat","Ts":..}
//   {"Type":"instruments"|"bars"|"quote"|"capabilities"|"resolve","RequestId":.., ...}
//   {"Type":"error","RequestId":..,"Message":..}
//
// Commands accepted from the suite: subscribe / unsubscribe / ping / quote / instruments / bars /
// capabilities / resolve. Unknown types are ignored (a growing protocol must not break a reader).
//
// Read-only: this bridge never places, modifies or cancels an order, and never touches account
// credentials. It binds 127.0.0.1 only. One client at a time (a new connection replaces the old).
//
// Deployment: built by ../build.ps1 with the .NET SDK, dropped into
//   Documents\NinjaTrader 8\bin\Custom\AddOns\
// with Tools ▸ Options ▸ General ▸ Miscellaneous ▸ "Allow custom assembly loading" enabled.
// ═══════════════════════════════════════════════════════════════════════════════════════════

#region Using declarations
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
#endregion

namespace ModFlow.Bridge
{
    public class ModFlowBridgeAddOn : AddOnBase
    {
        // ── configuration ────────────────────────────────────────────────────────────────
        public const int Port = 8790;                 // the suite's convention; the Bookmap bridge uses 8791
        private const string AddonName = "modflow-nt-bridge";
        private const string AddonVersion = "1.0";
        private const int HeartbeatMs = 5000;         // a heartbeat frame on this cadence, always
        private const int QuoteThrottleMs = 100;      // per instrument: bid/ask frames are coalesced to ~10/s
        private const int MaxInstruments = 400;       // a listing request never returns an unbounded set
        private const int MaxBars = 20000;

        private static readonly object Gate = new object();
        private static bool serverStarted;
        private static TcpListener listener;
        private static TcpClient client;
        private static BlockingCollection<string> sendQueue;
        private static Thread acceptThread;
        private static Thread heartbeatThread;
        private static readonly ConcurrentDictionary<string, Sub> Subs =
            new ConcurrentDictionary<string, Sub>(StringComparer.OrdinalIgnoreCase);
        private static long depthEventCount;
        private static HashSet<string> futureRoots;   // lazily built: the platform's futures roots

        // MEM-E-03: there is deliberately no load-time kick thread. A NinjaScript editor
        // recompile reloads this assembly in place; the old static kick bound the port from a
        // *new* copy while the previous copy's statics, threads and subscriptions stayed alive
        // in the process — two bridges, one port owner, one zombie. The bridge now binds only
        // through the platform's own AddOn lifecycle (OnStateChange / OnWindowCreated), which
        // the live instance always receives; a bind failure names the stale-copy case below.
        static ModFlowBridgeAddOn()
        {
        }

        // ── AddOn lifecycle ─────────────────────────────────────────────────────────────
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "ModFlow Bridge";
                Description = "Publishes live market data on 127.0.0.1:" + Port +
                              " for the MODDYS OrderFlow Analysis suite. Read-only.";
            }
            else if (State == State.Active)
            {
                StartServerOnce();
            }
            else if (State == State.Terminated)
            {
                Shutdown();
            }
        }

        protected override void OnWindowCreated(System.Windows.Window window)
        {
            StartServerOnce();       // belt and braces: whichever fires first wins, the other is a no-op
        }

        // ── server ──────────────────────────────────────────────────────────────────────
        private static void StartServerOnce()
        {
            lock (Gate)
            {
                if (serverStarted) return;
                serverStarted = true;
                try
                {
                    listener = new TcpListener(IPAddress.Loopback, Port);
                    listener.Start();
                    acceptThread = new Thread(AcceptLoop) { IsBackground = true, Name = "ModFlowBridge.Accept" };
                    acceptThread.Start();
                    Log("listening on 127.0.0.1:" + Port + " for the OrderFlow Analysis suite");
                    try
                    {
                        NinjaTrader.Code.Output.Process(
                            "[ModFlow Bridge] listening on 127.0.0.1:" + Port + " (read-only market data)",
                            PrintTo.OutputTab1);
                    }
                    catch { }
                }
                catch (Exception ex)
                {
                    serverStarted = false;
                    // MEM-E-03: name the stale-copy case in the user's words. After an F5
                    // recompile the previous copy of this add-on can still own the port, so the
                    // freshly loaded one cannot bind; one bridge build installed at a time.
                    Log("SERVER FAILED to bind 127.0.0.1:" + Port + " — " + ex.Message +
                        " (after a NinjaScript recompile an earlier bridge copy can hold the port — " +
                        "restart NinjaTrader to clear it)");
                }
            }
        }

        private static void AcceptLoop()
        {
            while (true)
            {
                TcpClient incoming;
                try { incoming = listener.AcceptTcpClient(); }
                catch { return; }
                try
                {
                    AttachClient(incoming);
                }
                catch (Exception ex)
                {
                    Log("accept failed: " + ex.Message);
                }
            }
        }

        private static void AttachClient(TcpClient incoming)
        {
            // One reader at a time: a new connection replaces the old one.
            try { if (client != null) client.Close(); } catch { }
            try { if (sendQueue != null) sendQueue.CompleteAdding(); } catch { }

            incoming.NoDelay = true;
            client = incoming;
            var stream = incoming.GetStream();            // the writer owns this socket's stream
            var queue = new BlockingCollection<string>(new ConcurrentQueue<string>());
            sendQueue = queue;

            var writer = new Thread(() => WriterLoop(stream, queue)) { IsBackground = true, Name = "ModFlowBridge.Writer" };
            writer.Start();

            SubscribeCleanup();      // drop all subscriptions from the previous session
            SendHello();

            var reader = new Thread(() => ReaderLoop(incoming)) { IsBackground = true, Name = "ModFlowBridge.Reader" };
            reader.Start();
            StartHeartbeat();
            Log("client connected");
        }

        private static void ReaderLoop(TcpClient conn)
        {
            var stream = conn.GetStream();
            var buffer = new byte[8192];
            var pending = new List<byte>(65536);
            try
            {
                while (conn.Connected)
                {
                    int n = stream.Read(buffer, 0, buffer.Length);
                    if (n <= 0) break;
                    for (int i = 0; i < n; i++)
                    {
                        byte b = buffer[i];
                        if (b == 0)
                        {
                            if (pending.Count > 0)
                            {
                                HandleFrame(Encoding.UTF8.GetString(pending.ToArray()));
                                pending.Clear();
                            }
                        }
                        else
                        {
                            pending.Add(b);
                            if (pending.Count > (1 << 20)) pending.Clear();   // 1 MiB without a separator: drop
                        }
                    }
                }
            }
            catch { }
            finally
            {
                try { conn.Close(); } catch { }
                // MEM-E-01: the session's own teardown. Without it the subscriptions stayed
                // attached and the writer's queue was neither drained nor completed, so the
                // platform kept serialising market data into a queue nobody reads (the leak
                // measured inside NinjaTrader, ~100-120 MB/h per instrument). Identity-guarded:
                // a client that has already been replaced must not tear down the new session.
                if (ReferenceEquals(client, conn))
                {
                    client = null;
                    var queue = sendQueue;
                    sendQueue = null;
                    try { if (queue != null) queue.CompleteAdding(); } catch { }
                    SubscribeCleanup();
                }
                Log("client disconnected");
            }
        }

        private static void WriterLoop(NetworkStream stream, BlockingCollection<string> queue)
        {
            try
            {
                foreach (string frame in queue.GetConsumingEnumerable())
                {
                    if (stream == null) break;
                    var payload = Encoding.UTF8.GetBytes(frame);
                    stream.Write(payload, 0, payload.Length);
                    stream.WriteByte(0);
                    stream.Flush();
                }
            }
            catch { }
            finally
            {
                try { if (stream != null) stream.Close(); } catch { }
            }
        }

        private static void Send(string json)
        {
            // MEM-E-01: a detached session must not be enqueued to either.
            var q = sendQueue;
            if (client == null || q == null || q.IsAddingCompleted) return;
            try { q.Add(json); } catch { }
        }

        private static void SendObj(object payload)
        {
            try { Send(Json.Serialize(payload)); } catch { }
        }

        private static void SendError(string requestId, string message)
        {
            SendObj(new { Type = "error", RequestId = requestId, Message = message, Ts = NowMs() });
        }

        private static long NowMs()
        {
            return DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();
        }

        private static void StartHeartbeat()
        {
            // MEM-E-02: one heartbeat per bridge, not one per accepted connection. The old
            // loop never exited (it waited on a queue that was never completed), so a session
            // with 24 reconnects left 24 live threads inside NinjaTrader. The loop now ends
            // when the client slot is empty, and Shutdown() interrupts the sleep.
            var existing = heartbeatThread;
            if (existing != null && existing.IsAlive) return;
            var t = new Thread(() =>
            {
                try
                {
                    while (client != null)
                    {
                        Thread.Sleep(HeartbeatMs);
                        var q = sendQueue;
                        if (q == null || q.IsAddingCompleted) return;
                        SendObj(new { Type = "heartbeat", Ts = NowMs() });
                    }
                }
                catch (ThreadInterruptedException) { /* Shutdown() asked the thread to stop */ }
                catch { }
            }) { IsBackground = true, Name = "ModFlowBridge.Heartbeat" };
            heartbeatThread = t;
            t.Start();
        }

        private static void SendHello()
        {
            try
            {
                List<object> connections = null;
                List<object> accounts = null;
                string ntVersion = "";
                try
                {
                    ntVersion = typeof(Instrument).Assembly.GetName().Version.ToString();
                }
                catch { }
                DispatcherRun(() =>
                {
                    connections = ConnectionList();
                    accounts = AccountList();
                }, 3000);
                SendObj(new
                {
                    Type = "hello",
                    Addon = AddonName,
                    Version = AddonVersion,
                    NT = ntVersion,
                    Machine = Environment.MachineName,
                    Port = Port,
                    Mode = "read-only",
                    Connection = connections == null || connections.Count == 0 ? null : connections[0],
                    Connections = connections ?? new List<object>(),
                    Accounts = accounts ?? new List<object>(),
                    Ts = NowMs(),
                });
            }
            catch (Exception ex)
            {
                Log("hello failed: " + ex.Message);
            }
        }

        private static List<object> ConnectionList()
        {
            var rows = new List<object>();
            try
            {
                foreach (var conn in Connection.Connections)
                {
                    if (conn == null) continue;
                    string name = "";
                    try { name = conn.Options == null ? "" : conn.Options.Name; } catch { }
                    rows.Add(new { Name = name ?? "", Status = conn.Status.ToString() });
                }
            }
            catch { }
            return rows;
        }

        private static List<object> AccountList()
        {
            var rows = new List<object>();
            try
            {
                foreach (var account in Account.All)
                {
                    if (account == null) continue;
                    string connName = "";
                    string status = "Disconnected";
                    bool sim = false;
                    try { connName = account.Connection == null || account.Connection.Options == null ? "" : account.Connection.Options.Name; } catch { }
                    try { status = account.Connection == null ? "Disconnected" : account.Connection.Status.ToString(); } catch { }
                    try { sim = account.Name != null && account.Name.StartsWith("Sim", StringComparison.OrdinalIgnoreCase); } catch { }
                    rows.Add(new { Name = account.Name, Connection = connName ?? "", Status = status, Sim = sim });
                }
            }
            catch { }
            return rows;
        }

        // ── dispatcher helpers: run on the NT UI thread with a timeout, never deadlock ──
        private static void DispatcherRun(Action action, int timeoutMs)
        {
            try
            {
                var app = System.Windows.Application.Current;
                var dispatcher = app == null ? null : app.Dispatcher;
                if (dispatcher == null || dispatcher.CheckAccess()) { action(); return; }
                var op = dispatcher.InvokeAsync(action);
                op.Wait(TimeSpan.FromMilliseconds(timeoutMs));
                if (op.Status != System.Windows.Threading.DispatcherOperationStatus.Completed)
                    Log("dispatcher run timed out");
            }
            catch (Exception ex)
            {
                Log("dispatcher run failed: " + ex.Message);
            }
        }

        private static T DispatcherRead<T>(Func<T> read, int timeoutMs = 5000) where T : class
        {
            T result = null;
            var ran = false;
            DispatcherRun(() => { result = read(); ran = true; }, timeoutMs);
            return ran ? result : null;
        }

        private static void RunOnInstrumentThread(Instrument instrument, Action action)
        {
            try
            {
                if (instrument == null) return;
                if (instrument.Dispatcher == null || instrument.Dispatcher.HasShutdownStarted)
                {
                    action();
                    return;
                }
                var op = instrument.Dispatcher.InvokeAsync(action);
                op.Wait(TimeSpan.FromMilliseconds(5000));
                if (op.Status != System.Windows.Threading.DispatcherOperationStatus.Completed)
                    Log("instrument dispatcher timed out");
            }
            catch (Exception ex)
            {
                Log("instrument dispatch failed: " + ex.Message);
            }
        }

        // ── frame handling ──────────────────────────────────────────────────────────────
        private static void HandleFrame(string text)
        {
            Json.Obj msg;
            try { msg = Json.Obj.Parse(text); }
            catch { return; }                                       // not JSON: ignore, never crash the reader
            string type = msg.Str("Type", "type").Trim().ToLowerInvariant();
            string requestId = msg.Str("RequestId", "requestId");
            switch (type)
            {
                case "subscribe":    HandleSubscribe(msg, requestId); break;
                case "unsubscribe":  HandleUnsubscribe(msg); break;
                case "ping":         SendObj(new { Type = "pong", Ts = NowMs() }); break;
                case "quote":        HandleQuoteRequest(msg, requestId); break;
                case "instruments":  HandleInstruments(msg, requestId); break;
                case "bars":         HandleBars(msg, requestId); break;
                case "capabilities": HandleCapabilities(requestId); break;
                case "resolve":      HandleResolve(msg, requestId); break;
                default: break;                                     // unknown: ignored, never an error
            }
        }

        private static Instrument FindInstrument(string name)
        {
            if (string.IsNullOrWhiteSpace(name)) return null;
            var tries = new List<string>();
            var raw = name.Trim();
            tries.Add(raw);
            if (raw != raw.ToUpperInvariant()) tries.Add(raw.ToUpperInvariant());
            var trimmed = raw.TrimEnd('!');
            if (trimmed != raw) tries.Add(trimmed);
            if (trimmed.EndsWith("1") && trimmed.Length > 2)
                tries.Add(trimmed.Substring(0, trimmed.Length - 1));   // NQ1 / NQ1! → NQ
            foreach (var candidate in tries)
            {
                try
                {
                    // A bare root can collide with a stock ticker (ES → Eversource Energy): when the
                    // name is also a futures root, the terminal's own rolling front month wins.
                    if (candidate.IndexOf(' ') < 0)
                    {
                        var front = ResolveFrontMonth(candidate);
                        if (front != null) return front;
                    }
                    var exact = Instrument.GetInstrument(candidate);
                    if (exact != null) return exact;
                }
                catch { }
            }
            return null;
        }

        // The contract NinjaTrader itself would chart for a bare root: the nearest expiry whose
        // roll date (expiry − 8 days, the platform's roll window) has not passed. Candidates use
        // the platform's own naming ("NQ DEC26"); months without a contract simply miss.
        private static Instrument ResolveFrontMonth(string root)
        {
            if (futureRoots == null)
            {
                var set = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
                try
                {
                    foreach (var master in MasterInstrument.All)
                    {
                        if (master.InstrumentType == InstrumentType.Future) set.Add(master.Name);
                    }
                }
                catch { }
                futureRoots = set;
            }
            if (!futureRoots.Contains(root)) return null;

            var now = DateTime.Now;
            string fromCalendar = FrontMonthFromRolloverCalendar(root, now);
            if (fromCalendar != null)
            {
                try
                {
                    var inst = Instrument.GetInstrument(fromCalendar);
                    if (inst != null) return inst;          // the platform's own front month
                }
                catch { }
            }
            var first = new DateTime(now.Year, now.Month, 1);
            for (int m = 0; m <= 18; m++)
            {
                var month = first.AddMonths(m);
                string candidate = root.ToUpperInvariant() + " " +
                    month.ToString("MMM", CultureInfo.InvariantCulture).ToUpperInvariant() +
                    month.ToString("yy", CultureInfo.InvariantCulture);
                try
                {
                    var inst = Instrument.GetInstrument(candidate);
                    if (inst == null) continue;
                    DateTime expiry;
                    try { expiry = inst.Expiry; } catch { continue; }
                    if (expiry == default(DateTime) || expiry.Year > 2060) continue; // 2099 placeholders
                    if (expiry.AddDays(-8) >= now) return inst;                      // nearest live contract
                }
                catch { }
            }
            return null;
        }

        // The platform's own roll calendar decides the front month: the entry whose roll date is
        // the latest one not in the future identifies the contract NinjaTrader would chart now.
        private static string FrontMonthFromRolloverCalendar(string root, DateTime now)
        {
            MasterInstrument master = null;
            try
            {
                foreach (var m in MasterInstrument.All)
                {
                    if (string.Equals(m.Name, root, StringComparison.OrdinalIgnoreCase) &&
                        m.InstrumentType == InstrumentType.Future)
                    { master = m; break; }
                }
            }
            catch { }
            if (master == null) return null;
            try
            {
                var bestDate = DateTime.MinValue;
                var bestMonth = default(DateTime);
                foreach (object entry in (System.Collections.IEnumerable)master.RolloverCollection)
                {
                    if (entry == null) continue;
                    var entryType = entry.GetType();
                    var dateProp = entryType.GetProperty("Date");
                    var monthProp = entryType.GetProperty("ContractMonth");
                    var riskProp = entryType.GetProperty("IsRiskManagementOnly");
                    if (dateProp == null || monthProp == null) continue;
                    if (riskProp != null && (bool)riskProp.GetValue(entry, null)) continue;
                    var date = (DateTime)dateProp.GetValue(entry, null);
                    if (date <= now && date > bestDate)
                    {
                        bestDate = date;
                        bestMonth = (DateTime)monthProp.GetValue(entry, null);
                    }
                }
                if (bestMonth != default(DateTime))
                {
                    return root.ToUpperInvariant() + " " +
                        bestMonth.ToString("MMM", CultureInfo.InvariantCulture).ToUpperInvariant() +
                        bestMonth.ToString("yy", CultureInfo.InvariantCulture);
                }
            }
            catch { }
            return null;
        }

        private sealed class Sub
        {
            public readonly Instrument Instrument;
            public bool MarketHooked;
            public bool DepthHooked;
            public long LastQuoteMs;

            public Sub(Instrument instrument) { Instrument = instrument; }

            public void OnMarketData(object sender, MarketDataEventArgs e)
            {
                try
                {
                    if (e.MarketDataType == MarketDataType.Last)
                    {
                        double bid = 0, ask = 0;
                        try { bid = Instrument.MarketData.Bid.Price; } catch { }
                        try { ask = Instrument.MarketData.Ask.Price; } catch { }
                        string aggressor = "";
                        if (ask > 0 && e.Price >= ask) aggressor = "buy";
                        else if (bid > 0 && e.Price <= bid) aggressor = "sell";
                        SendObj(new
                        {
                            Type = "trade",
                            Instrument = Instrument.FullName,
                            Price = e.Price,
                            Size = e.Volume,
                            Aggressor = aggressor,
                            Ts = NowMs(),
                        });
                    }
                    else if (e.MarketDataType == MarketDataType.Bid || e.MarketDataType == MarketDataType.Ask)
                    {
                        long now = NowMs();
                        if (now - LastQuoteMs < QuoteThrottleMs) return;
                        LastQuoteMs = now;
                        SendQuote(Instrument);
                    }
                }
                catch { }
            }

            public void OnMarketDepth(object sender, MarketDepthEventArgs e)
            {
                try
                {
                    Interlocked.Increment(ref depthEventCount);
                    SendObj(new
                    {
                        Type = "depth",
                        Instrument = Instrument.FullName,
                        Side = e.MarketDataType == MarketDataType.Ask ? "ask" : "bid",
                        Price = e.Price,
                        Size = e.Volume,
                        Operation = e.Operation.ToString().ToLowerInvariant(),
                        Position = e.Position,
                        Ts = NowMs(),
                    });
                }
                catch { }
            }
        }

        private static void HandleSubscribe(Json.Obj msg, string requestId)
        {
            string name = msg.Str("Instrument", "instrument");
            var channels = msg.StrList("Channels", "channels");
            bool wantQuote = true, wantTrade = true, wantDepth = false;
            if (channels.Count > 0)
            {
                var set = new HashSet<string>(channels.Select(c => c.ToLowerInvariant()));
                wantQuote = set.Contains("quote");
                wantTrade = set.Contains("trade");
                wantDepth = set.Contains("depth");
            }

            var instrument = FindInstrument(name);
            if (instrument == null)
            {
                SendError(requestId, "instrument not found in NinjaTrader: " + name);
                return;
            }

            var sub = Subs.GetOrAdd(instrument.FullName, _ => new Sub(instrument));
            if ((wantQuote || wantTrade) && !sub.MarketHooked)
            {
                RunOnInstrumentThread(instrument, () => { instrument.MarketData.Update += sub.OnMarketData; });
                sub.MarketHooked = true;
            }
            if (wantDepth && !sub.DepthHooked)
            {
                RunOnInstrumentThread(instrument, () => { instrument.MarketDepth.Update += sub.OnMarketDepth; });
                sub.DepthHooked = true;
            }

            // Snapshot right after subscribing — the documented platform behaviour
            // ("Snapshot data is provided right on subscription").
            RunOnInstrumentThread(instrument, () =>
            {
                SendQuote(instrument);
                if (wantDepth) SendDepthSnapshot(instrument, requestId);
            });
            Log("subscribed " + instrument.FullName + (wantDepth ? " (+depth)" : ""));
        }

        private static void HandleUnsubscribe(Json.Obj msg)
        {
            string name = msg.Str("Instrument", "instrument");
            var instrument = FindInstrument(name);
            if (instrument == null) return;
            Sub sub;
            if (Subs.TryRemove(instrument.FullName, out sub)) Detach(sub);
        }

        private static void Detach(Sub sub)
        {
            RunOnInstrumentThread(sub.Instrument, () =>
            {
                if (sub.MarketHooked)
                {
                    sub.Instrument.MarketData.Update -= sub.OnMarketData;
                    sub.MarketHooked = false;
                }
                if (sub.DepthHooked)
                {
                    sub.Instrument.MarketDepth.Update -= sub.OnMarketDepth;
                    sub.DepthHooked = false;
                }
            });
        }

        private static void SubscribeCleanup()
        {
            foreach (var key in Subs.Keys.ToList())
            {
                Sub sub;
                if (Subs.TryRemove(key, out sub)) Detach(sub);
            }
        }

        private static void SendQuote(Instrument instrument)
        {
            try
            {
                var md = instrument.MarketData;
                SendObj(new
                {
                    Type = "quote",
                    Instrument = instrument.FullName,
                    Last = Safe(() => md.Last.Price),
                    LastSize = (long)Safe(() => md.Last.Volume),
                    Bid = Safe(() => md.Bid.Price),
                    BidSize = (long)Safe(() => md.Bid.Volume),
                    Ask = Safe(() => md.Ask.Price),
                    AskSize = (long)Safe(() => md.Ask.Volume),
                    Volume = (long)Safe(() => md.DailyVolume.Volume),
                    High = Safe(() => md.DailyHigh.Price),
                    Low = Safe(() => md.DailyLow.Price),
                    Opening = Safe(() => md.Opening.Price),
                    Settlement = Safe(() => md.Settlement.Price),
                    Ts = NowMs(),
                });
            }
            catch (Exception ex)
            {
                Log("quote snapshot failed for " + instrument.FullName + ": " + ex.Message);
            }
        }

        private static void SendDepthSnapshot(Instrument instrument, string requestId)
        {
            try
            {
                var bids = new List<object[]>();
                var asks = new List<object[]>();
                var depth = instrument.MarketDepth;
                for (int i = 0; i < depth.Bids.Count && i < 50; i++)
                    bids.Add(new object[] { depth.Bids[i].Price, depth.Bids[i].Volume });
                for (int i = 0; i < depth.Asks.Count && i < 50; i++)
                    asks.Add(new object[] { depth.Asks[i].Price, depth.Asks[i].Volume });
                SendObj(new
                {
                    Type = "depthsnapshot",
                    Instrument = instrument.FullName,
                    RequestId = requestId,
                    Bids = bids,
                    Asks = asks,
                    Ts = NowMs(),
                });
            }
            catch (Exception ex)
            {
                Log("depth snapshot failed for " + instrument.FullName + ": " + ex.Message);
            }
        }

        private static double Safe(Func<double> read)
        {
            try { return read(); } catch { return 0.0; }
        }

        private static void HandleQuoteRequest(Json.Obj msg, string requestId)
        {
            string name = msg.Str("Instrument", "instrument");
            var instrument = FindInstrument(name);
            if (instrument == null)
            {
                SendError(requestId, "instrument not found in NinjaTrader: " + name);
                return;
            }
            RunOnInstrumentThread(instrument, () =>
            {
                try
                {
                    var md = instrument.MarketData;
                    SendObj(new
                    {
                        Type = "quote",
                        RequestId = requestId,
                        Instrument = instrument.FullName,
                        Last = Safe(() => md.Last.Price),
                        Bid = Safe(() => md.Bid.Price),
                        BidSize = (long)Safe(() => md.Bid.Volume),
                        Ask = Safe(() => md.Ask.Price),
                        AskSize = (long)Safe(() => md.Ask.Volume),
                        Volume = (long)Safe(() => md.DailyVolume.Volume),
                        Ts = NowMs(),
                    });
                }
                catch (Exception ex)
                {
                    SendError(requestId, "quote failed: " + ex.Message);
                }
            });
        }

        private static void HandleResolve(Json.Obj msg, string requestId)
        {
            string name = msg.Str("Instrument", "instrument");
            var instrument = FindInstrument(name);
            if (instrument == null)
            {
                SendObj(new { Type = "resolve", RequestId = requestId, Instrument = name, Resolved = "", Root = "", Front = false, Ts = NowMs() });
                return;
            }
            string root = "";
            try { root = instrument.MasterInstrument.Name; } catch { }
            SendObj(new { Type = "resolve", RequestId = requestId, Instrument = name, Resolved = instrument.FullName, Root = root, Front = true, Ts = NowMs() });
        }

        private static void HandleInstruments(Json.Obj msg, string requestId)
        {
            string filter = msg.Str("Filter", "filter");
            string kind = msg.Str("Kind", "kind");
            filter = (filter ?? "").Trim().ToUpperInvariant();
            kind = (kind ?? "").Trim().ToUpperInvariant();

            var rows = DispatcherRead(() =>
            {
                var output = new List<object>();
                foreach (var master in MasterInstrument.All)
                {
                    if (master == null) continue;
                    if (kind.Length > 0 && !string.Equals(master.InstrumentType.ToString(), kind, StringComparison.OrdinalIgnoreCase)) continue;
                    var name = master.Name ?? "";
                    var desc = "";
                    try { desc = master.Description ?? ""; } catch { }
                    if (filter.Length > 0
                        && name.IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0
                        && desc.IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0) continue;
                    if (output.Count >= MaxInstruments) break;
                    string fullName = name;
                    string expiry = "";
                    try
                    {
                        var instrument = Instrument.GetInstrument(name);
                        if (instrument != null)
                        {
                            fullName = instrument.FullName;
                            try { expiry = instrument.Expiry == default(DateTime) ? "" : instrument.Expiry.ToString("yyyy-MM-dd"); } catch { }
                        }
                    }
                    catch { }
                    double tickSize = 0, pointValue = 0;
                    try { tickSize = master.TickSize; } catch { }
                    try { pointValue = master.PointValue; } catch { }
                    output.Add(new
                    {
                        Name = fullName,
                        Root = name,
                        Kind = master.InstrumentType.ToString(),
                        TickSize = tickSize,
                        PointValue = pointValue,
                        Expiry = expiry,
                        Description = desc,
                    });
                }
                return output;
            }, 15000);

            if (rows == null)
            {
                SendError(requestId, "the instrument database did not answer in time");
                return;
            }
            SendObj(new { Type = "instruments", RequestId = requestId, Instruments = rows, Ts = NowMs() });
        }

        private static BarsPeriodType ParsePeriod(string period)
        {
            switch ((period ?? "").Trim().ToLowerInvariant())
            {
                case "minute": return BarsPeriodType.Minute;
                case "day": return BarsPeriodType.Day;
                case "second": return BarsPeriodType.Second;
                case "tick": return BarsPeriodType.Tick;
                case "volume": return BarsPeriodType.Volume;
                case "range": return BarsPeriodType.Range;
                default: return BarsPeriodType.Minute;
            }
        }

        private static void HandleBars(Json.Obj msg, string requestId)
        {
            string name = msg.Str("Instrument", "instrument");
            var instrument = FindInstrument(name);
            if (instrument == null)
            {
                SendError(requestId, "instrument not found in NinjaTrader: " + name);
                return;
            }
            int count = Math.Max(1, Math.Min(MaxBars, msg.Int(300, "Count", "count")));
            var periodType = ParsePeriod(msg.Str("Period", "period", "Minute"));
            int interval = Math.Max(1, msg.Int(1, "Interval", "interval"));

            RunOnInstrumentThread(instrument, () =>
            {
                try
                {
                    var request = new BarsRequest(instrument, count);
                    request.BarsPeriod = new BarsPeriod { BarsPeriodType = periodType, Value = interval };
                    if (instrument.MasterInstrument.TradingHours != null)
                        request.TradingHours = instrument.MasterInstrument.TradingHours;
                    request.Request((req, errorCode, errorMessage) =>
                    {
                        try
                        {
                            if (errorCode != ErrorCode.NoError)
                            {
                                SendError(requestId, "bars request failed: " + errorMessage);
                            }
                            else
                            {
                                var bars = new List<object>();
                                for (int i = 0; i < req.Bars.Count; i++)
                                {
                                    var timeUtc = DateTime.SpecifyKind(req.Bars.GetTime(i), DateTimeKind.Local).ToUniversalTime();
                                    bars.Add(new
                                    {
                                        T = (timeUtc - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalMilliseconds,
                                        O = req.Bars.GetOpen(i),
                                        H = req.Bars.GetHigh(i),
                                        L = req.Bars.GetLow(i),
                                        C = req.Bars.GetClose(i),
                                        V = req.Bars.GetVolume(i),
                                    });
                                }
                                SendObj(new { Type = "bars", RequestId = requestId, Instrument = instrument.FullName, Bars = bars, Ts = NowMs() });
                            }
                        }
                        catch (Exception ex)
                        {
                            SendError(requestId, "bars failed: " + ex.Message);
                        }
                        finally
                        {
                            try { req.Dispose(); } catch { }
                        }
                    });
                }
                catch (Exception ex)
                {
                    SendError(requestId, "bars failed: " + ex.Message);
                }
            });
        }

        private static void HandleCapabilities(string requestId)
        {
            List<object> connections = null;
            List<object> accounts = null;
            DispatcherRun(() =>
            {
                connections = ConnectionList();
                accounts = AccountList();
            }, 5000);
            SendObj(new
            {
                Type = "capabilities",
                RequestId = requestId,
                NT = SafeString(() => typeof(Instrument).Assembly.GetName().Version.ToString()),
                Machine = Environment.MachineName,
                Connections = connections ?? new List<object>(),
                Accounts = accounts ?? new List<object>(),
                OrderFlowPlus = "unknown",
                Depth = new { Enabled = true, Events = Interlocked.Read(ref depthEventCount) },
                Subscribed = Subs.Keys.ToList(),
                Port = Port,
                Mode = "read-only",
                Ts = NowMs(),
            });
        }

        private static string SafeString(Func<string> read)
        {
            try { return read(); } catch { return ""; }
        }

        // ── lifecycle helpers ───────────────────────────────────────────────────────────
        private static void Shutdown()
        {
            try { SubscribeCleanup(); } catch { }
            try { if (client != null) client.Close(); } catch { }
            client = null;
            try
            {
                var hb = heartbeatThread;
                if (hb != null && hb.IsAlive) hb.Interrupt();      // MEM-E-02
            }
            catch { }
            try { if (listener != null) listener.Stop(); } catch { }
            Log("bridge stopped");
        }

        private static void Log(string message)
        {
            try
            {
                var dir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ModFlow");
                Directory.CreateDirectory(dir);
                var path = Path.Combine(dir, "ntbridge.log");
                try
                {
                    var info = new FileInfo(path);
                    if (info.Exists && info.Length > 4 * 1024 * 1024) File.Delete(path);
                }
                catch { }
                File.AppendAllText(path, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff") + " | " + message + "\r\n");
            }
            catch { }
        }
    }
}
