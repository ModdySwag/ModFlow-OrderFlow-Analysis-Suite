package com.moddy.ofapbridge;

import velox.api.layer1.annotations.Layer1ApiVersion;
import velox.api.layer1.annotations.Layer1ApiVersionValue;
import velox.api.layer1.annotations.Layer1SimpleAttachable;
import velox.api.layer1.annotations.Layer1StrategyName;
import velox.api.layer1.data.InstrumentInfo;
import velox.api.layer1.data.TradeInfo;
import velox.api.layer1.simplified.Api;
import velox.api.layer1.simplified.CustomModuleAdapter;
import velox.api.layer1.simplified.DepthDataListener;
import velox.api.layer1.simplified.InitialState;
import velox.api.layer1.simplified.TradeDataListener;

import java.io.IOException;
import java.io.OutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;

/**
 * OFAP bridge — a read-only Bookmap add-on that republishes what Bookmap already has, on loopback,
 * in the frame format the MODDYS OrderFlow Analysis suite reads (see
 * orderflow_system/data/bookmap_client.py, which is the other end of this wire).
 *
 * It is deliberately small and passive:
 *   - it subscribes to two simplified-API listeners (trades and depth) and writes them out;
 *   - it never sends orders, never touches your account, and never writes anything into Bookmap;
 *   - it binds 127.0.0.1 only, so nothing leaves this machine.
 *
 * Written against the classes that ship inside the installed Bookmap
 * (bm-l1api.jar + bm-simplified-api-wrapper.jar, Bookmap 7.8.0 build:13):
 *   velox.api.layer1.annotations.Layer1SimpleAttachable / Layer1StrategyName / Layer1ApiVersion
 *   velox.api.layer1.simplified.{Api, CustomModuleAdapter, TradeDataListener, DepthDataListener}
 *   velox.api.layer1.data.{InstrumentInfo (info.pips), TradeInfo (isBidAggressor)}
 * The lifecycle and callback signatures are the ones Bookmap's own "Add-ons API" tutorial uses:
 *   initialize(String alias, InstrumentInfo info, Api api, InitialState initialState)
 *   onTrade(double price, int size, TradeInfo tradeInfo)
 *   onDepth(boolean isBid, int price, int size)          // price is in ticks — multiply by pips
 *
 * Build: see build.gradle in this folder (needs a JDK; Bookmap ships only a JRE).
 */
@Layer1SimpleAttachable
@Layer1StrategyName("OFAP bridge")
@Layer1ApiVersion(Layer1ApiVersionValue.VERSION2)
public class OfapBridge implements CustomModuleAdapter, TradeDataListener, DepthDataListener {

    /** The port the suite's "Test connection" defaults to; override with -Dofap.bridge.port=... */
    private static final int PORT = Integer.getInteger("ofap.bridge.port", 8791);
    private static final String ADDON = "ofap-bookmap-bridge";
    private static final String VERSION = "0.1";
    private static final long HEARTBEAT_MS = 5000;

    private String alias = "";
    private double minPriceIncrement = 0.01;     // InstrumentInfo.pips, straight from Bookmap
    private ServerSocket server;
    private Thread acceptThread;
    private Thread beatThread;
    private volatile Client client;
    private volatile boolean running;

    /** One connected reader (the suite). Writes are serialised so two callbacks cannot interleave. */
    private static final class Client {
        private final Socket socket;
        private final OutputStream out;
        private final Object lock = new Object();

        Client(Socket socket) throws IOException {
            this.socket = socket;
            this.out = socket.getOutputStream();
        }

        void send(String json) {
            synchronized (lock) {
                try {
                    out.write(json.getBytes(StandardCharsets.UTF_8));
                    out.write(0);                 // the NUL frame separator the suite splits on
                    out.flush();
                } catch (IOException e) {
                    close();
                }
            }
        }

        boolean alive() {
            return !socket.isClosed() && socket.isConnected();
        }

        void close() {
            try {
                socket.close();
            } catch (IOException ignored) {
                // the reader went away; nothing to do but forget it
            }
        }
    }

    // ── lifecycle ────────────────────────────────────────────────────────────────────────────

    @Override
    public void initialize(String alias, InstrumentInfo info, Api api, InitialState initialState) {
        this.alias = alias == null ? "" : alias;
        if (info != null && info.pips > 0) {
            this.minPriceIncrement = info.pips;
        }
        running = true;
        startServer();
        startHeartbeat();
    }

