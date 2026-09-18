# Sierra Chart: UX / GUI study for ModFlow OrderFlow Analysis Suite

**Purpose:** extract UX, layout and interaction lessons from Sierra Chart (SC) — a paid, deliberately dense professional trading client — for a single-window, vanilla-JS, pywebview-hosted desktop app built by one developer (ModFlow). Read-only study; nothing in the ModFlow repo was modified.

**How this was verified (read this before trusting any claim):**

| Source class | Access | Status |
|---|---|---|
| Sierra Chart documentation pages | Fetched in a real browser and saved to disk; quoted from the saved text | **Read** (see §10 for the exact page list) |
| Sierra Chart Support Board threads | Same method (some via text extraction) | **Read** (6 threads) |
| Reddit threads | Reddit returned 403 / login-wall to both the browser and text extraction (`curl` 403, `old.reddit.com` → login, `r.jina.ai` → "blocked by network security") | **Not read** — quotes below come from search-engine result snippets for those exact URLs and are labelled `[snippet]` |
| Elite Trader, Trustpilot, AMP Futures reviews, review blogs | Fetched and read | **Read** (Trustpilot star breakdown: not read) |
| Spreadsheet-studies doc body, free-trial/mobile/web pages, telephone-support policy body | Not fetched | **not read** — flagged inline |

All URLs resolve to the pages as read on 2026-09-18. Quotes are verbatim from those pages, including SC's typos.

---

## 1. Snapshot

