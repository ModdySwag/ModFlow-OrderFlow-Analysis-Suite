// ModFlow Bridge — probe add-on (stage 1 of the NinjaTrader integration).
//
// Purpose: prove the whole pipeline end to end with the smallest possible surface:
//   1. this file compiles against NinjaTrader's own assemblies with the .NET SDK,
//   2. NinjaTrader loads a third-party DLL dropped into Documents\NinjaTrader 8\bin\Custom,
//   3. the loaded DLL can read the platform's live facts (instruments, accounts, the
//      MarketData/MarketDepth API surface) from inside the NT process.
//
// It writes everything it learns to %LOCALAPPDATA%\ModFlow\ntbridge-probe.log.
// Read-only: it subscribes to nothing and sends nothing.
//
// Replaced by the full bridge (ModFlowBridge.cs) once this stage is verified.

#region Using declarations
using System;
using System.Threading;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using NinjaTrader.Cbi;
using NinjaTrader.NinjaScript;
#endregion

namespace ModFlow.Bridge
{
    public class ModFlowProbe : AddOnBase
    {
        private static readonly object Gate = new object();
        private static bool dumped;

        // Same load-time kick as the bridge: proves "the assembly loaded at all" even when the
        // platform reloads it mid-session (NinjaScript editor compile) and no window event fires.
        static ModFlowProbe()
        {
            try
            {
                new Thread(() =>
                {
                    try
                    {
                        Thread.Sleep(4000);
                        lock (Gate)
                        {
                            if (dumped) return;
                            dumped = true;
                        }
                        W("=== ModFlow probe (assembly-load kick) ===");
                        Dump();
                    }
                    catch (Exception ex) { W("STATIC DUMP FAILED: " + ex); }
                }) { IsBackground = true, Name = "ModFlowProbe.LoadKick" }.Start();
            }
            catch { /* a probe must never take the platform down */ }
        }

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Description = "ModFlow Bridge probe — writes API facts to %LOCALAPPDATA%\\ModFlow\\ntbridge-probe.log";
                Name = "ModFlow Probe";
            }
        }

        protected override void OnWindowCreated(System.Windows.Window window)
        {
            lock (Gate)
            {
                if (dumped) return;
                dumped = true;
            }
            try { Dump(); }
            catch (Exception ex) { W("DUMP FAILED: " + ex); }
        }

        private static string LogPath()
        {
            string dir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "ModFlow");
            Directory.CreateDirectory(dir);
            return Path.Combine(dir, "ntbridge-probe.log");
        }

        private static void W(string line)
        {
            try { File.AppendAllText(LogPath(), DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff") + " | " + line + "\r\n"); }
            catch { /* a probe must never take the platform down */ }
        }

        private static void Dump()
        {
            W("=== ModFlow probe v1 ===");
            W("core assembly: " + typeof(Instrument).Assembly.FullName);
            W("running under: " + Environment.Version);

            foreach (string typeName in new[]
            {
                "NinjaTrader.Cbi.MarketData", "NinjaTrader.Cbi.MarketDepth",
                "NinjaTrader.Data.MarketDataEventArgs", "NinjaTrader.Data.MarketDepthEventArgs",
            })
            {
                Type t = FindType(typeName);
                W("TYPE " + typeName + " -> " + (t == null ? "NOT FOUND" : t.Assembly.GetName().Name + " public=" + t.IsPublic));
                if (t != null) DumpType(t);
            }

            DumpLicenseTypes();
            DumpAccounts();
            DumpInstrument("NQ");
            DumpInstrument("ES");
            DumpInstrument("AAPL");
            DumpRollFacts();
            W("=== probe end ===");
        }

        private static void DumpRollFacts()
        {
            W("-- rollover facts --");
            try
            {
                MasterInstrument master = null;
                foreach (var m in MasterInstrument.All)
                    if (string.Equals(m.Name, "NQ", StringComparison.OrdinalIgnoreCase)) { master = m; break; }
                if (master == null) { W("   NQ master not found"); return; }
                foreach (var prop in typeof(MasterInstrument).GetProperties())
                {
                    string val;
                    try { var v = prop.GetValue(master, null); val = v == null ? "null" : v.ToString(); }
                    catch (Exception ex) { val = "<" + ex.GetType().Name + ">"; }
                    if (val.Length > 90) val = val.Substring(0, 90);
                    W("   master." + prop.Name + " (" + prop.PropertyType.Name + ") = " + val);
                }
                ProbedRollovers(master);

                var inst = Instrument.GetInstrument("NQ DEC26");
                if (inst != null)
                {
                    foreach (var prop in typeof(Instrument).GetProperties())
                        if (prop.Name.IndexOf("Roll", StringComparison.OrdinalIgnoreCase) >= 0 ||
                            prop.Name.IndexOf("Expir", StringComparison.OrdinalIgnoreCase) >= 0 ||
                            prop.Name.IndexOf("Notice", StringComparison.OrdinalIgnoreCase) >= 0 ||
                            prop.Name.IndexOf("Days", StringComparison.OrdinalIgnoreCase) >= 0)
                        {
                            string val;
                            try { var v = prop.GetValue(inst, null); val = v == null ? "null" : v.ToString(); }
                            catch (Exception ex) { val = "<" + ex.GetType().Name + ">"; }
                            W("   inst." + prop.Name + " (" + prop.PropertyType.Name + ") = " + val);
                        }
                }
            }
            catch (Exception ex) { W("   roll facts failed: " + ex.Message); }
        }

        private static void ProbedRollovers(MasterInstrument master)
        {
            try
            {
                object rc = master.RolloverCollection;
                if (rc == null) { W("   rollovers: null"); return; }
                Type rcType = rc.GetType();
                W("   rollovers type: " + rcType.FullName + " base=" + (rcType.BaseType == null ? "?" : rcType.BaseType.Name));
                foreach (var p in rcType.GetProperties(BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly))
                    W("   rc.PROP " + p.PropertyType.Name + " " + p.Name);
                foreach (var mth in rcType.GetMethods(BindingFlags.Public | BindingFlags.Instance | BindingFlags.DeclaredOnly))
                {
                    if (mth.IsSpecialName) continue;
                    string sig = string.Join(", ", Array.ConvertAll(mth.GetParameters(), x => x.ParameterType.Name + " " + x.Name));
                    W("   rc.METHOD " + mth.Name + "(" + sig + ") -> " + mth.ReturnType.Name);
                }
                foreach (var iface in rcType.GetInterfaces())
                    W("   rc.IMPLEMENTS " + iface.Name);

                // concrete attempts, most-likely first
                foreach (var tryName in new[] { "GetRolloverDate", "GetNextRollover", "Get" })
                {
                    var mth = rcType.GetMethod(tryName, new[] { typeof(DateTime) });
                    if (mth == null) { mth = rcType.GetMethod(tryName); }
                    if (mth == null) continue;
                    try
                    {
                        object val = mth.GetParameters().Length == 0
                            ? mth.Invoke(rc, null)
                            : mth.Invoke(rc, new object[] { new DateTime(2026, 12, 1) });
                        W("   rc." + tryName + "() -> " + (val == null ? "null" : val.ToString()));
                    }
                    catch (Exception ex) { W("   rc." + tryName + " threw " + (ex.InnerException ?? ex).GetType().Name + ": " + (ex.InnerException ?? ex).Message); }
                    break;
                }
                var item = rcType.GetProperty("Item");
                if (item != null)
                {
                    var ps = item.GetIndexParameters();
                    W("   rc.Item indexer params: " + string.Join(", ", Array.ConvertAll(ps, x => x.ParameterType.Name)));
                    try
                    {
                        object val = ps.Length == 1 && ps[0].ParameterType == typeof(DateTime)
                            ? item.GetValue(rc, new object[] { new DateTime(2026, 12, 1) })
                            : null;
                        if (val != null) W("   rc[2026-12-01] -> " + val);
                    }
                    catch (Exception ex) { W("   rc[] threw " + (ex.InnerException ?? ex).GetType().Name); }
                }
                if (rc is System.Collections.IEnumerable seq)
                {
                    var all = new System.Collections.ArrayList();
                    foreach (object entry in seq) all.Add(entry);
                    W("   rc total entries: " + all.Count);
                    int from = Math.Max(0, all.Count - 9);      // the newest entries: the upcoming calendar
                    for (int i = from; i < all.Count; i++)
                    {
                        object entry = all[i];
                        if (entry == null) { W("   rc[" + i + "] null"); continue; }
                        var parts = new List<string>();
                        foreach (var p in entry.GetType().GetProperties(BindingFlags.Public | BindingFlags.Instance))
                        {
                            string v;
                            try { var val = p.GetValue(entry, null); v = val == null ? "null" : val.ToString(); }
                            catch (Exception ex) { v = "<" + ex.GetType().Name + ">"; }
                            parts.Add(p.Name + "=" + v);
                        }
                        W("   rc[" + i + "] " + string.Join(" | ", parts.ToArray()));
                    }
                }
            }
            catch (Exception ex) { W("   rollover introspection failed: " + ex.Message); }
        }

        private static Type FindType(string fullName)
        {
            foreach (Assembly asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                try
                {
                    Type t = asm.GetType(fullName, false);
                    if (t != null) return t;
                }
                catch { }
            }
            return null;
        }

        private static void DumpType(Type t)
        {
            foreach (EventInfo ev in t.GetEvents(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly))
                W("  EVENT " + ev.Name + " : " + (ev.EventHandlerType == null ? "?" : ev.EventHandlerType.Name));
            foreach (PropertyInfo p in t.GetProperties(BindingFlags.Public | BindingFlags.Instance | BindingFlags.Static | BindingFlags.DeclaredOnly))
                W("  PROP " + p.PropertyType.Name + " " + p.Name);
            try
            {
                foreach (ConstructorInfo c in t.GetConstructors(BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance))
                    W("  CTOR (" + string.Join(", ", c.GetParameters().Select(x => x.ParameterType.Name + " " + x.Name)) + ")");
            }
            catch { }
        }

        private static void DumpLicenseTypes()
        {
            W("-- licence-ish types in core --");
            try
            {
                Type[] types = typeof(Instrument).Assembly.GetTypes();
                foreach (Type t in types.Where(x => x.Name.IndexOf("License", StringComparison.OrdinalIgnoreCase) >= 0
                                                 || x.Name.IndexOf("Licence", StringComparison.OrdinalIgnoreCase) >= 0
                                                 || x.Name.IndexOf("Entitle", StringComparison.OrdinalIgnoreCase) >= 0))
                    W("  " + t.FullName + " public=" + t.IsPublic);
            }
            catch (ReflectionTypeLoadException ex)
            {
                foreach (Type t in (ex.Types ?? new Type[0]).Where(x => x != null && x.Name.IndexOf("License", StringComparison.OrdinalIgnoreCase) >= 0))
                    W("  (partial) " + t.FullName);
            }
            catch (Exception ex) { W("  licence scan failed: " + ex.GetType().Name); }
        }

        private static void DumpAccounts()
        {
            W("-- accounts --");
            try
            {
                foreach (object acc in (IEnumerable)Account.All)
                {
                    if (acc == null) continue;
                    string s = Describe(acc);
                    W("  " + s);
                }
            }
            catch (Exception ex) { W("  accounts failed: " + ex.GetType().Name + " " + ex.Message); }

            W("-- connections --");
            try
            {
                foreach (object conn in (IEnumerable)Connection.Connections)
                {
                    if (conn == null) continue;
                    W("  " + Describe(conn));
                }
            }
            catch (Exception ex) { W("  connections failed: " + ex.GetType().Name + " " + ex.Message); }
        }

        private static string Describe(object o)
        {
            var sb = new StringBuilder(o.GetType().FullName);
            foreach (string prop in new[] { "Name", "DisplayName", "Status", "IsSimAccount", "Provider" })
            {
                try
                {
                    PropertyInfo pi = o.GetType().GetProperty(prop);
                    if (pi != null) sb.Append(" | ").Append(prop).Append("=").Append(pi.GetValue(o, null));
                }
                catch { }
            }
            return sb.ToString();
        }

        private static void DumpInstrument(string name)
        {
            W("-- instrument " + name + " --");
            try
            {
                Instrument inst = Instrument.GetInstrument(name);
                if (inst == null) { W("  not found"); return; }
                W("  FullName=" + inst.FullName + " Expiry=" + inst.Expiry + " Exchange=" + Safe(() => inst.Exchange));
                var mi = inst.MasterInstrument;
                if (mi != null)
                {
                    W("  master.Name=" + mi.Name + " Type=" + mi.InstrumentType);
                    W("  master.TickSize=" + mi.TickSize + " PointValue=" + mi.PointValue);
                    W("  master.Description=" + mi.Description);
                }
                W("  MarketData type: " + SafeType(() => inst.MarketData));
                W("  MarketDepth type: " + SafeType(() => inst.MarketDepth));
            }
            catch (Exception ex) { W("  instrument failed: " + ex.GetType().Name + " " + ex.Message); }
        }

        private static string Safe(Func<object> f)
        {
            try { object v = f(); return v == null ? "(null)" : Convert.ToString(v); }
            catch { return "(err)"; }
        }

        private static string SafeType(Func<object> f)
        {
            try { object v = f(); return v == null ? "(null)" : v.GetType().FullName; }
            catch (Exception ex) { return "(err " + ex.GetType().Name + ")"; }
        }
    }
}
