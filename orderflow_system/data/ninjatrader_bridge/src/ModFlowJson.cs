// ModFlowJson.cs — a tiny, dependency-free JSON layer for the ModFlow bridge.
//
// Why it exists: NinjaScript's compiler does not reference Newtonsoft.Json by default, and an
// add-on that compiles in EVERY NinjaTrader install beats one that needs a reference added by
// hand. Scope: exactly what this bridge's wire needs — serializing the outbound frames
// (anonymous objects, dictionaries, lists, primitives) and parsing the inbound flat command
// objects (keys case-insensitive, missing keys read as null/fallback, never throws on access).

using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Reflection;
using System.Text;

namespace ModFlow.Bridge
{
    internal static class Json
    {
        // ── writing ─────────────────────────────────────────────────────────────────────
        public static string Serialize(object value)
        {
            var sb = new StringBuilder(256);
            Write(sb, value);
            return sb.ToString();
        }

        private static void Write(StringBuilder sb, object value)
        {
            if (value == null) { sb.Append("null"); return; }

            if (value is string str) { WriteString(sb, str); return; }
            if (value is bool flag) { sb.Append(flag ? "true" : "false"); return; }
            if (value is int || value is long || value is short || value is byte || value is uint || value is ulong)
            {
                sb.Append(Convert.ToString(value, CultureInfo.InvariantCulture));
                return;
            }
            if (value is float || value is double || value is decimal)
            {
                double d = Convert.ToDouble(value, CultureInfo.InvariantCulture);
                sb.Append(double.IsNaN(d) || double.IsInfinity(d)
                    ? "null" : d.ToString("R", CultureInfo.InvariantCulture));
                return;
            }
            if (value is DateTime dt)
            {
                WriteString(sb, dt.ToString("yyyy-MM-dd HH:mm:ss.fff", CultureInfo.InvariantCulture));
                return;
            }

            if (value is IDictionary<string, object> map)
            {
                sb.Append('{');
                bool first = true;
                foreach (var kv in map)
                {
                    if (!first) sb.Append(',');
                    first = false;
                    WriteString(sb, kv.Key);
                    sb.Append(':');
                    Write(sb, kv.Value);
                }
                sb.Append('}');
                return;
            }
            if (value is IEnumerable items)
            {
                sb.Append('[');
                bool first = true;
                foreach (var item in items)
                {
                    if (!first) sb.Append(',');
                    first = false;
                    Write(sb, item);
                }
                sb.Append(']');
                return;
            }

            // anonymous objects / plain classes: public properties, declaration order
            sb.Append('{');
            PropertyInfo[] props = value.GetType().GetProperties(BindingFlags.Public | BindingFlags.Instance);
            for (int i = 0; i < props.Length; i++)
            {
                if (i > 0) sb.Append(',');
                WriteString(sb, props[i].Name);
                sb.Append(':');
                Write(sb, props[i].GetValue(value, null));
            }
            sb.Append('}');
        }

        private static void WriteString(StringBuilder sb, string s)
        {
            sb.Append('"');
            foreach (char c in s)
            {
                switch (c)
                {
                    case '"': sb.Append("\\\""); break;
                    case '\\': sb.Append("\\\\"); break;
                    case '\b': sb.Append("\\b"); break;
                    case '\f': sb.Append("\\f"); break;
                    case '\n': sb.Append("\\n"); break;
                    case '\r': sb.Append("\\r"); break;
                    case '\t': sb.Append("\\t"); break;
                    default:
                        if (c < 0x20) sb.Append("\\u").Append(((int)c).ToString("x4"));
                        else sb.Append(c);
                        break;
                }
            }
            sb.Append('"');
        }

        // ── reading: a flat command object; keys case-insensitive ──────────────────────
        internal sealed class Obj
        {
            private readonly Dictionary<string, object> map;

            private Obj(Dictionary<string, object> map) { this.map = map; }

            public static Obj Parse(string text)
            {
                int pos = 0;
                if (!(ParseValue(text, ref pos) is Obj obj)) throw new FormatException("not a JSON object");
                return obj;
            }

            public object this[string key]
            {
                get { object v; return map.TryGetValue(key, out v) ? v : null; }
            }

            private object Get(string key, string alt)
            {
                object v;
                if (map.TryGetValue(key, out v)) return v;
                if (alt != null && map.TryGetValue(alt, out v)) return v;
                return null;
            }

            public string Str(string key, string alt = null, string fallback = "")
            {
                object v = Get(key, alt);
                if (v == null) return fallback;
                if (v is string s) return s;
                return Convert.ToString(v, CultureInfo.InvariantCulture) ?? fallback;
            }