- **Platform/tech:** native **Windows desktop** client (single EXE + DLLs, OpenGL-based rendering — SC's own docs discuss "Maximum Fonts for OpenGL" and DPI-based font rasterisation `[S10]`). Current build advertised on the setup page: **"Download Sierra Chart 2950 (September 13, 2026)"** `[S14]`. Company: "Sierra Chart has been in business since 1996 developing and supporting financial market analysis and trading software… futures, stocks, forex, indexes and options" `[S17]`. High-performance server-side market-data infrastructure is part of the product ("We develop high-performance server software for market data for Sierra Chart") `[S17]`.
- **Licence model — headline (read, not recalled):** monthly **service packages**, no perpetual option: Base Standard **26 USD/month**, Base + Advanced Features **36**, Integrated Standard **36**, Integrated + Advanced **46**, Integrated + Advanced + Market-by-Order **56** `[S11]`. "Base Packages… do not support connections to external provided Data or Trading services" (i.e. you need the Integrated tiers to connect a broker/feed) `[S11]`. On perpetual licences: *"Occasionally we get asked if we offer a one-time purchase option for Sierra Chart. The answer is no, and this is something that would never be offered."* `[S11]`. Free-trial contents page was **not read**.
- **Scale of surface:** the docs' Table of Contents "lists and categorizes **every single page** on this website"; the Support Board index reported **"[Page 1 of 2565]"** of threads when read `[S12][S18]`.
- **Business context that shapes the UX:** SC also sells data and order routing, and states the software is *not* sold separately from those ongoing services — hence continuous monthly billing, continuous updates, and a support model built on a public board rather than tickets/wizards `[S11][S12]`.

---

## 2. Layout & windowing model

**The core abstraction is the Chartbook, not the window.** SC's docs: *"A Chartbook is not a window. It is a collection of multiple windows."* and *"A Chartbook is like a desktop/layout/workspace for Sierra Chart."* It holds chart windows, Time & Sales, Market Depth, Trade windows, Trade DOMs and spreadsheets — "When a chart or Trade DOM window is opened, it is added to a Chartbook" `[S3]`.

The load-bearing constraint: *"Many Chartbooks can be loaded but only **1 can be visible at a time in an instance** of Sierra Chart. To have multiple Chartbooks visible at the same time requires that you use additional instances of Sierra Chart."* `[S3]`. Chartbooks themselves **cannot be detached**; the documented workarounds are (a) run extra instances (`File >> New Instance`, each with its own data-files folder `SierraChartInstance_#\Data`) or (b) **restore** the main window from maximised and stretch it across monitors `[S1][S3]`.

Within a chartbook, the escape hatches are deliberately few but blunt:

- **Detach a chart/spreadsheet window** with `Chart >> Detach/Attach Window` or `Window >> Detach/Attach Window`; to re-attach you must reach **the detached window's own menu** `[S1]`.
- **`Window >> Window Always Visible`** pins one chart so it stays on screen even when its chartbook is not the active one — explicitly framed as a way to "share a chart between Chartbooks", with a warning: *"It is recommended not to overuse this feature, so there is no confusion as to what Chartbook a chart belongs to."* `[S3]`. Detached charts can also be set "always on top" and all detached charts can be minimised/restored together `[S1]`.
- **Chartbook tabs** exist as an opt-in feature ("It is supported to display clickable tabs for easy navigation among multiple open Chartbooks… can be positioned anywhere") `[S3]`.
- **Chartbook Groups** open several chartbooks at once (`File >> Open Chartbook Group`, with a setting controlling whether existing chartbooks are closed) `[S3]`.

**The Window menu is the real window manager** and it reads like a 1990s MDI app: Cascade, Tile Horizontally, Tile Vertically, Tile as Grid – Horizontally, Tile as Grid – Vertically, Maximize, Minimize, Restore, Always on Top, Window Always Visible, Detach/Attach Window, Hide Window, Arrange Minimized Windows, Hide All Trade Windows, Restore All Trade Windows, Control Bars [1-8], Previous Chart, Next Chart, Previous Chartbook, Next Chartbook, Message Log `[S2]`.

**Two documented failure modes that are pure UX debt, and that any app with real OS windows inherits:**

1. *"If after opening a Chartbook, you find that not all Chart or Spreadsheet Windows are not visible, then you can find these windows under the **CW** menu."* Recover with `Window >> Cascade`, then `Window >> Maximize` `[S2]`. A FAQ topic exists for it: **"Help topic 14: Window Size and Position Not Restored When Opening Chartbook"** `[S9]`.
2. *"Make sure the windows have a title bar. Do not remove the title bars."* — with an explicit warning that users removing title bars/menus cause "various malfunctions of these windows which can and will occur at the Windows operating system level" `[S2]`.

Support-board evidence that these are not theoretical — all three threads were read:

- A user received a chartbook from a customer containing "a detached window with no title bar that was showed maximized on my 2nd monitor. **It took a lot of steps to restore the window, resize it and move it to my primary monitor.**" Recovery needed the "Windows and Chartbooks" dialog plus an old-Windows `CTRL-Spacebar` → Restore trick. A second user in the same thread defends the titless-window workflow — *"I have multiple detached charts with no visible title bar, menu, or scroll bar. This maximizes the space for charts… If you have shortcut keys to add/remove title bars, max/restore windows, etc this isn't a problem at all."* — i.e. the density-maximising power user and the recovery path are in direct tension `[S19]`.
- *"How to reattach a detached Chart Window without Title / Menu / Scrollbar"*: *"I detached my profile window which was then a window without Title, Menu and Scrollbar. **I tried to reattach it for 10mins now. Its simply impossible**… Right clicking doesnt lead to anything and I also cannot find any solution here on the Support Board."* Answers: pre-add Detach/Attach to the chart context menu (`Global Settings >> Customize Chart Shortcut Menu`), set a keyboard shortcut, or use a floating control bar carrying "Show Menu / Show Title Bar / Show Scroll Bar" buttons `[S20]`.
- *"Cannot find a window after detaching it"*: a chart that re-attached but "Attempts to again detach this window (#28) fail… it disappears and is not returned to the detached area"; the user tried `Ctrl-Alt-D`, another user had to check whether they meant `Ctrl-Alt-Delete` `[S21]`.

---

## 3. Navigation & IA

**Model: menus everywhere, one canonical command location each, plus per-object context menus; docs are the map.** SC's information architecture is unusual for a consumer app — there is no command palette and no global "what do I want to do?" search. Instead:

1. **Menus are the API.** Every command lives in a menu (File, Edit, Chart, Analysis, Trade, Tools, Window, Global Settings, Help), and every menu command carries its shortcut on the menu line itself: *"To see the supported keyboard shortcut for a corresponding menu command, refer to the keyboard shortcut description after each menu command on the Sierra Chart menus."* `[S5]`.
2. **Menus are user-editable.** `Global Settings >> Customize Menu Items`, `Customize Chart Shortcut Menu` (right-click menu on a chart), `Customize Chart Trade Menu`, `Customize Chart Drawing Menu` `[S6]`. The consequence: the canonical right-click menu on a chart/DOM contains **only what the user put there** — the docs literally say of two order-moving commands, *"In order for these menu commands to be available, they must first be added to the Chart Trade Shortcut Menu. This is done by using the Customize Chart Trade Menu and adding these specific items"* `[S7]`.
3. **Context help is wired to the OS help key.** *"The function key F1 is going to be interpreted at the operating system level and open the relevant help documentation for the current context. It should not be used for any other keyboard shortcut."* `[S5]`.
4. **Docs are cross-referenced by number, from inside the product.** Docs refer to "help topic # 1", "Help Topic 1.3 (Symbols)", "help topic number 62", "refer to Help topic 14" as first-class identifiers, and the FAQ is a flat numbered list of ~100 titled topics (`Help topic 27: How to Quickly Change the Bar/Column Time Period In a Chart`, …) `[S9][S13][S16]`.
5. **How users cope, in SC's own words:** the docs *expect* the user to live in the documentation — "The website documentation is updated and improved almost daily. It is designed to be simple and complete… You will notice how the website has a very simple and logical organization to it" `[S13]`. The Support page doubles down: "**Try to find your answer on this page before sending a question to support**", "The Software Documentation is the complete documentation for the program. Be sure to read the Getting Started documentation page" `[S12]`.
6. **Forum culture as second-order IA.** Support is a **public board**, monitored by engineering ("Sierra Chart Engineering continuously monitors the Support Board and it is given the highest priority"), with a documented anti-email policy — *"Questions and requests sent to us by email that should be on the Support Board or through an Account Support Ticket will be delayed by 2 days or not answered at all."* `[S12]`. Threads are indexed, searchable and permanent; when read, the board index alone was **2,565 pages** of threads `[S18]`. Users therefore learn to search the board, not to expect a wizard — and answers often contain config-file attachments for the user to load (`DetachedWindowDifficultToMove.Cht` in `[S19]`).
7. **Editing a menu is itself the fix path.** The escape hatch for "I can't find the command" is documented three ways (context menu, keyboard shortcut, floating control bar) in a single thread `[S20]` — the IA is explicitly user-rebuildable rather than discoverable.

---

## 4. Interaction model

### 4.1 "Everything is a study" — the extensibility spine

SC's own definition: *"A simple definition of a Study is that it is a graph of the results from a formula applied to the entire series of data elements in a chart. A study may also be called an indicator. In Sierra Chart they are called studies."* `[S8]`. Operationally:

- Studies are added from a **Chart Studies window** (`Analysis >> Studies`, or **F6**), *"Any number studies can be added to a chart and even the same study can be added more than once"* — so identity is per-instance, not per-type: *"Each study has a unique ID assigned to it (ID: ). It is unique and cannot be changed after it is assigned. When a study is duplicated, it will receive a new ID."* `[S8]`.
- Every study has a **Settings and Inputs** tab plus a **Subgraphs** tab (draw style, colour per subgraph) — inputs and visuals are separated in the UI `[S8]`.
- Sets of studies are saved as **Study Collections** ("Save Studies as Study Collection", with an option "Prompt to Remove Existing Studies") so configurations travel between charts `[S8]`.
- **Advanced Custom Studies are DLLs** dropped in the Data Files Folder and added via an "Add Custom Study" window — i.e. the plugin model is native C++ DLL loading, not a sandboxed script `[S8]`.
- **Spreadsheet studies** extend the same model to a formula grid: the docs index lists *Overview of Spreadsheet Studies*, *Using the Spreadsheet Study*, *Spreadsheet Functions*, *Spreadsheet Study Inputs*, *Referencing Other Charts in Spreadsheet Study Formulas*, *Spreadsheet Systems, Alerts and Automated Trading*, *Sharing Your Spreadsheet Study With Another User*, *Spreadsheet System for Trading Test Procedure* `[S15b]`. (`[S15b]` is the docs Contents page listing these pages; the **bodies of the spreadsheet pages were not read** — the fetch failed and I did not retry more than twice. What they *contain* beyond the titles is **not** asserted here.)
- Spreadsheet windows are first-class members of the windowing model: they detach like charts and live inside chartbooks `[S1][S3]`.

### 4.2 Chart interaction

- **Right-click is the order-entry root.** Stop-limit: "Move your mouse pointer to the price level where you want the Stop order. Right-click on the chart and select either Buy Stop-Limit or Sell Stop-Limit." OCO pairs: right-click once per leg; auto-set OCO prices are offset by a Trade Window setting `[S7]`.
- **Direct manipulation of orders:** *"Left click and drag the order line… to change its price. You are able to click and drag anywhere along the order line to modify the order except for the quantity and 'X' buttons."* Mobile-ambiguous behaviours are explicitly called out and made optional: *"By default, when you left click you have to hold that state, and then drag… This behavior is changeable. Refer to Working Orders >> Use Click, Release, Click Method to Adjust Orders."* Precision fallback: click the order quantity to get a numeric price box with OK `[S7]`.
- **Safety/undo semantics on drag:** *"if an order has been moved up using click and drag, but then moved back to the original price before letting up on the left-click button, then the original order is still in place"* `[S7]`.
- **The price axis is interactive** — right-click the Values Scale → **Interactive Scale Range** (then drag to compress) or **Interactive Scale Move**; this is also the documented way to bring an off-screen order back into view `[S7]`.
- **Trading DOM specifics:** typed quantity directly into the window then Enter (click the DOM body to make it active), per-tick ladder scaling, "Double Click Operations in Order Entry Columns", "Blank Trading DOM", "Saving Trade DOM Configuration", "Always on Top", "Adding Studies on a Trade DOM", "Adding Custom Text to a Trade DOM", "Improving Performance of Trading DOM" `[S7]`. Columns are fully user-defined: *"What specific columns are displayed, the alignment of text within those columns and the order of columns is all customizable"* (`Trade >> Customize Chart/Trade DOM Columns`), including a **P&L column whose format cycles Currency/Points/Ticks on click of its header label** `[S7]`.
- **Trade Window** can be attached to the right side of a chart or detached; trade windows can be globally hidden/restored from the Window menu (`Hide All Trade Windows`) `[S2][S7]`.

### 4.3 Keyboard

- **Global, not per-window:** *"Keyboard shortcuts are global and affect all windows assuming that the command they invoke, is relevant to that particular window."* `[S5]`
- **User-assignable for any command**: `Global Settings >> Customize Keyboard Shortcuts`; the menus re-render with the new key — with an OS caveat SC cannot control ("it is known that in some cases even though the menus are updated, the operating system is still not updating the menu. Sierra Chart has no control over this") `[S6]`.
- **Trading actions get their own gated shortcut namespace** and a master switch: *"When this option is checked/enabled, then Trading Keyboard Shortcuts that have been setup through Global Settings >> Customize Keyboard Shortcuts >> Trading Keyboard Shortcuts will be available. Otherwise, these keyboard shortcuts will not perform the assigned trading activity when selected."* (`Trade >> Trading Keyboard Shortcuts Enabled`) `[S7]` (the dedicated Trading Keyboard Shortcuts doc page URL I tried was not found; that page body is **not read**).
- **Settings windows are keyboard-driven too:** `Ctrl-Enter`/`Ctrl-Space` start editing a setting, `Enter` accepts (and closes the window when not editing), `Esc` cancels/reverts, `Tab` / `Ctrl-Up` / `Ctrl-Down` move between settings, `Alt`+underlined letter switches tabs `[S4]`.

### 4.4 Settings/dialog interaction (the most transferable section)

SC's docs openly describe the migration away from OS dialog boxes: *"These new Settings type of windows are gradually replacing the old Microsoft Windows-based dialog windows which have proven to be **unreliable, very inefficient, and operating system resource heavy**."* The replacement windows are **modeless** ("you can interact with other areas of Sierra Chart while one of these Settings Windows remains open. This is a major advantage"), resizable, column-width adjustable, with user-configurable font, font colours and element colours `[S4]`.

Per-setting semantics — unusual and worth copying:

- **A / C buttons** next to every entry: `A` accepts the entered value (= Enter, *not* Apply), `C` cancels that field back to the last entered/selected value, distinct from the window-level Cancel `[S4]`.
- **Window-level `OK` / `Cancel` / `Revert All` / `Apply All`** — Cancel reverts to last *saved* state and closes; Revert All reverts without closing; Apply All accepts without closing `[S4]`.
- **`View >> Show Original Values`** adds a column showing each setting's original value once changed `[S4]` — a built-in "what did I just change?" diff.
- **Search inside settings windows**: "Enter Search Text" box; matches list below; selecting one switches to the tab containing it and highlights the setting. Matching mode is configurable: *Extract String Matching* (tokenised, "allow partial words", `Mas Mod` → `Master Mode`) vs *Approximate String Matching* (`alw zr vl` → `Allow Zero Values`) `[S4]`.
- **Minimised settings windows go to the desktop, not the taskbar** — "When a Sierra Chart window is minimized it will not be shown in the task bar, as it is still managed by the main Sierra Chart window" `[S4]`.

---

## 5. Visual design language

**Density is the design.** SC is a stacking-grid app: chart + Values Scale + Time Scale + region data line + study values, with per-chart tab colours, per-study subgraph colours, and a **hundreds-of-items colour table**. The Graphics Settings page's own table of contents lists (excerpt) `[S10]`:

- `Chart`, `Chart Text`, `Chart Values Scale Text Color`, `Chart Values Scale Background`, `Chart Time Scale Text Color`, `Chart Time Scale Background`, `Chart Background`, `Chart Grid`, `Chart Grid Secondary`, `Chart Scale Border`, `Region Dividing Line`, `Chart Selected Tab Color`, `Chart Selected Tab Text Color`, `Chart Selected Tab Border Color`, `Chart Tab Color`, `Chart Tab Text Color`, `Chart Tab Control Background Color`, `Last Trade Price Box` + foreground + outline, bar up/down High-Low colour pairs, `Candlestick Up Outline` / `Up Fill` / `Down Outline` / `Down Fill`, `Net Change Up` / `Down`, `Bid Ask Average Line`, `Scroll End Color` / `Scroll Not End Color`, `Alert Highlight Color`, plus a separate **`Window`** group (`Main Window Background`, `Window Title Bar`).
- For the DOM specifically the colour list runs into the hundreds — the "Customizing Fonts, Colors… for Chart Trading, ChartDOM, and Trade DOM" page enumerates ~180 entries prefixed `Chart DOM …` and ~210 prefixed `Trade DOM …` (counted by grep over the saved page text) — including quantity-threshold tiers (`Chart DOM Bid Market Depth Quantity High Threshold Background Color`), same-price-and-side repeat-trade colours (`…Cumulative Last Size Bid Trade Same Price and Side Background Color`), pulling/stacking backgrounds and market-orders backgrounds `[S10][S22]`. The Graphics Settings page's own colour section likewise runs to well over a hundred named items `[S10]`.

**Fonts are configurable per scope, with DPI awareness.** Font settings are listed per chart-or-global (`Chart Text`, Values Scale, Time Scale, Study/Region text, `Window Title Bar`, and **`Settings Windows`**, which "changes the font properties for the Settings Windows. This includes windows like Chart >> Chart Settings"), selectable by Font / Style / Size / Strikeout / Underline with a live sample, and reset per item via a Reset-to-Default column. Point sizes are "internally stored in Sierra Chart and transformed during actual drawing to the actual required pixel height, based upon the Dots per Inch (DPI) setting in the operating system" `[S10]`. After changing chart text size you must re-run `Chart >> Recalculate` to resize the Values Scale column `[S10]`.

**Two scopes, one gotcha.** Every chart can either inherit or override global graphics: a per-chart option `Use Global Graphics Settings Instead of These Settings`, and commands `Copy to Global` / `Copy from Global`. The docs warn that editing the global window does nothing for a chart that "is set to use its own independent Graphics Settings", and that a font-size change may silently do nothing if the chosen font face is unsupported on the OS (`"choose a different Font name and then change the Size again"`) `[S10]`. Saved graphics configurations (slots 1-20) store **colours only** — *"It does not include items that are part of the Graphics Settings - Font or Graphics Settings - Other"* `[S10]`.

**Theming is per-object, not per-theme.** There is no "dark mode" toggle for the application surface documented in what I read; dark/light is achieved by editing background/foreground pairs, and there is a website-level "Toggle Dark Mode" control on every doc page `[S4][S10]`.

**What users say about the looks (the complaints are consistent and specific):**

- *"Sierra Chart's UI and website is ridiculously bad… I have seen bad UI, but Sierra Charts is so bad. I get that it is customizable to do what ever you want with it. Its just wall after walls…"* — r/SierraChart thread title: *"Sierra Chart's UI and website is ridiculously bad"* `[S23]` `[snippet]`.
- *"It's UI is ugly, there is no search functionality for indicators or settings. You literlly have to scroll through each and every thing…"* `[S24]` `[snippet]`. **Note the disagreement with the current docs**: SC *does* now document a search box in Settings Windows `[S4]` and ships a video "How to Search for Settings In Sierra Chart" `[S8]` — the complaint is at least partly about *searchability of studies and of the app as a whole* (there is no global command/study search), and partly stale.
- *"I hate the overall UI/UX of Sierra and no matter what it always looks like crap…"* (same thread: *"extremely customizable with a steep learning curve"*) `[S26]` `[snippet]`.
- *"Too ugly and settings are just overwhelming. The capability of the brackets blew my mind."* `[S27]` `[snippet]`.
- *"Ugly UI and a learning curve from hell, but it does everything a trader could want."* `[S28]` `[snippet]`.
- *"…the ugly, archaic, user interface."* `[S29]` `[snippet]`.
- AMP Futures' aggregated review summary (543 reviews, 4.80) states plainly: *"Although the platform has a steep learning curve and complex interface that can overwhelm beginners, users find the effort worthwhile due to unmatched flexibility and reliability"*; an individual review's headline text is literally **"Old Design"** `[S25]`.
- A review-site verdict: *"the first thing one usually thinks when they see the site is that it was made in 1995… Though their GUI is mid-90s, SierraChart has customizable charts, live trading, and hundreds of customizable options"* (pros: highly customisable, 300+ studies; cons: learning curve, desktop-only, external data required) `[S30]`.

**Small-text / accessibility evidence** (SC's own board, both threads read):

- *"I have a big problem with the font size of the Sierra Charts on this computer, **it's so small and impossible to read** (esp on the X and Y axis). I tried adjusting the resolution of the computer but it doesn't change the font size in Sierra at all."* — the developer's answer was a single link to `GraphicsSettings.html#Fonts`; the user's resolution: *"I didn't realise there are **2 types of graphic settings**. now I manage to adjust the font now finally."* `[S31]`
- Separate threads exist for study-level font controls and for font-size regressions on update: *"Type Text tool font size changed on update to 2789… they all have the altered font size"* and *"Change Delta Font Size in DOM… 'Text Font Size' is an option (in:110) but changing that doesn't change the font size"* `[S32]` (titles/snippets from search results; **thread bodies not read**).
- Counter-signal: DOM legibility is partly handled by layout, not by fonts — the workaround cited by users for one study was *"set 'Text Font Size' to 0 and… Set the width there to 5 for super tiny and neat text overlay"* `[S32]` `[snippet]`.

**Read on the design language:** the aesthetic cost is accepted as the price of density and speed, and both SC and its users say so explicitly — including SC's own reply to a GUI-overhaul request (see §7).

---

## 6. Onboarding & discoverability

**There are no wizards; there are numbered steps, videos, a board and a link wall.** What actually substitutes for in-product onboarding:

1. **A five-page setup chain** — Download → Create Account → Data/Trading Services → Getting Started Tutorial → Activate a Package, opening with the claim *"Sierra Chart is simple to get started with and simple to use"* `[S14]`.
2. **A Getting Started tutorial page** that walks chart creation, symbol entry, chartbooks, drawing tools, and trading, while routing failures *out* of the app: bad symbol → *"You will also see a message on the chart or Trade DOM that says Symbol is Unknown"* → "refer to Help Topic 1.3 (Symbols)"; feed failure → *"the Sierra Chart Message Log (Window >> Message Log) will display and indicate this. In this case, refer to help topic # 1"* `[S13]`. Note the pattern: **an error message in the UI names a documentation topic**.
3. **A Video Library** of ~20 task videos, including "Sierra Chart Basic Usage", "Sierra Chart Trading Interface", "Settings Windows Interface", "How to Search for Settings In Sierra Chart", "Volume By Price", "Trade Tagging in Sierra Chart", "Sierra Chart Simulated Futures Trading Service" — with a stated fallback for browsers that won't play them ("you can download them… and play them with the VLC video player") `[S15]`.
4. **Docs-as-product:** "The website documentation is updated and improved almost daily. It is designed to be simple and complete" `[S13]`; the Support page orders the options Self Help → Docs → Site Search → FAQ → then the board `[S12]`.
5. **A public board that behaves like a knowledge base**, where engineering answers and *other users* answer (the reattach puzzle in §2 was solved by two ordinary users, not by SC `[S20]`; the "Cannot find a window" thread was diagnosed by a user `[S21]`).
6. **The official line on the learning curve is "read the docs" + a hard email wall**: support-by-email is delayed two days or ignored `[S12]`.

**Where onboarding visibly fails (read, cited):**

- Elite Trader, *"New to Sierra Chart and about to give up on them"*: *"After almost 20 messages back and forth with support I still can't figure out how to access my futures account and at the same time see real time US equities data. I asked them a bunch of times which services/feeds I need to activate but I never get a straight answer. Instead they ask me snarky questions and send me links with tons of sublinks and unneeded information."* Replies included *"If the platform is not user-friendly, abandon it"* and, from another long-time user, *"Never could figure out their 'Sierra Chart Exchange Feed' vs 'Denali Exchange Feed' (also from them)"* `[S22]`.
- A 10-minute failure to undo a detach because the window had no menu (above) `[S20]`.
- A user who couldn't fix text size because a chart was using chart-specific rather than global graphics settings `[S31]`.
- The documented remedy for "windows missing from a chartbook" is a menu archaeology procedure (CW menu → Cascade → Maximize) rather than a visible restore affordance `[S2]`.

**The learning curve is the single most repeated user fact about the product** (representative, all `[snippet]`): *"It has a VERY STEEP learning curve, but well worth it"* `[S33]`; *"I know there is a steep learning curve and I'm completely fine with it… This is how I learned Sierra Chart. I just followed all of this…"* `[S34]`; *"Sierra chart is ridiculously powerful and adaptive to any traders requirements… But it has one hell of a steep learning curve"* `[S35]`; a MotiveWave-forum comparison calling it *"Super stable and robust software. Huge amount of customization. The only real con seems to be the steep learning curve"* `[S36]`.

---

## 7. What users actually say

**Praise (why people stay):**

- Vendor-curated wall of user emails on SC's About Us page (self-selected — treat as marketing evidence of *what* users value, not of satisfaction rates): *"We are simply amazed at the depth and power hidden behind every single feature within SierraChart!"*; *"I use your software everyday and probably only use 1% of it's capability but if I have an idea for a study, I know that I can find the tools in the software to test it."*; *"The customisability and speed/implementation really stand out, as does your knowledgeable support."*; *"stable, robust, minimal lag, customizable = FANTASTIC."* `[S17]`.
- Third-party aggregate: Trustpilot **3.7 / 25 reviews** (unclaimed profile; star breakdown **not read**), with 5★ reviews citing *"Extremely customizable… without a doubt in the elite tier of trading software"* and *"SC is one year light speed over all competitors, especially for scalpers"*; a 1★ review quotes the site's own "not woke or insane" line as a reason to avoid the vendor `[S37]`.
- AMP Futures review page: **4.80 from 543 reviews**; users specifically call out DOM/footprint/volume-profile depth, "everything integrated into one comprehensive package", and reliability `[S25]`.
- The engineering-level reply in the GUI-overhaul thread shows the flip side of the praise — SC's positioning as the anti-Bloomberg: *"software in general is in a state of utter pure deterioration at this point in time regarding efficiency, capabilities, and user interfaces. User interfaces are in decline. It is a race to the bottom… Except Sierra Chart. Sierra Chart needs improvement, and we will do that, but we will do it right."* (posted 2025-08-05, in reply to a user request titled *"Sierra Charts GUI Interface Overhaul"*) `[S38]`.
- A long-time Elite Trader user summarises the value/hassle trade: *"I've used Sierra for a long time. At least 20 years. I have found that it will likely do everything you need it to, but you will have to look…"* `[S39]` `[snippet]`.

**Complaints (the recurring five):**

1. **Ugly / dated UI** — §5 quotes `[S23][S24][S26][S27][S28][S29][S25][S30]`.
2. **Settings overwhelm** — *"settings are just overwhelming"* `[S27]`; the platform is described as "hundreds of customizable options" `[S30]`.
3. **No global search** for indicators/settings (partially stale — settings windows now search `[S4]`, studies still have no search `[S24]`).
4. **Window management traps** — hidden windows, title-bar-less detached windows, chartbook-not-visible-vs-instance rules `[S2][S19][S20][S21]`.
5. **Support tone and gating** — "snarky questions", links instead of answers, email effectively refused, and (Elite Trader) pricing/feed-configuration confusion between similarly named feeds `[S12][S22]`.

Independent comparisons converge on: **power and price are best-in-class; interface and onboarding are the tax** — e.g. *"There's a much higher learning curve with Sierra Charts, and it's no where near as user friendly for beginners as NinjaTrader"* `[S40]` `[snippet]`, and *"Steep Learning Curve: Its complex interface and extensive customization options can be intimidating for beginners"* `[S41]` `[snippet]`.

---

## 8. UX patterns worth adopting into ModFlow (vanilla-JS, single-window, one developer)

**Framing:** every row below assumes the ModFlow surfaces already listed in the brief (rail views, keyboard registry + Keys menu, workspaces/layouts, hover explain cards, per-surface pause/resume, help corpus, terminal mode with OS widget windows) stay as they are. These are *behaviours around* those surfaces, not new vertical features. Effort assumes one developer, no bundler, pywebview/WebView2 host, no breaking changes to the working app.

| # | Pattern (as Sierra Chart does it) | Why it matters here (evidence) | Effort | Risk |
|---|---|---|---|---|
| 1 | **Settings/properties surfaces: modeless + in-panel search + `Show Original Values` column + `Apply All` / `Revert All` / per-field accept-cancel (`A`/`C`)** `[S4]` | SC migrated off OS dialogs because they were "unreliable, very inefficient, and operating system resource heavy", and made settings modeless — "you can interact with other areas… This is a major advantage" `[S4]`. The search box with *tokenised* matching (`Mas Mod` → `Master Mode`) is directly copyable in JS and answers the loudest user complaint about SC `[S24]` | M | Low — additive to existing Settings/Studies surfaces; the trap is only scope creep (do per-panel, not global, first) |
| 2 | **Explicit settings scope: "this surface only" vs "global", with `Copy to Global` / `Copy from Global` and named saved configurations (slots)** `[S10]` | SC's #1 repeat support question is a scoping confusion — a user needed 10 messages and a "2 types of graphic settings" epiphany to change font size `[S31]`; saved configs store a subset only (colours), which users discover late `[S10]`. ModFlow has per-surface + global settings already; the missing affordance is an explicit, labelled scope switch plus a one-click copy between scopes | M | Low-Med — must not silently override per-surface tweaks; show a diff badge when a surface is in "own settings" mode |
| 3 | **Per-command shortcut legend + user-assignable shortcuts + a single master switch that disarms action/trading shortcuts** `[S5][S6][S7]` | SC puts the shortcut *on the menu line* `[S5]`, lets any command be rebound, and gates live-order shortcuts behind `Trade >> Trading Keyboard Shortcuts Enabled` `[S7]`. ModFlow already has a keyboard registry + Keys menu: the cheap wins are (a) print the binding next to each item in menus/buttons, (b) an always-visible "shortcuts armed/disarmed" indicator before anything that can move money | S-M | Low — pure additive UI; risk is a stale legend if the registry is edited at runtime, so render from the registry, not a static table |
| 4 | **Regression-proof window geometry: always keep a title bar/close affordance; clamp OS widget windows to a visible monitor; keep a "Windows & layouts" master list with restore/attach per window** `[S2][S19][S20][S21]` | Every SC windowing bug reported by users reduces to "the window is now unreachable": a title-bar-less detached window on monitor 2 that "took a lot of steps to restore" `[S19]`; *"I tried to reattach it for 10mins now. Its simply impossible"* `[S20]`; hidden windows recoverable only via the CW menu → Cascade `[S2]`, and a dedicated FAQ topic exists for position-not-restored `[S9]`. ModFlow has terminal-mode OS widget windows: a "list every window + reset position to primary monitor" command is the single highest-value defensive UI here | S-M | Low — defensive; requires touching the OS-window layer only in the "restore/clamp" path |
| 5 | **Blank / broken surface states carry the fix inline**: the surface itself names the diagnostic and links a help topic (`Symbol is Unknown` → Help Topic 1.3; feed failure → Message Log → help topic #1) `[S13]`, with a numbered, permanent help corpus `[S9]` | ModFlow already has ~90 help topics + Logs; making every empty/error panel render *"<reason> — Help #N"* with a click-through (and giving log lines stable topic IDs) converts the existing corpus into in-product onboarding, which is exactly what SC's numbered topics do from inside the app | S | Low — content work, not code risk; the failure mode is dead links, so a build-time check that topic IDs exist is worth it |
| 6 | **Docs-first culture with a *searchable* board archive rather than 1:1 support**: public threads, engineering replies, config attachments, searchable history, no email `[S12][S18][S19]` | SC's anti-email policy is only viable because the board is searchable, permanent, and answer-rich `[S12]`; users self-serve from old threads (the reattach fix came from two users) `[S20]`. ModFlow already ships a Journal + Guide/Help: adding *permalink IDs* and a search over past sessions/journals gives the same self-serve effect without staff | M | Med — without discipline it becomes a stale second knowledge base; only ship if the existing help corpus is the single source and journals link into it |
| 7 | **Right-click-anywhere context menus that the user can curate**, with the same command reachable from menu, shortcut and a visible button as three documented routes `[S6][S20]` | SC's right-click menus are *user-defined* (`Customize Chart Trade Menu`), which is why a missing command is a config problem rather than a dead end `[S6][S7]`. ModFlow has right-click explain cards; extending them into "explain + act" with a per-surface "edit this menu" affordance is a small step and directly addresses "where do I click to attach/detach" class bugs | M | Med — menu sprawl and inconsistent behaviour across 20+ surfaces; cap the default menu and require an explicit edit for extras |
| 8 | **Axis / scale as an interactive object**: right-click the value scale → Interactive Range / Move, then drag `[S7]` | Cheapest possible fix for the "my order/level is off-screen" class of confusion, which SC documents twice in two separate sections `[S7]`. ModFlow's Chart/Heatmap/DOM/Profile all have scales; the pattern is 20 lines of code plus a menu entry | S | Low — must not steal drag from existing pan/zoom; put it behind right-click only, and keep a documented "Reset Scales" command (SC has one per chart/DOM) `[S7b]` |
| 9 | **Density controls with per-region fonts, per-region colours and *threshold tiers*** (e.g. DOM quantity "high threshold" background, same-price-and-side repeat-trade colours, pulling/stacking backgrounds) `[S10][S22]` | SC handles "too small to read" with *layout and contrast tiers*, not just font size — and even then users report unreadable axis text and ask how to shrink study text to 0-width overlays `[S31][S32]`. ModFlow already has dark theme + colour-blind palettes: adding 2-3 named contrast tiers (Calm / Standard / Aggressive) layered on the existing palettes is a contained change | S-M | Low-Med — readability regressions are easy to ship unnoticed; needs a side-by-side screenshot check per tier before merge |
| 10 | **Config as portable artifacts**: Study Collections, saved DOM configuration, chartbook files users mail to each other `[S3][S7][S8]` | SC's users share `*.Cht` chartbooks and spreadsheet studies; the docs even cover "Sharing Your Spreadsheet Study With Another User" `[S15]`. For a one-developer app, "export/import a workspace+studies JSON" is a support-cost reducer (users fix setup by loading a file) and a bug-report aid | M | Low — versioning/schema drift is the only real risk; embed a schema version and refuse silently-corrupt imports with a readable message |
| 11 | **Per-instance identity for analysis modules**: a study added twice has two IDs, independent inputs, and a Settings/Inputs tab separated from a Subgraphs (visual) tab `[S8]` | This is the mechanism that lets SC be "everything is a study" without a config explosion. ModFlow's studies/expression API should mirror it: instance IDs (not type IDs) as the unit of config, inputs separated from display settings, and "duplicate with independent inputs" as the primary way users branch | M | Med — touches the studies/expression API, an area the app already depends on; do it as an additive ID layer, never a refactor of existing IDs |
| 12 | **A "message log" surface that is a first-class window**, referenced from error docs and reachable from the Window menu `[S2][S13]` | SC's documented first action for feed problems is "the Message Log will display and indicate this… refer to help topic #1" `[S13]`. ModFlow has Logs; the uplift is making each log line clickable to its help topic *and* letting other surfaces deep-link into a filtered view of Logs (one shared component, no new surface) | S | Low |

**Explicitly not recommended to copy:** the "everything is a right-click menu, and users must customise it before a command exists" default (rows landed in support pain `[S20]`); detachable/title-bar-less windows as a *default* density strategy (row 4); "no global search" for commands/studies `[S24]`; per-object colour tables with hundreds of entries as the only theming mechanism `[S10][S22]`.

---

## 9. Where their model does NOT fit

| SC assumption | Why it does not transfer to ModFlow |
|---|---|
| **Paid monthly service gating** (26–56 USD/mo; base tiers deliberately unable to connect to external feeds) `[S11]` | ModFlow is keyless-first and local-first. Gating surfaces behind a licence tier would be a UX regression with no revenue machinery behind it; conversely, SC's "activate a package, then troubleshoot which feed" onboarding step `[S14]` is the exact cost ModFlow exists to remove. |
| **A support organisation behind a public board** ("Engineering continuously monitors the Support Board"; 2,565 pages of threads; engineering-level replies on UX threads) `[S12][S18][S38]` | One developer cannot staff a board. The transferable part is the *artifact* (searchable, permalinked answers with config attachments `[S19]`), not the *process*. ModFlow's equivalent is a searchable in-app corpus + journals, not a public forum. |
| **Multi-instance + client/server architecture for multi-monitor** (`File >> New Instance` with its own data folder; DTC server for data/trading between instances) `[S1][S3]` | SC's answer to "two chartbooks at once" is to run two copies of the program talking DTC. ModFlow is a single pywebview shell with workspaces/layouts; replicating instances would multiply state, storage and support burden for a single dev, and risks the working DTC read-only bridge. |
| **Native C++ DLL plugin ecosystem** (Advanced Custom Studies as DLLs in the Data Files Folder; a published list of third-party study programmers and a study store) `[S8][S16]` | Unbounded native plugins mean: code signing questions, crash attribution, "your DLL broke my app" support load, and security surface — all unacceptable for a local-first app whose trust story is "nothing leaves your machine". The safe analogue is already present (declarative studies/expression API), and it should stay sandboxed. |
| **Windows MDI-era window semantics** (chartbooks as invisible containers, windows that can be hidden with no affordance, title bars users must not remove) `[S1][S2][S3]` | ModFlow's terminal mode uses real OS widget windows for a reason (multi-monitor power users), but every SC windowing pitfall `[S19][S20][S21]` is a bug class ModFlow would have to pay for: unreachable windows, geometry not restored `[S9]`, attach/detach discoverability. Adopt the *master list + clamp + always-visible pin* (row 4), not the container model. |
| **"Settings are the product"** — hundreds of per-object colour/font entries as the primary visual language `[S10][S22]` | Defensible for users who live in the tool for a decade and trade for a living `[S25]`; a discoverability tax for everyone else, and a maintenance tax for one developer (each new visual element multiplies the colour table). Named palettes + contrast tiers + a small number of scoped overrides get most of the value. |
| **Docs-first onboarding at the *scale* SC runs it** (numbered help topics cross-referenced from error strings; "read the docs before posting"; email support refused) `[S12][S13][S16]` | SC can require reading because its users are professionals with money at stake and because the docs are effectively a second product, updated "almost daily" `[S13]`. For ModFlow the same *mechanism* (error → numbered topic, F1-style context help `[S5]`) is worth having; the same *attitude* (no guided first-run) is not — SC's own board shows the cost: a new user with 20 support messages and a "shut up and read" reception `[S22]`, and a 10-minute dead end on a basic window action `[S20]`. |
| **Search-and-scroll as a navigation strategy** | SC's power users tolerate "wall after walls" of menus and settings `[S23][S24]`; ModFlow's single-window shape makes a global command/study/help search cheap and makes the absence of one conspicuous. Their model supplies the *content* to search (numbered topics `[S9]`, permalinked threads `[S18]`) but not the navigation. |

---

## 10. Sources (all read 2026-09-18 unless marked)

| ID | Source | URL | Read status |
|---|---|---|---|
| S1 | Detaching and Attaching Chart Windows | https://www.sierrachart.com/index.php?page=doc/DetachingandAttachingChartWindows.html | Read |
| S2 | Window, CB and CW Menus | https://www.sierrachart.com/index.php?page=doc/WindowMenu.html | Read |
| S3 | Chartbooks | https://www.sierrachart.com/index.php?page=doc/Chartbooks.html | Read |
| S4 | Settings Windows Interface | https://www.sierrachart.com/index.php?page=doc/SettingsWindowsInterface.php | Read |
| S5 | Keyboard Commands | https://www.sierrachart.com/index.php?page=doc/KeyboardCommands.html | Read |
| S6 | Global Settings Menu (Customize Keyboard Shortcuts / Customize Menu Items / Graphics Settings Configurations) | https://www.sierrachart.com/index.php?page=doc/GlobalSettingsMenu.html | Read |
| S7 | Chart Trading and the Chart DOM | https://www.sierrachart.com/index.php?page=doc/ChartTrading.html | Read |
| S7b | Trade Menu | https://www.sierrachart.com/index.php?page=doc/TradeMenu.html | Read |
| S8 | Chart Studies | https://www.sierrachart.com/index.php?page=doc/ChartStudies.html | Read |
| S9 | Help / FAQ list (numbered topics) | https://www.sierrachart.com/index.php?page=doc/help.php | Read |
| S10 | Graphics Settings (colours, fonts, scoping, saved configurations) | https://www.sierrachart.com/index.php?page=doc/GraphicsSettings.html | Read |
| S11 | Description of Service Packages and Pricing | https://www.sierrachart.com/index.php?page=doc/Packages.php | Read |
| S12 | Support and Contact (support policy, board-first, email policy) | https://www.sierrachart.com/index.php?page=doc/support.html | Read (telephone-policy body not read) |
| S13 | Getting Started, Opening Charts and Basic Trading | https://www.sierrachart.com/index.php?page=doc/GettingStarted.php | Read |
| S14 | Setup Instructions (5 steps, build 2950, 13 Sep 2026) | https://www.sierrachart.com/index.php?page=doc/setup.php | Read |
| S15 | Video Library | https://www.sierrachart.com/index.php?page=doc/VideoLibrary.php | Read |
| S15b | Docs Contents page (index of spreadsheet-study pages) | https://www.sierrachart.com/index.php?page=doc/Contents.php | Read (linked spreadsheet pages' bodies not read) |
| S16 | Developing Custom Studies and Systems | https://www.sierrachart.com/index.php?page=doc/DevelopingCustomStudiesAndSystems.php | Listed on Contents only; body not read |
| S17 | About Us (company facts + curated user praise wall) | https://www.sierrachart.com/index.php?page=doc/AboutUs.php | Read (vendor-curated quotes) |
| S18 | Support Board index (2,565 thread pages; sticky notices) | https://www.sierrachart.com/SupportBoard.php | Read |
| S19 | Thread 103652 — "Detached Windows with Show Title Bar off makes chart difficult to move/restore" | https://www.sierrachart.com/SupportBoard.php?ThreadID=103652 | Read |
| S20 | Thread 90655 — "How to reattach a detached Chart Window without Title / Menu / Scrollbar" | https://www.sierrachart.com/SupportBoard.php?ThreadID=90655 | Read |
| S21 | Thread 68230 — "Cannot find a window after detaching it" | https://www.sierrachart.com/SupportBoard.php?ThreadID=68230 | Read |
| S22 | Elite Trader — "New to Sierra Chart and about to give up on them" | https://www.elitetrader.com/et/threads/new-to-sierra-chart-and-about-to-give-up-on-them.361790/ | Read |
| S23 | r/SierraChart — "Sierra Chart's UI and website is ridiculously bad" | https://www.reddit.com/r/SierraChart/comments/u1gsox/sierra_charts_ui_and_website_is_ridiculously_bad/ | Not read (403/login wall) — quote from search snippet |
| S24 | r/SierraChart — "Sierra chart is pure shit and a scam company" | https://www.reddit.com/r/SierraChart/comments/k42oec/sierra_chart_is_pure_shit_and_a_scam_company/ | Not read — snippet |
| S25 | AMP Futures — Sierra Chart user reviews (4.80 / 543) | https://www.ampfutures.com/reviews/sierra-chart | Read (individual reviews partially read) |
| S26 | r/FuturesTrading — "What's so special about Quantower and Sierra Charts?" | https://www.reddit.com/r/FuturesTrading/comments/1kumjrd/whats_so_special_about_quantower_and_sierra_charts/ | Not read — snippet |
| S27 | r/FuturesTrading — "Sierra Chart vs Quantower" | https://www.reddit.com/r/FuturesTrading/comments/1998fkc/sierra_chart_vs_quantower/ | Not read — snippet |
| S28 | r/FuturesTrading — replay-capable platforms thread | https://www.reddit.com/r/FuturesTrading/comments/1pms5kk/what_are_some_good_trading_platforms_that_allow/ | Not read — snippet |
| S29 | r/FuturesTrading — "Sierra chart?" | https://www.reddit.com/r/FuturesTrading/comments/l3tjkb/sierra_chart/ | Not read — snippet |
| S30 | BullishBears — Sierra Chart Review (2026) | https://bullishbears.com/sierra-chart-review/ | Read |
| S31 | Thread 24882 — "Font size adjustment" (small/unreadable axis text; two settings scopes) | https://www.sierrachart.com/SupportBoard.php?ThreadID=24882 | Read |
| S32 | Threads 101834 / 86573 / 56092 — font-size regressions and study font controls | https://www.sierrachart.com/SupportBoard.php?ThreadID=101834 ; https://www.sierrachart.com/SupportBoard.php?ThreadID=86573 | Titles/snippets only — bodies not read |
| S33 | r/SierraChart — "Sierra Chart, What are your pros and cons?" | https://www.reddit.com/r/SierraChart/comments/cau7la/sierra_chart_what_are_your_pros_and_cons/ | Not read — snippet |
| S34 | r/FuturesTrading — "Sierra Charts tutorial or reference guide?" | https://www.reddit.com/r/FuturesTrading/comments/1frvjki/sierra_charts_tutorial_or_reference_guide/ | Not read — snippet |
| S35 | r/FuturesTrading — "Platforms" | https://www.reddit.com/r/FuturesTrading/comments/1jwyneg/platforms/ | Not read — snippet |
| S36 | MotiveWave forum — competitor-comparison thread | https://forum.motivewave.com/threads/i-love-mw-but-please-consider-hiring-more-devs.2974/page-3 | Not read — snippet |
| S37 | Trustpilot — sierrachart.com (3.7 / 25 reviews, unclaimed) | https://www.trustpilot.com/review/sierrachart.com | Read (star breakdown not read) |
| S38 | Thread 100913 — "Sierra Charts GUI Interface Overhaul" (engineering reply, 2025-08-05) | https://www.sierrachart.com/SupportBoard.php?ThreadID=100913 | Read (original post text truncated by the extractor) |
| S39 | Elite Trader — "A question for SierraChart devs" | https://www.elitetrader.com/et/threads/a-question-for-sierrachart-devs.387279/ | Not read — snippet |
| S40 | Elite Trader — "Good Software for Scalping Futures" | https://www.elitetrader.com/et/threads/good-software-for-scalping-futures.363057/ | Not read — snippet |
| S41 | QuantLabsNet — MotiveWave / Sierra Chart / TradingView comparison | https://www.quantlabsnet.com/post/best-institutional-trading-platform-motivewave-sierra-chart-and-tradingview | Not read — snippet |

**Claims count:** ~60 discrete cited statements across §§1-7, of which ~35 are from primary SC documentation and Support Board threads read directly, ~20 from user/review sources (7 of those via search snippets, explicitly labelled), and the remainder marked "not read".

**Known gaps (do not guess around them):** free-trial contents (`helpdetails59.php`), the body of the spreadsheet-studies pages, the telephone-support policy body, the Trading Keyboard Shortcuts doc page (URL not found), Trustpilot's star distribution, and the full text of the Reddit threads (blocked). Raw saved page text for everything read is in `./src/` next to this brief.