    @Override
    public void stop() {
        running = false;
        Client current = client;
        if (current != null) {
            current.send("{\"Type\":\"bye\"}");
            current.close();
            client = null;
        }
        try {
            if (server != null) {
                server.close();
                server = null;              // E-07: the closed listener is released, not retained
            }
        } catch (IOException ignored) {
            // closing a listener that is already gone is not an error worth reporting
        }
        if (acceptThread != null) {
            acceptThread.interrupt();
        }
        if (beatThread != null) {
            beatThread.interrupt();
        }
    }

    // ── the wire ─────────────────────────────────────────────────────────────────────────────

    private void startServer() {
        /* E-07: initialize() runs once per attached instrument — start the accept loop once, and
           only when the previous one is gone (the old shape leaked a thread per attach). */
        if (acceptThread != null && acceptThread.isAlive()) {
            return;
        }
        acceptThread = new Thread(new Runnable() {
            @Override
            public void run() {
                try {
                    server = new ServerSocket(PORT, 2, InetAddress.getByName("127.0.0.1"));
                } catch (IOException e) {
                    // Port busy is the common case (two charts open): say it once, stay quiet after.
                    System.out.println("[ofap-bridge] cannot bind 127.0.0.1:" + PORT + " — " + e.getMessage());
                    return;
                }
                System.out.println("[ofap-bridge] listening on 127.0.0.1:" + PORT
                        + " for the OrderFlow Analysis suite");
                while (running) {
                    try {
                        Socket socket = server.accept();
                        socket.setTcpNoDelay(true);
                        Client fresh = new Client(socket);
                        Client old = client;
                        if (old != null) {
                            old.close();
                        }
                        client = fresh;
                        fresh.send(hello());
                        System.out.println("[ofap-bridge] suite connected from " + socket.getRemoteSocketAddress());
                    } catch (IOException e) {
                        if (running) {
                            System.out.println("[ofap-bridge] accept stopped: " + e.getMessage());
                        }
                        return;
                    }
                }
            }
        }, "ofap-bridge-accept");
        acceptThread.setDaemon(true);
        acceptThread.start();
    }

    private void startHeartbeat() {
        if (beatThread != null && beatThread.isAlive()) {
            return;                         // E-07: one heartbeat per add-on, not one per attach
        }
        beatThread = new Thread(new Runnable() {
            @Override
            public void run() {
                while (running) {
                    try {
                        Thread.sleep(HEARTBEAT_MS);
                    } catch (InterruptedException e) {
                        return;
                    }
                    publish("{\"Type\":\"heartbeat\",\"Ts\":" + System.currentTimeMillis() + "}");
                }
            }
        }, "ofap-bridge-heartbeat");
        beatThread.setDaemon(true);
        beatThread.start();
    }

    private void publish(String json) {
        Client current = client;
        if (current == null || !current.alive()) {
            return;
        }
        current.send(json);
    }

    private String hello() {
        return "{\"Type\":\"hello\",\"Addon\":\"" + ADDON + "\",\"Version\":\"" + VERSION + "\","
                + "\"Bookmap\":\"" + System.getProperty("bookmap.version", "") + "\","
                + "\"Symbol\":\"" + escape(alias) + "\",\"Port\":" + PORT + "}";
    }

    // ── the two listeners ────────────────────────────────────────────────────────────────────

    @Override
    public void onTrade(double price, int size, TradeInfo tradeInfo) {
        String aggressor = "unknown";
        if (tradeInfo != null) {
            aggressor = tradeInfo.isBidAggressor ? "sell" : "buy";
        }
        publish("{\"Type\":\"trade\",\"Symbol\":\"" + escape(alias) + "\",\"Price\":" + price
                + ",\"Size\":" + size + ",\"Aggressor\":\"" + aggressor + "\""
                + ",\"Ts\":" + System.currentTimeMillis() + "}");
    }

    @Override
    public void onDepth(boolean isBid, int price, int size) {
        // onDepth gives prices in ticks; InstrumentInfo.pips is the increment, exactly as Bookmap's
        // own tutorial scales them (`minPriceIncrement = info.pips`).
        publish("{\"Type\":\"depth\",\"Symbol\":\"" + escape(alias) + "\",\"Side\":\""
                + (isBid ? "bid" : "ask") + "\",\"Price\":" + (price * minPriceIncrement)
                + ",\"Size\":" + size + ",\"Ts\":" + System.currentTimeMillis() + "}");
    }

    private static String escape(String text) {
        if (text == null) {
            return "";
        }
        StringBuilder out = new StringBuilder(text.length() + 8);
        for (int i = 0; i < text.length(); i++) {
            char c = text.charAt(i);
            if (c == '"' || c == '\\') {
                out.append('\\').append(c);
            } else if (c < 0x20) {
                out.append(String.format("\\u%04x", (int) c));
            } else {
                out.append(c);
            }
        }
        return out.toString();
    }
}