            public int Int(int fallback, string key, string alt = null)
            {
                object v = Get(key, alt);
                if (v == null) return fallback;
                try { return Convert.ToInt32(v, CultureInfo.InvariantCulture); }
                catch { return fallback; }
            }

            public List<string> StrList(string key, string alt = null)
            {
                var outList = new List<string>();
                object v = Get(key, alt);
                if (v is List<object> items)
                    foreach (object item in items)
                        outList.Add(Convert.ToString(item, CultureInfo.InvariantCulture) ?? "");
                return outList;
            }

            private static object ParseValue(string t, ref int i)
            {
                SkipWs(t, ref i);
                if (i >= t.Length) throw new FormatException("unexpected end");
                char c = t[i];
                if (c == '{')
                {
                    i++;
                    var map = new Dictionary<string, object>(StringComparer.OrdinalIgnoreCase);
                    SkipWs(t, ref i);
                    if (i < t.Length && t[i] == '}') { i++; return new Obj(map); }
                    while (true)
                    {
                        SkipWs(t, ref i);
                        if (i >= t.Length || t[i] != '"') throw new FormatException("key expected");
                        string key = ParseString(t, ref i);
                        SkipWs(t, ref i);
                        if (i >= t.Length || t[i] != ':') throw new FormatException("colon expected");
                        i++;
                        map[key] = ParseValue(t, ref i);
                        SkipWs(t, ref i);
                        if (i >= t.Length) throw new FormatException("unexpected end");
                        if (t[i] == ',') { i++; continue; }
                        if (t[i] == '}') { i++; return new Obj(map); }
                        throw new FormatException("',' or '}' expected");
                    }
                }
                if (c == '[')
                {
                    i++;
                    var list = new List<object>();
                    SkipWs(t, ref i);
                    if (i < t.Length && t[i] == ']') { i++; return list; }
                    while (true)
                    {
                        list.Add(ParseValue(t, ref i));
                        SkipWs(t, ref i);
                        if (i >= t.Length) throw new FormatException("unexpected end");
                        if (t[i] == ',') { i++; continue; }
                        if (t[i] == ']') { i++; return list; }
                        throw new FormatException("',' or ']' expected");
                    }
                }
                if (c == '"') return ParseString(t, ref i);
                if (StartsWith(t, i, "true")) { i += 4; return true; }
                if (StartsWith(t, i, "false")) { i += 5; return false; }
                if (StartsWith(t, i, "null")) { i += 4; return null; }
                return ParseNumber(t, ref i);
            }

            private static object ParseNumber(string t, ref int i)
            {
                int start = i;
                while (i < t.Length && (char.IsDigit(t[i]) || t[i] == '-' || t[i] == '+' ||
                                        t[i] == '.' || t[i] == 'e' || t[i] == 'E')) i++;
                if (i == start) throw new FormatException("number expected");
                string raw = t.Substring(start, i - start);
                long l;
                if (!raw.Contains(".") && !raw.Contains("e") && !raw.Contains("E") &&
                    long.TryParse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture, out l))
                    return l;
                double d;
                if (double.TryParse(raw, NumberStyles.Float, CultureInfo.InvariantCulture, out d))
                    return d;
                throw new FormatException("bad number: " + raw);
            }

            private static string ParseString(string t, ref int i)
            {
                if (t[i] != '"') throw new FormatException("string expected");
                i++;
                var sb = new StringBuilder();
                while (i < t.Length)
                {
                    char c = t[i++];
                    if (c == '"') return sb.ToString();
                    if (c != '\\') { sb.Append(c); continue; }
                    if (i >= t.Length) break;
                    char e = t[i++];
                    switch (e)
                    {
                        case '"': sb.Append('"'); break;
                        case '\\': sb.Append('\\'); break;
                        case '/': sb.Append('/'); break;
                        case 'b': sb.Append('\b'); break;
                        case 'f': sb.Append('\f'); break;
                        case 'n': sb.Append('\n'); break;
                        case 'r': sb.Append('\r'); break;
                        case 't': sb.Append('\t'); break;
                        case 'u':
                            if (i + 4 > t.Length) throw new FormatException("bad unicode escape");
                            sb.Append((char)Convert.ToInt32(t.Substring(i, 4), 16));
                            i += 4;
                            break;
                        default: sb.Append(e); break;
                    }
                }
                throw new FormatException("unterminated string");
            }

            private static void SkipWs(string t, ref int i)
            {
                while (i < t.Length && (t[i] == ' ' || t[i] == '\t' || t[i] == '\r' || t[i] == '\n')) i++;
            }

            private static bool StartsWith(string t, int i, string word)
            {
                return i + word.Length <= t.Length && string.CompareOrdinal(t, i, word, 0, word.Length) == 0;
            }
        }
    }
}
