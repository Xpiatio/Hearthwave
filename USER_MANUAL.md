# Hearthwave User Manual

> **Version:** v2.17.0

This manual covers day-to-day operation of Hearthwave as a GMRS family hub or neighborhood watch base station — a shared radio operating station where every household member or watch volunteer connects from their own device. For installation and server setup, see [README.md](README.md).

---

## Table of contents

0. [Quick start](#0-quick-start)
1. [Signing in](#1-signing-in)
2. [The interface](#2-the-interface)
   - [2a. Mobile interface](#2a-mobile-interface)
3. [Receiving transmissions (RX)](#3-receiving-transmissions-rx)
4. [Sending a message (TX)](#4-sending-a-message-tx)
5. [Quick messages](#5-quick-messages)
6. [Station identification (FCC ID)](#6-station-identification-fcc-id)
7. [Contacts](#7-contacts)
8. [Pending stations](#8-pending-stations)
9. [Spectrogram](#9-spectrogram)
10. [Session attendance](#10-session-attendance)
11. [Journals](#11-journals)
12. [Family journal (public page)](#12-family-journal-public-page)
13. [Settings](#13-settings)
14. [Your account](#14-your-account)
15. [Admin — managing users](#15-admin--managing-users)
16. [NCS — Net Control Station mode](#16-ncs--net-control-station-mode)
17. [Browser notifications](#17-browser-notifications)
18. [Text shortcuts reference](#18-text-shortcuts-reference)
19. [Voice PTT (browser microphone)](#19-voice-ptt-browser-microphone)
20. [CW (Morse code) receive mode](#20-cw-morse-code-receive-mode)
21. [Admin Settings dialog (admin)](#21-admin-settings-dialog-admin)
22. [Plugins](#22-plugins)
    - [22a. Installing and managing plugins](#22a-installing-and-managing-plugins)
    - [22b. MeshCore example plugin](#22b-meshcore-example-plugin)
    - [22c. Meshtastic example plugin](#22c-meshtastic-example-plugin)
    - [22d. Writing your own plugin](#22d-writing-your-own-plugin)
23. [FCC compliance and remote access](#23-fcc-compliance-and-remote-access)
24. [Transcription vocabulary biasing](#24-transcription-vocabulary-biasing)
25. [Deployment profiles and GPU acceleration (admin)](#25-deployment-profiles-and-gpu-acceleration-admin)
26. [STT calibration wizard (admin)](#26-stt-calibration-wizard-admin)
27. [AAC interface (symbol-button communication)](#27-aac-interface-symbol-button-communication)
28. [Home screen & interface levels](#28-home-screen--interface-levels)
29. [Accessibility options](#29-accessibility-options)
30. [Family activity](#30-family-activity)
31. [Neighborhood activity](#31-neighborhood-activity)
32. [Wall display (kiosk)](#32-wall-display-kiosk)

---

## 0. Quick start

> **UI note:** The interface uses a navy/blue design. Dark mode is enabled by
> default. Toggle between dark and light mode from Settings (hamburger menu on
> mobile, or the account menu on desktop).

New to Hearthwave? Here is what happens in your first five minutes.

1. **Open the app** — navigate to `http://<server-ip>` in any browser on your home network. Your administrator gives you this address.
2. **Create your account** — on first launch the Setup screen appears. Enter your name and a password; optionally add your operator name, callsign, and location. Click **Create Account**.
3. **Check station status** — the top bar shows **READY ●** (green dot) when the radio is connected and the server is listening. If it shows **OFFLINE**, the audio hardware may not be connected — contact your administrator.
4. **Send a test message** — type anything in the message box and press **Enter**. The status bar briefly shows **Transmitting**, then returns to idle. Your message appears in chat as a `[TX]` entry visible to all connected users.
5. **Confirm audio** — you should hear the TTS voice through the radio's speaker. If nothing plays, open **Settings → Audio** to verify the correct device is selected.
6. **Invite family members** — go to your account chip (top-left) → **Admin → Users** → **New User** to create accounts for each household member. Each person opens the same URL on their own device and signs in.

That's it. The rest of this manual covers each feature in detail when you're ready.

---

## 1. Signing in

Open your browser and navigate to the Hearthwave host address — typically `http://192.168.x.x` or a hostname your administrator provides.

### First launch — Setup screen

If no accounts exist yet, the **Setup** screen appears instead of the login screen. This happens once, the very first time Hearthwave is used.

1. Enter your **display name** and choose a **password** (minimum 8 characters, confirmed).
2. Optionally fill in **operator name**, **call sign**, and **location** — these can be changed later.
   - The call sign and location you enter here are saved to your personal profile **and** used to seed the station defaults on the **Station tab of Settings**. Both can be adjusted independently afterward.
3. Click **Create Account**. Your admin account is created and you are signed in automatically.

After setup, go to **ADMIN → Users** to create accounts for other family members.

### Returning users — Login screen

The **login screen** appears automatically. Select your name from the profile list, enter your password, and click **Sign In**.

- Each family member has their own account with a unique password.
- Your preferences (dark mode, profanity filter, listen-only mode, etc.) are stored in your account and follow you across all devices — phone, tablet, laptop.
- If you enter the wrong password three times, your account is locked for 15 minutes. Contact your administrator to unlock it sooner.

**New to the station?** Your administrator creates your account and gives you your initial password. You can change it any time via the account menu (see [Your account](#14-your-account)).

The login screen shows the **Hearthwave logo** and an **About** link beneath the sign-in form. The About link displays the running version (e.g. *v2.12.0*) and opens the **About Hearthwave** dialog with project links and FCC information. Once signed in, you can reopen this dialog any time from the **logo in the top bar** or the **About Hearthwave** entry in the account menu.

If the server is unreachable, the status bar shows **OFFLINE** in amber. Refresh the page or contact your administrator.

---

## 2. The interface

The Hearthwave interface adapts to your screen size — desktop and mobile use
different layouts but share the same feature set.

### Desktop layout

The desktop shows all panels simultaneously:

```
┌──────────────────────────── TopBar ─────────────────────────────┐
│ Callsign ●  [PTT]  [ABORT TX]  [Spectrogram]  [👤]              │
├──────────────────────────────────────────────────────────────────┤
│ NCS panel (when opened) · Stations/Journal open as dialogs        │
├──────────────────────────────────────────────────────────────────┤
│ Pending Stations                                                   │
├──────────────────────────┬───────────────────────────────────────┤
│ Spectrogram (waterfall)   │  Chat Display (scrollable RX/TX log)   │
├──────────────────────────┴───────────────────────────────────────┤
│ Status · Quick Messages · Message Input                            │
└──────────────────────────────────────────────────────────────────┘
```

- **TopBar** — navy gradient bar. Shows your callsign, a green dot when
  connected, the PTT button, the ABORT TX button, the spectrogram toggle, and
  your account chip.
- **Chat Display** — scrollable log of all RX (received), TX (sent), and CHAT
  messages, shared server-side across every signed-in device. Received messages
  appear with a green `[RX]` label; sent messages with a blue `[TX]` label;
  operator chat with a `[CHAT]` label. See
  [Shared, persisted message log](#shared-persisted-message-log).
- **Panels & dialogs** — on tablets and desktop, **Stations** and **Journals**
  open as centered modal dialogs that fill most of the window (the same as
  **Contacts**); close them with the toolbar button, the Escape key, or by
  clicking outside. The NCS panel and any installed plugin panels still appear
  inline above the chat. Each has a coloured gradient header: NCS uses a blue
  gradient; Journals and Stations use a darker navy gradient.
- **StatusRow** — bottom bar showing radio status (READY / OFFLINE /
  TRANSMITTING), audio device, and connection count.

### Colour language

| Colour | Meaning |
|---|---|
| Green dot / indicator | Radio connected and ready |
| Green `[RX]` label | Incoming transmission |
| Blue button / highlight | Primary action (send, save, confirm) |
| Amber / warning | Degraded state (connection issues) |
| Red / error | Error or emergency state |

---

## 2a. Mobile interface

On phones Hearthwave shows a single-column mobile view (tablets and larger screens get the desktop layout):

```
┌────────────────── TopBar (sticky) ──────────────────┐
│ [≡]  Callsign ●        [PTT]  [ABORT TX]            │
└──────────────────────────────────────────────────────┘
│                                                      │
│              Chat Display (scrollable)               │
│                                                      │
└──────────────────────────────────────────────────────┘
┌────────── Bottom Navigation ─────────────────────────┐
│  Chat  │  Family  │  Neighborhood │  Stations*  │  Journal* │
└──────────────────────────────────────────────────────┘
  * Stations and Journal only appear for Operator-level accounts.
```

- Tap **[≡]** (top-left) to open the settings drawer: dark mode, listen-only,
  STT, read-aloud, notifications.
- The **PTT** button and **ABORT TX** button are always visible in the top bar.
- **Chat**, **Family**, and **Neighborhood** are available at both interface
  levels; **Stations** and **Journal** need the **Operator** level (see
  [section 28](#28-home-screen--interface-levels)). NCS mode is desktop/tablet
  only and does not appear on the phone layout.
- See [section 30](#30-family-activity) for what the Family tab does, and
  [section 31](#31-neighborhood-activity) for the Neighborhood tab.
- The account menu is accessible from the settings drawer.

---

## 3. Receiving transmissions (RX)

Received audio is automatically transcribed by Whisper and displayed in the chat area. Transcription runs continuously in the background.

Each received entry is labelled **[RX]** in the chat (in green). Outgoing entries are labelled **[TX]** (in blue). System messages appear without a label.

**Partial transcripts** appear within about two seconds of a station keying up — you see the text growing while the operator is still talking rather than waiting for them to unkey. Each ~2-second audio slice is transcribed and appended to the running chat line. Once the transmission ends the complete transcript replaces the partial.

**Callsign highlighting:** Callsigns in received text appear as amber chips. The system detects all common forms — compact (`WSLZ233`), NATO phonetic (*Whiskey Sierra Lima Zulu Two Three Three*), spaced (`W S L Z 2 3 3`), and hyphenated (`WSLZ-233`) — and collapses them into a single chip showing the compact canonical form.

- **Known contacts** (in your shared contacts list) show an amber chip. Hover or tap for the operator name, location, and any GMRS/HAM cross-references. If multiple family members share the same callsign, the tooltip lists all of them.
- **Verified contacts** show a green **✓** badge immediately after the chip, indicating the callsign has been confirmed against the FCC database.
- **Unknown callsigns** appear as a dimmer chip and are added to the [Pending stations](#8-pending-stations) bar above the chat.
- **Fuzzy correction:** If fuzzy callsign matching is enabled and Whisper mishears a single character (e.g. `WSLZ235` instead of `WSLZ233`), the chip is shown with the corrected canonical form if a known contact is only one character away.
- **Callsign auto-correct:** With the additional **Callsign Auto-Correct** toggle on, the correction is written into the transcript itself — the journal, chat history, read-aloud, and plugins all see the corrected callsign. Corrected chips show a dotted underline; hover to see what was actually heard. If two known callsigns are equally close, nothing is changed.
- **Cross-transmission detection:** If a callsign is phonetically spelled across two separate keying events (e.g. the first half in one transmission, the second half in the next), it is still detected and highlighted in both chat entries.

**Profanity filter:** If your profanity filter is enabled (see [Settings](#13-settings)), profanity is masked in received text with asterisks. Other users with the filter off see the unmasked text. This is a per-account setting.

**Read Aloud:** Enable the **READ ALOUD** button in the top bar to have finalized RX transcripts spoken aloud through your browser. The station's TTS voice is used. Useful for eyes-busy operation or hearing-accommodated operators. This is a per-account preference and does not affect other users.

---

## 4. Sending a message (TX)

Hearthwave has two distinct send actions — **CHAT** and **TRANSMIT**. Use the correct one for what you want to do.

### CHAT — operators only, no radio

Pressing **CHAT** (or **Shift+Enter**) broadcasts your message to the shared log for all connected operators but does **not** key the radio. The message appears in the chat area marked `[CHAT]` and is visible to everyone currently signed in. It is profanity-filtered per recipient according to each user's individual filter setting. Chat messages are blocked when your account is in listen-only mode.

Use CHAT for coordination notes that do not need to go over the air — confirming a plan before transmitting, alerting other operators to channel activity, or passing administrative notes.

### Shared, persisted message log

The message log — received transcriptions (`[RX]`), your transmissions (`[TX]`), and chat lines (`[CHAT]`) — is shared by the server across the base station and every web and mobile login. When you sign in, or simply refresh the page, you see the history that has accumulated since the log was last cleared, not a blank screen. The stream is profanity-filtered to match *your* personal filter setting, regardless of who sent each line.

The log is held in the server's memory. It is **not** written to disk, so restarting the backend starts the log fresh, and only the most recent messages are kept (older entries roll off automatically on a very long session).

**Clearing the log is admin-only and clears it for everyone.** Only an administrator sees the **Clear chat log** button (the sweep icon in the top bar). Using it asks for confirmation, then wipes the shared log for every connected operator — base station, web, and mobile — at the same time. There is no per-user "clear my view only"; this keeps everyone looking at the same stream. Clearing cannot be undone.

### TRANSMIT — sends over the air

1. Type your message in the message box at the bottom of the screen.
2. Press **Enter** or tap **TRANSMIT**.

The system will:
- Expand TTY abbreviations and Q-signals (see [Text shortcuts reference](#18-text-shortcuts-reference))
- Apply your profanity filter if enabled
- Wrap the message with the station callsign per FCC rules
- Synthesize speech server-side using the configured Piper voice and play it out the configured output device to the radio
- Key the radio via PTT and transmit

The status bar shows **Transmitting** while the radio is keyed and returns to **Idle** when done.

> **Server-side audio:** TTS playback for transmitted messages is handled entirely by the server through the configured output device. Your browser does not play back the audio, which prevents double-keying the base station if multiple operators are connected.

**Per-operator voice:** If the transmitting operator has a personal TTS voice configured in their profile (`voice_as`), that voice is used for the transmission. If no personal voice is set, the station default voice is used.

**Chat echo:** Every outgoing transmission appears in the chat area as a `[TX]` entry (shown in blue). All connected users see the same entry in real time. When a message is directed to a specific station, the recipient is shown between the sender and the message text:

| Scenario | Chat display |
|---|---|
| Broadcast | `[TX] [Dad]: Hello everyone` |
| Directed | `[TX] [Dad] → WSLZ233 — Dave: Hello` |

**Targeting a specific station:** Use the **To** dropdown above the message box to address a transmission. The list is sorted alphabetically by callsign; **ALL — Broadcast** is pinned at the top. Your own callsign appears in the list so you can address yourself (useful for testing or self-checks). Selecting a contact pre-fills the callsign and name; the outgoing message is addressed to that station and the recipient label appears in chat for all users. When multiple family members share the same GMRS callsign, each appears as a separate entry (`WQZE123 — Alice`, `WQZE123 — Bob`) and the correct person is always selected regardless of order.

**Placeholder tokens:** Include `{1}`, `{2}`, etc. as fill-in-the-blank slots. When you send, the system prompts you to fill in each before transmitting. Useful for templates: `Heading to {1} — ETA {2} minutes`.

**Voice preview:** Open your account menu (the chip in the top bar) and click **Sample** next to the voice selector to hear the selected TTS voice without keying the radio. To change your personal voice, see [Your account](#14-your-account).

**Listen-only mode:** When active, all TX controls are hidden. Your setting does not affect other users — each person controls their own TX access independently.

**Message length limit (mesh-bridge plugins):** When a mesh-bridge plugin (MeshCore or Meshtastic) is enabled (see [section 22](#22-plugins)), a live character counter appears under the message box showing that plugin's hint (e.g. `MeshCore · 18 / 135` or `Meshtastic · 18 / 200`) and typing is capped so the message — plus the sender-name prefix added on the mesh — fits a single mesh packet. The counter turns red at the limit. With no such plugin enabled there is no limit and no counter. Each plugin's settings live in the **Plugins** tab of the Settings dialog.

---

## 5. Quick messages

The quick messages bar sits between the chat area and the message input. It provides one-tap access to pre-set phrases — useful for common responses like "Standing by", "QSL", or channel changes.

**Using a quick message:** Click any button to insert that phrase into the message box. The text can be edited before sending as normal.

**`{Name}` placeholder:** If a phrase contains `{Name}` it is automatically replaced with your operator name when you tap the button.

**Editing your quick messages:** Click the **⚙** (settings) icon on the right of the bar to open edit mode.

- **Add:** Type a new phrase in the text box and click **ADD** (or press Enter).
- **Reorder:** Use the **↑** / **↓** arrow buttons.
- **Remove:** Click the **🗑** button next to a phrase.
- Click **DONE** to close edit mode.

Quick messages are stored in your browser's local storage — they are per-browser, not synced across devices.

---

## 6. Station identification (FCC ID)

GMRS regulations require your station to identify with the callsign at least every 15 minutes. Hearthwave handles this automatically — every outgoing message is wrapped with the station callsign and the timer resets.

**Manual "THIS IS" ID:** Tap the **THIS IS** button to send a standalone identification in NATO phonetics (e.g., *"This is Whiskey Quebec Zulu X-Ray 9 9 9"*). Use this at the start of a session or when required by net control. A `[TX] Station ID` entry appears in chat for all connected users.

**Monitoring beacon (optional):** Hearthwave can also send a periodic presence call — *"<CALLSIGN> Hearthwave base, monitoring."* — on a fixed timer, announcing that the station is listening even when no one is on frequency. It is **off by default**. Enable it with the `monitoring_beacon_enabled` config key, and tune `monitoring_beacon_interval` (seconds between beacons, default 900) and `monitoring_beacon_text` (the spoken phrase; `{callsign}` is substituted). The beacon transmits only when the channel is clear, is suppressed while NCS mode is active, and — because it leads with your callsign — satisfies the FCC station ID when it airs, so it never double-IDs with the automatic identification above.

---

## 7. Contacts

The **Contacts** panel shows the shared station contact list. All users on all devices see the same list.

| Field | Description |
|-------|-------------|
| Callsign | Primary callsign (GMRS or HAM) |
| Name | Operator name |
| Location | City/state or grid square |
| GMRS callsign | GMRS-specific callsign (if different from primary) |
| HAM callsign | Amateur radio callsign (if different from primary) |
| Verified | FCC verification status (✓ = confirmed against FCC database) |

### GMRS family callsigns

A GMRS licence covers an entire household, so multiple people share the same callsign. Hearthwave supports this by allowing **multiple contact records with the same callsign**, each identified by a unique name.

**Example:** John Smith / WQZE123 and Jane Smith / WQZE123 are stored as two separate rows. Each can be edited, deleted, or verified independently. When a callsign chip appears in chat, hovering shows all family members registered to that callsign.

There is no limit to the number of records per callsign. A nameless record can still be created for stations where the operator is not yet known; a second record with a name is added separately and does not replace the nameless one.

### Adding a contact

1. Click **Add Contact** in the Contacts panel.
2. Enter the callsign. This field is required.
3. Optionally enter a name, location, GMRS callsign, and HAM callsign.
4. Click **FCC Look Up** to auto-fill name and location from the FCC database (requires internet).
5. Click **Save**.

To add a second family member with the same callsign, simply click **Add Contact** again, enter the same callsign, and enter a different name. Both records are kept.

### Editing a contact

Click the **edit icon** (✏) in the row you want to change. The callsign cannot be changed during edit (it is the record's identifier). All other fields — name, location, GMRS callsign, HAM callsign — can be updated freely. Click **Save** to apply.

> **Note:** When editing a contact that shares a callsign with other family members, only that specific record is changed. The others are not affected.

### Deleting a contact

Click the **delete icon** (🗑) in the row you want to remove. Only that specific record is deleted — other records with the same callsign are unaffected.

### Verify All

Runs an FCC database check on every contact in the list simultaneously. Verified contacts display a ✓ badge. This requires internet access.

### Sort by suffix

Sorts the list by the numeric suffix of each callsign — useful for GMRS family callsigns that share a prefix (e.g. WQZE100, WQZE200, WQZE543 sort together by 100, 200, 543 regardless of prefix).

### Import and export

Use the **Import** and **Export** buttons in the Contacts toolbar to transfer contacts in bulk.

| Format | Description |
|--------|-------------|
| **Export JSON** | Saves the full contacts list as `contacts.json` — includes all fields and can be re-imported directly |
| **Export CSV** | Saves as a spreadsheet-compatible CSV with columns: callsign, name, location, gmrs_callsign, ham_callsign, verified |
| **Import** | Accepts `.json` or `.csv` files; all records in the file are added; existing records with the same callsign *and* name are updated in place |

---

## 8. Pending stations

When an unrecognized callsign is detected in a received transmission, it appears as a chip in the bar below the top bar.

- **Click a chip** to open Add Contact pre-filled with the extracted callsign, name, and location.
- **Tap × on a chip** to dismiss without adding.
- **Dismiss All** clears the entire bar.

If internet is available and a name was detected, the system runs an FCC lookup automatically and may add the contact on its own. A notification appears in chat when this happens.

**Accessibility:** The pending stations bar is a labelled landmark region. Screen readers announce new chips as stations are detected mid-session. Each chip's dismiss button is labelled with the specific callsign (e.g. "Dismiss WSLZ233") so it is unambiguous in a screen reader's interactive elements list. When a name or location was extracted from the transmission, it is included in the chip's accessible label.

---

## 9. Spectrogram

The spectrogram shows a real-time waterfall of incoming audio to the left of the chat area.

**Showing / hiding:** Click the **WATERFALL** button in the top bar to toggle the display on or off. The preference is remembered in your browser across sessions.

**Left-edge indicators:**
- **Amber stripe** — squelch is open (audio above the noise floor)
- **White stripe** — VAD active; speech is being segmented

**Configuring the spectrogram** (Config tab):

| Setting | Options | Description |
|---------|---------|-------------|
| Colormap | Viridis / Grayscale | Color scheme (per-user) |
| Freq Range | Voice / Full | Voice = 300–3400 Hz, Full = 0–8 kHz (station-wide) |
| Time Window | 10s / 30s / 60s | History visible (per-user) |

---

## 10. Session attendance

The **Stations** panel tracks which callsigns have been heard during the current session.

**Clear attendance:** Resets the list for a new session or net.

Attendance is in-memory only and resets when the server restarts.

---

## 11. Journals

The **Journals** panel lets you generate and save AI-written session summaries. Requires a Google Gemini API key configured by your administrator.

**Generating a journal:**
1. Open the Journals panel at the end of a session.
2. Click **GENERATE FROM SESSION**. The system sends the session transcript and detected callsigns to Gemini.
3. The journal is saved automatically — a **"Journal saved"** snackbar confirms it. The new entry appears at the top of the list on the left.

**Viewing saved journals:** Click any entry in the list to read its title, summary, stations on air, and session transcript.

**Deleting a journal:** Click the **delete icon** (🗑) next to a journal in the list. Click once to arm the delete, click again to confirm.

**Publishing to the family journal:** Select a saved journal, then click the **PUBLISH TO FAMILY JOURNAL** button that appears in the detail view. Click once to arm, click again to confirm. A snackbar confirms publication. You can also publish directly from the list using the **publish icon** (⬆) next to each entry. See [Family journal](#12-family-journal-public-page).

---

## 12. Family journal (public page)

The family journal at `/journal` is a public page — no login required. It shows the most recent published session logs and can be bookmarked and shared with anyone.

**URL:** `http://<your-host>/journal`

**What's shown:** Each published entry displays the session date, who published it, the AI-generated summary, and the list of stations on the air. Raw transcripts are not included.

**Capacity:** The page always shows the 10 most recently published journals. Publishing an 11th entry automatically removes the oldest.

**Accessibility:** The page is designed to meet WCAG 2.1 AA standards — it works with screen readers, keyboard navigation, and automatically adapts to your browser's dark mode setting. No JavaScript is required.

---

## 13. Settings

Open your personal settings panel by clicking your **account chip** in the top bar and selecting **Settings**. All changes take effect immediately and are saved to your account.

### Audio (station-wide, admin)
| Setting | Description |
|---------|-------------|
| Input device | Which microphone/audio interface the server listens on |
| System audio loopback | Capture from a PulseAudio sink (for radios on virtual cable) |

> **Connecting the radio:** Hearthwave connects to the radio's **combo (speaker/mic) jack** — typically a Kenwood-style **K1** cable — either through the computer's built-in 3.5 mm jack or a USB sound card. A USB connection *to the radio itself* is not required. For a VOX-keyed radio, enable the **VOX primer tone** (see [Settings → System tab](#21-admin-settings-dialog-admin)) so the radio opens before speech begins. Full wiring options are in the [README](README.md#connecting-the-radio).

### Radio & content (per-user)
| Setting | Description |
|---------|-------------|
| Profanity filter | Masks profanity in your sent and received text (other users unaffected) |
| Listen-only mode | Disables TX for your account only |
| AAC Interface (symbol buttons) | Replaces the whole UI with a full-screen symbol-button communication screen — see [section 27](#27-aac-interface-symbol-button-communication) |
| Fuzzy callsign matching | Station-wide; when Whisper mishears a single character in a callsign (e.g. `WSLZ235` → `WSLZ233`), the chip in chat and the pending/attendance entry are corrected to the known canonical form |
| Callsign auto-correct | Station-wide; requires fuzzy matching. Rewrites the misheard callsign in the final transcript itself (journal, read-aloud, and plugins see the corrected text). Corrected chips are marked with a dotted underline and a tooltip showing the heard text |

### Voice
| Setting | Description |
|---------|-------------|
| Voice Test | Preview your current TTS voice (or the first available voice if none is set) without keying the radio. The button shows **Playing…** while audio is synthesizing. |

Your personal TTS voice and speech speed are chosen in **Account → Edit Profile** (see [Your account](#14-your-account)). If you have not selected a voice, the station-default voice configured by the admin is used.

### Spectrogram (per-user)
| Setting | Description |
|---------|-------------|
| Colormap | Viridis or Grayscale |
| Time window | How much history is visible |

> Frequency range is a station-wide setting controlled by an admin.

### Station identity (admin only)
The **callsign**, **name**, **location**, **default TTS voice**, **Gemini API key**, and **journals directory** are set on the **Station tab** of the **Settings** dialog (admin only). These are shared by all users. Changes are persisted to `config.json`.

The **Default TTS Voice** dropdown sets which Piper voice the station uses when a user has not chosen a personal voice. Click the **mic icon** next to the dropdown to preview the selected voice without keying the radio.

The same Station tab has a **Neighborhood** area, below NCS/SKYWARN, where an admin sets the weekly **Net Day** and **Net Time** for the neighborhood watch net. This schedule is shown on the Neighborhood home card and inside the Neighborhood activity, and updates live for every connected user the moment it's saved — see [section 31](#31-neighborhood-activity).

### Dark / Light mode

Toggle between dark mode (navy backgrounds, light text) and light mode
(navy-tinted light backgrounds, dark text) from:

- **Mobile:** Settings drawer (hamburger menu → Dark mode switch)
- **Desktop:** Account menu → dark mode toggle

The preference is saved per-user on the server and restored on next login.

---

## 14. Your account

Click your **name chip** in the top-left of the top bar to open the account menu.

### Edit profile
Change your **operator name** (shown in TX messages), **call sign**, **location**, **avatar emoji**, **TTS voice**, and **speech speed**. These are personal to your account and affect how your transmissions are identified — other users' transmissions use their own profile values.

> **Station vs. personal callsign:** Each user can have their own call sign and location. Your personal call sign takes precedence over the station-wide callsign for your transmissions. If your profile has no call sign set, the station callsign (set on the Station tab of Settings) is used as a fallback.

**TTS Voice:** Choose your personal Piper voice from the dropdown. Click **Sample** to hear it before saving — no radio is keyed. Select *Station Default* to fall back to whichever voice the administrator has configured. Each family member can use a different voice.

**Speech speed:** Enable **Custom speed** and adjust the slider to set a personal TTS pace — lower values produce faster speech, higher values produce slower speech. Leave it on *Station Default* to use the speed configured by the admin.

### Change password
Enter a new password (minimum 8 characters). You must confirm it. Your current sessions remain active after a password change.

### Sign out
Ends your session on this device. Your preferences are saved and will be restored when you sign in again, even on a different device.

> **Tip:** Signing out does not affect other users or the radio. The station continues to receive and the other family members stay connected.

---

## 15. Admin — managing users

Admin accounts open the **Settings** dialog from the **Settings** entry in the account chip menu. Beyond the **Preferences** tab that every user sees, admins also get three tabs: **Station** (station identity, user accounts, NCS / SKYWARN), **System** (audio, STT, PTT, and advanced server settings — see [section 21](#21-admin-settings-dialog-admin)), and **Plugins** (install, enable/disable, and configure plugins — see [section 22](#22-plugins)). The **NCS MODE** button in the top bar opens the NCS panel alongside the main interface without entering the settings dialog.

### User accounts

The **User Accounts** table lists all family member accounts, with a **Role** column for each.

**Creating a new account:**
1. Click **New User**.
2. Choose an avatar emoji, enter the display name, operator name, call sign, and location.
3. Set a password (minimum 8 characters, confirmed).
4. Pick a **Role** — **Admin**, **Adult**, or **Kid** (see below).
5. Click **Create**.

**Changing a role later:** Use the **Role** dropdown directly in that user's row — it saves immediately, no separate save step. You cannot change your own role (the dropdown is disabled on your own row), which prevents a station from being accidentally left with no admin.

**Resetting a lockout:** If someone is locked out after too many wrong passwords, click the **unlock icon** (🔓) next to their name. They can sign in immediately.

**Deleting an account:** Click the **delete icon** (🗑) next to a user. You cannot delete your own account.

**Neighborhood coordinator:** A **Coordinator** switch in the same table grants or revokes the Neighborhood-net controls described in [section 31](#31-neighborhood-activity) (Start/End net, round-table calling, street alerts) for that user. It saves immediately, like the Role dropdown. The switch is disabled for **Kid** accounts — a kid account can never be a coordinator — and demoting an Admin or Adult to Kid automatically clears any coordinator grant they held.

> **Security note:** For public internet access, put a TLS reverse proxy (nginx, Caddy) in front of the app. Passwords are hashed with PBKDF2-SHA256 (260,000 iterations, per-user salt) but session tokens travel in plaintext over HTTP without TLS.

#### Roles

| Role | Can do |
|---|---|
| **Admin** | Everything Adult can, plus station settings (Settings → Station/System/Plugins tabs), user management, NCS mode, and the admin-only controls throughout this manual. |
| **Adult** | Full day-to-day operation — send/receive, contacts, journals, quick messages, Family check-ins — but no station settings. |
| **Kid** | A locked-down account for children — see below. |

**Kid accounts** are restricted for safety and simplicity:
- Can use text **CHAT** freely, with the profanity filter always on and locked — a Kid account cannot turn it off.
- Can only **transmit on-air** (send over the radio) using their preset quick messages — the same buttons shown in the Family activity (see [section 30](#30-family-activity)) — sent exactly as written; there is no free-text on-air transmit box.
- Interface level is locked to **Simple** (no Operator-level controls, ever).
- No access to the Settings dialog at all — the gear icon is hidden on the Home screen and settings drawer.
- Can still send the **I'm OK** check-in — see [section 30](#30-family-activity) — since that is treated as a safety action available to every role.
- Can still check in to the Neighborhood net and view the incident log and street alerts — see [section 31](#31-neighborhood-activity) — but cannot file an incident report (it keys the radio) and can never be a Neighborhood coordinator.
- Kid accounts can use the AAC Interface (section 27): sends are limited to the words on their buttons — the server checks every send against the buttons a parent configured (or the built-in starter grid) and rejects anything else.

### NCS / SKYWARN (admin only)

The **NCS / SKYWARN** section at the bottom of the Admin panel configures the Net Control Station plugin:

| Field | Description |
|-------|-------------|
| NWS County Zone | NWS zone code for SKYWARN alert polling (e.g. `MIZ025`). Empty = disabled. Find your zone at weather.gov. |
| Net Opening Preamble | Script read on the air (via the NCS panel) to open a net. Placeholders: `{callsign} {name} {location} {date} {time}`. Empty = none. |
| Net Closing Script | Script read on the air to sign off a net. Same placeholders. Empty = none. |

The announcement interval (how often net ID is broadcast during an active NCS session) defaults to 10 minutes and is set in `config.json` (`ncs_announcement_interval`).

---

## 16. NCS — Net Control Station mode

NCS mode is for licensed operators running a net. It is available to admin accounts only. When active, the **NCS MODE** button in the top bar glows red and the **NCS panel** appears on the left side of the screen alongside the other panels.

### Activating NCS mode

Click **NCS MODE** in the top bar. The button turns red and the NCS panel opens. Click again to deactivate — ongoing roster and audio state are reset when NCS mode ends. An end-of-net journal is automatically saved on deactivation.

### Checking in a station

The check-in form at the top of the NCS panel has four fields:

| Field | Required | Description |
|-------|----------|-------------|
| **Callsign** | Yes | The station's callsign (uppercase, normalized automatically) |
| **Traffic** | No | Traffic priority level (see below); defaults to Routine |
| **Name** | No | Operator name; auto-filled from Contacts if known |
| **Location** | No | Station location; auto-filled from Contacts if known |

Type the callsign and press **Enter** or click **CHECK IN**. The callsign and name fields clear after a successful check-in; the traffic level is kept for the next entry.

**When the same callsign checks in twice with a different name**, both appear as separate roster rows — this is the expected behavior for GMRS family licences where John Smith and Jane Smith share WQZE123.

### Traffic levels

Six levels are available, selectable from the Traffic dropdown:

| Level | Use |
|-------|-----|
| **Routine** | Normal net traffic — default |
| **Priority** | Elevated — time-sensitive but non-emergency |
| **Emergency** | Life-safety situation — displayed prominently |
| **General** | General conversation / off-net traffic |
| **Short Term** | Operator can only stay for a few minutes |
| **IN-n-Out** | Quick check-in, no traffic, leaving after acknowledgement |

### Roster

The roster table lists every station that has checked in during the net. Each row shows:

| Column | Description |
|--------|-------------|
| Callsign | Station callsign; a ✓ badge indicates FCC-verified contact |
| Name | Operator name (shown below the callsign in small text if set) |
| Status | Current status — click the chip to toggle between CheckedIn and Standby |
| Traffic | Traffic priority — displayed as a colored chip |
| Time | Check-in time |
| Remove | Click the delete icon to remove a station from the roster |

**Status values:**
- **✓ In** (green) — Checked in and active
- **Stby** (amber) — Standing by, not responding at the moment
- **Out** (gray) — Logged out of the net

**Automatic contact handling:** When a callsign checks in that is not in the shared contacts list, it is automatically added as a new contact and an FCC lookup is triggered in the background. When the FCC result arrives, the contact record is updated and the ✓ badge appears in the roster live — no manual action required. If the callsign is already in contacts, the name and location fields are pre-filled automatically.

**GMRS family members:** Multiple operators sharing a callsign appear as distinct rows — one per name. Remove, status-toggle, and traffic actions target only the individual row clicked.

### BREAK BREAK

The red **BREAK BREAK** button immediately interrupts the current net. When pressed:

1. Any queued TX is drained.
2. TX is blocked for 2 seconds while an acknowledgement is broadcast to all connected clients.
3. A pulsing animation on the button confirms the break was sent.

Use BREAK BREAK for emergency announcements or to immediately silence the channel.

### Instant replay

Click the **replay icon** in the NCS panel header to hear the last 15 seconds of received audio played back through your browser. The replay buffer rolls continuously; clicking it at any moment lets you re-listen to something you may have missed.

### SKYWARN alerts

If a NWS county zone is configured in the Admin panel and internet is available, the NCS plugin polls api.weather.gov every 5 minutes for Extreme or Severe weather alerts. When one arrives:

- A red alert banner appears at the top of the NCS panel showing the event name and headline.
- A browser notification fires (if **NOTIFY** is enabled and the tab is hidden).
- An auto-TX announcement is sent over the air (listen-before-talk checked first).

### SKYWARN spot reports

Click the **storm icon** in the NCS panel header to file a SKYWARN spot report. This is available whether or not a net is active — severe weather does not wait for a net. The composer asks for the hazard type and a few fields keyed to the official SKYWARN reporting criteria:

| Hazard | Reporting threshold |
|---|---|
| Tornado / funnel cloud / rotating wall cloud | Always reportable |
| Hail | Largest stone ≥ 1.00 inch |
| Wind / damage | ≥ 40 mph (estimated or measured); describe damage |
| Flooding / rainfall | ≥ 1 inch in an hour, or describe the flooding |
| Snow / Other | Snowfall amount or a description |

You also enter the **location** (required) and the **time observed** (defaults to now). The **TRANSMIT REPORT** button stays disabled until the report meets criteria. When you submit, Hearthwave:

- Builds a standardized report — e.g. *"SKYWARN SPOT REPORT. HAIL, LARGEST STONE 1.75 INCHES (GOLF BALL). LOCATION DOWNTOWN GRAND RAPIDS. TIME 14:05 LOCAL. W8ABC."*
- Transmits it over the air immediately (it keys even over a busy channel; BREAK BREAK still suppresses it).
- Posts it to the shared message log, tagged **SKYWARN**.
- Records it in the active net's session journal (if a net is running).

If a report is below threshold, the server rejects it and the reason is shown in the composer.

### Net scripts (preamble & closing)

Set an opening **preamble** and a **closing** script in **Admin → Station → NCS / SKYWARN**. While a net is active, the NCS panel shows **READ PREAMBLE** and **READ CLOSING** buttons — clicking one transmits that script over the air and posts it to the message log (and into the session journal). Use the preamble to open the net (state its purpose and instructions) and the closing to sign off.

Scripts support placeholders that are filled in when read: `{callsign}`, `{name}`, `{location}`, `{date}`, `{time}`. If a script is blank, the button reports that none is configured.

### Round-table caller

To run a directed net, use the round-table controls below the roster:

- **CALL NEXT STATION** — picks the next checked-in station that hasn't been called yet this round, transmits *"Station <callsign>, do you have any traffic or comments?"*, highlights that row, and marks it called. After the last station it reports **Round complete**.
- Each roster row also has a **call** button to call that specific station out of order.
- **NEW ROUND** clears the "called" marks so you can go around again.

### Net announcements

While NCS mode is active, the system periodically transmits a net ID announcement at the configured interval (default 10 minutes). The listen-before-talk check prevents it from interrupting an active transmission.

### End-of-net journal

When you deactivate NCS mode, a session journal is automatically saved with the roster and transcript. It appears in the Journals panel and can be published to the public family journal like any other journal.

---

## 17. Browser notifications

Hearthwave can fire browser (OS-level) notifications when the tab is in the background — useful when the station is monitoring in another window or on a separate screen.

**Enabling notifications:**
1. Click the **NOTIFY** button in the top bar. It turns blue when active.
2. On first enable, the browser asks for notification permission. Grant it.
3. If you deny permission in the browser, the button shows an error and remains off. You will need to re-enable the permission in your browser settings.

**What triggers a notification:**
- A final RX transcript arrives (shows callsign + first 120 characters of the text)
- A SKYWARN alert fires from the NCS plugin (shows event name)

Notifications only appear when the Hearthwave tab is **not** in focus. If you are actively looking at the tab, no notification is shown.

**Disabling notifications:** Click **NOTIFY** again. The button returns to the unselected state and notifications stop.

This preference is saved to your account and restored across sessions and devices.

---

## 18. Text shortcuts reference

Hearthwave automatically expands common TTY, Q-signal, and CW abbreviations before transmitting.

### Common TTY/TDD abbreviations

| Abbreviation | Expands to |
|-------------|------------|
| `GA` | Go ahead |
| `SK` | End of contact |
| `AR` | End of message |
| `BK` | Break |
| `HH` | Error — disregard |
| `NR` | Number |
| `MSG` | Message |
| `ANS` | Answer |
| `PLS` | Please |
| `TMW` | Tomorrow |
| `WRK` | Work |
| `CUL` | See you later |

### Q-signals

| Code | Meaning |
|------|---------|
| `QRZ` | Who is calling me? |
| `QSL` | I acknowledge receipt |
| `QRM` | Interference |
| `QRN` | Static / noise |
| `QRO` | Increase power |
| `QRP` | Reduce power |
| `QRT` | Stop transmitting |
| `QRX` | Stand by |
| `QSO` | Contact / conversation |
| `QTH` | Location |
| `QRB` | Distance |
| `QSY` | Change frequency |

### Callsign phonetics

Callsigns in outgoing messages are automatically spelled in NATO phonetics when transmitted via TTS. For example, `KD9ABC` is spoken as *"Kilo Delta 9 Alpha Bravo Charlie"*.

You do not need to type phonetics manually.

---

## 19. Voice PTT (browser microphone)

The PTT button captures audio from your browser microphone and transmits it
over the radio.

**To use Voice PTT:**

1. Click and hold the **PTT** button (top bar) — or press and hold the **Space
   bar** anywhere on the page.
2. Speak your message. A pre-roll buffer captures the first ~200 ms before you
   press, so the first syllable is never clipped.
3. Release the button or Space bar. The audio is sent to the server, synthesised
   to speech, and transmitted.

**Keyboard PTT:** The Space bar triggers PTT when focus is not inside a text
field. This lets you keep your hands on a keyboard during a net.

**Notes:**
- The PTT button shows **PTT●** (with a dot) while recording.
- The browser will ask for microphone permission on first use.
- If the channel is busy (another user is transmitting), PTT is disabled until
  the channel clears.
- Listen-only mode disables PTT entirely.

---

## 20. CW (Morse code) receive mode

When the station is configured for CW mode, incoming audio is decoded by an FFT-based CW decoder instead of Whisper STT. This is useful for monitoring morse code transmissions.

### Configuring CW mode (admin)

1. Open the **Admin** panel.
2. Set the `rx_mode` field to `"cw"` (voice mode uses `"voice"`).
3. Changing this setting restarts the STT worker — expect a brief interruption in transcription.

### How CW decoding works

| Parameter | Value |
|-----------|-------|
| Tone detection range | 400–1200 Hz |
| Bandpass filter | ±100 Hz around detected tone |
| WPM estimation | Adaptive (adjusts to the operator's sending speed) |

Decoded morse appears in chat as **[RX]** entries, identical in appearance to voice transcription.

---

## 21. Admin Settings dialog (admin)

These settings live in the **Settings** dialog, opened from the **Settings** entry in the account chip menu. Every user sees a **Preferences** tab (personal options — see [section 13](#13-settings)); admin accounts additionally see the three admin-only tabs described below. A single **Save** button in the dialog footer commits changes across every tab at once and leaves the dialog open with a confirmation.

- **Station tab** — station identity (callsign, name, location, default TTS voice, Gemini API key, journals directory), user accounts, and NCS / SKYWARN zone.
- **System tab** — technical server-side settings (audio devices, STT, PTT, VOX, and advanced options).
- **Plugins tab** — install, enable/disable, configure, reload, and uninstall plugins (see [section 22](#22-plugins)). Per-plugin settings — including those for the MeshCore and Meshtastic example plugins — live here.

### System tab settings

| Setting | Description |
|---------|-------------|
| VAD threshold | Sensitivity of voice activity detection. Lower = more sensitive; higher = requires stronger signal. Changing this restarts the STT worker. |
| Whisper model | Which Whisper model the server uses for live (streaming) transcription. Changing this restarts the STT worker. |
| Final-pass model | Optional larger model that re-transcribes each completed transmission in full once the other station unkeys, replacing the live partial text with a more accurate final. The final pass never truncates a long transmission or drops a callsign the live pass already heard — if it returns a short or empty result, the complete live text is kept. Choose **Auto** (default on new installs) to use the best staged model — `large-v3-turbo` > `distil-large-v3` > `large-v3` — or silently run single-pass when none is staged; the panel shows what Auto resolved to. Choose **Off** for single-pass, or name a model explicitly. The model must be staged first (see below) and adds ~1.5 GB RAM only while active. Changing this restarts the STT worker. |
| Final-pass device | Where the whole-utterance final pass runs: `auto` (GPU if a ROCm GPU is present, else CPU), `gpu`, or `cpu`. Requires the ROCm deployment profile to use GPU. See [section 25](#25-deployment-profiles-and-gpu-acceleration-admin). |
| Adaptive squelch | Tracks the channel noise floor and opens at 3× it, so weak carriers pre-trigger audio capture instead of clipping the first word. Leave off on consistently strong signals; enable on noisy or distant channels. Restarts the STT worker. |
| Noise profile denoise | Samples the channel's noise floor while the squelch is closed and uses it as the denoiser's noise estimate (stationary spectral gating), instead of letting the denoiser guess from the speech itself. Utterances with no usable quiet span beforehand (fresh start, first over after transmitting) automatically fall back to the standard denoise. Off by default — an experimental setting; compare with the eval harness's `--noise-profile auto` before leaving it on. Restarts the STT worker. |
| Gain control | How received audio is leveled before transcription. **Dynamic AGC** (default) rides the level continuously with a fast attack and slow release; **Simple RMS** applies one steady gain to hit a target loudness (gentler, no pumping); **Off** disables leveling entirely. If transcription seems to mishear during loud/quiet swings or "breathy" passages, try Simple RMS. Tune objectively with the STT eval harness's `--gain-mode {agc,rms,off}` flag against captured audio. Changing this restarts the STT worker. |
| TX conditioning | Band-limits, compresses, and levels synthesized speech before it drives the radio's microphone input — clearer over narrowband FM. Browser read-aloud is unaffected. Takes effect immediately. |
| STT debug capture | Saves raw / segmented / processed audio plus transcripts for each utterance (and the squelch-closed noise clip as `noise.wav` when Noise profile denoise is on), for offline word-error-rate evaluation. For tuning only — leave off in normal operation. Restarts the STT worker. |
| Saved Phrases | A list of phrases Whisper is pre-loaded with as vocabulary hints to improve recognition accuracy. Common radio phrases ("break break", "QSL", "copy that") are included by default. Add any group-specific phrases — net names, operator handles, local shorthand — to help Whisper recognise them consistently. Changes take effect immediately without an STT restart. |
| PTT mode | How PTT is keyed: `manual`, `serial`, or `vox` (voice-operated transmit — keys automatically based on audio level). |
| PTT port / line | Serial port and control line used when PTT mode is `serial`. |
| VOX primer tone | When enabled, a short tone is prepended to each transmission so a VOX-keyed radio is fully keyed before the message starts. Silence alone does not reliably trip many VOX radios; the tone guarantees the radio is open when the speech begins. Off by default. Also configurable: tone duration in milliseconds. Enable this only if your radio uses VOX keying. |
| Monitor passthrough | When enabled, audio captured from the radio input is simultaneously played back through the output device. Useful when the radio is not directly audible at the operator position. Does not require a server restart. |
| Attendance tracking | Enable or disable automatic callsign recording in the Stations panel. When disabled, the panel still exists but callsigns are not recorded automatically. |

> Plugin settings — including the MeshCore and Meshtastic mesh-bridge example plugins — are no longer on the System tab. They now live on the **Plugins** tab (see [section 22](#22-plugins)).

> Changes to VAD threshold, Whisper model, Final-pass model, Adaptive squelch, Noise profile denoise, Gain control, or STT debug capture trigger a live STT worker restart and will briefly interrupt transcription. TX conditioning and Saved Phrases changes take effect immediately.

> Not sure which Gain control / Noise profile denoise / Whisper model combination is best for your radio and environment? The **Run STT calibration…** button on this tab automates finding out — see [section 26](#26-stt-calibration-wizard-admin).

### Staging the final-pass model

The final-pass model is not bundled — download it once on an internet-connected machine, then it loads automatically on the first finished transmission:

```bash
# Docker (host volumes):
bash setup.sh --final-model distil-large-v3
# Portainer (named volumes):
bash prereq.sh --final-model distil-large-v3
# Native install:
python bootstrap_models.py --model small.en distil-large-v3
```

With **Final-pass model** set to `auto` (the default on new installs) the staged model is picked up on the next Listen toggle — nothing else to configure. `large-v3-turbo` is also available (`--final-model large-v3-turbo`): near `large-v3` accuracy at a fraction of the decode cost, preferred by Auto when staged. On a CPU-only host a long transmission may take roughly its own duration to produce the improved final; live partials are unaffected.

> **Upgrading from an earlier version?** Installs that ever saved server settings have `whisper_model_final: ""` (explicit **Off**) persisted in `config.json`, and stay off — deliberately, so an operator who turned the second pass off doesn't get it back after an upgrade. Set the panel to **Auto** once to opt in.

---

## Tips

- **GMRS family licences:** One callsign covers your whole household. Add each person as a separate contact with the same callsign — only the name needs to differ. In NCS mode, each family member checks in as their own entry in the roster.
- **Multiple users:** Each family member signs into their own account. All clients see the same chat in real time — both received audio (RX) and outgoing transmissions (TX) — but each person's profanity filter, listen-only mode, and display preferences are independent.
- **Across devices:** Your settings follow you. Sign in on your phone and get the same preferences as your tablet.
- **Dark environments:** Toggle dark/light mode from the account menu (desktop) or the hamburger settings drawer (mobile). The public `/journal` page automatically adapts to your browser's dark mode preference.
- **Slow or noisy transcription:** Adjust the VAD threshold on the **System** tab of Settings (admin). Lower values (e.g. 0.3) are more sensitive; higher (e.g. 0.7) require a stronger signal. The setting can also be changed directly in `config.json` (`vad_threshold`).
- **Wrong time spoken in reports:** Times embedded in incident reports, spot reports, net scripts (`{time}`/`{date}`), and check-in reminder schedules use the backend container's clock. The compose files mount the host's `/etc/localtime` so this is local automatically on Linux hosts; on other platforms, set a `TZ` environment variable on the backend service (e.g. `TZ=America/Detroit`). Chat timestamps are unaffected — they always render in your browser's timezone.
- **FCC lookups not working:** The online indicator (dot in the top bar) shows internet connectivity. If it is gray, FCC verification is unavailable until connectivity is restored.
- **Session locked out?** Wait 15 minutes or ask an admin to use **Admin → Users → Reset lockout**.
- **On a phone:** The app automatically shows the mobile interface — bottom tabs for Chat, NCS, Journals, Status, and Settings. Tap the ≡ menu for dark mode and your account. **On a tablet**, you get the desktop layout with larger, touch-friendly controls.
- **NCS traffic levels:** Use **IN-n-Out** for stations who only have a moment; use **Short Term** for those who can stay a few minutes but need to leave soon. Both are tracked in the roster and included in the end-of-net journal.
- **Neighborhood watch groups:** Create one account per volunteer. Assign **listen-only** mode to members who should monitor but not transmit, and reserve TX-capable accounts for designated net control operators. The NCS roster and SKYWARN alerts work the same way they do for family nets — the watch's patrol log is automatically saved as a session journal at end of net.

---

## 22. Plugins

Hearthwave supports **installable third-party plugins** — self-contained add-ons that attach new capabilities to the radio pipeline without changing the core server. Plugins are installed and managed from the **Plugins** tab of the admin Settings dialog. Several plugins ship with Hearthwave: the **NCS / SKYWARN** net-control feature ([section 16](#16-ncs--net-control-station-mode)) is built in, and **MeshCore** ([section 22b](#22b-meshcore-example-plugin)) and **Meshtastic** ([section 22c](#22c-meshtastic-example-plugin)) are seeded as example plugins you can study, enable, or replace with your own.

> **Trust warning:** Plugins run with **full server access** — they can read and transmit on the radio, touch your contacts and configuration, and reach the network. Only install plugins from sources you trust. The Plugins tab is admin-only and shows this warning prominently.

---

## 22a. Installing and managing plugins

The **Plugins** tab is visible only to admin accounts. It lists every installed plugin, each with its own controls.

**What a plugin is:** a directory containing a `plugin.py` file, stored under `/data/plugins/<id>/` — the directory name is the plugin's id. You can also install one as a `.zip` archive from the Plugins tab.

**Per-plugin controls:** for each installed plugin the list shows:

- An **enable / disable toggle.** Disabling a plugin hides its UI and stops its functionality immediately; the plugin stays installed and can be re-enabled later.
- The plugin's **auto-generated settings form** — every setting the plugin declares, edited inline. (Each plugin's settings are stored under `config["plugins"][<id>]`.)
- The plugin's **version** and a **conflicts note** when one applies (for example, MeshCore and Meshtastic are mutually exclusive — see below).
- **Reload** — re-reads the plugin's code from disk, picking up changes without restarting the server.
- **Uninstall** — removes the plugin and its directory.

**Installing a plugin:** click **Install plugin (.zip)** and choose a `.zip` archive. The archive is unpacked into `/data/plugins/<id>/` and the plugin loads immediately.

**Hot-reload:** install, reload, and uninstall all take effect live — no server restart is required. If a plugin ever misbehaves after a reload, restarting the server is a safe fallback that reloads every plugin cleanly from disk.

---

## 22b. MeshCore example plugin

The MeshCore plugin forwards every message you transmit onto a [MeshCore](https://meshcore.co.uk/) LoRa mesh network, so your group stays in contact even where there is no GMRS coverage or internet. It ships as an **example plugin** seeded into `/data/plugins` on first run and is **disabled by default**; an admin enables it from the Plugins tab.

> **Mutually exclusive with Meshtastic:** enabling MeshCore automatically disables the Meshtastic plugin, and vice versa. Only one mesh bridge runs at a time.

**What it does**

- Every message that goes over the air is also sent to the mesh, **prefixed with the sender's name** (e.g. `Ben: heading home`), so mesh-only members know who is talking.
- It is **outbound only** — messages *received* on the radio are never forwarded to the mesh. Only what your station transmits is bridged.
- Because it taps the transmit pipeline after all checks, a message blocked by NCS **BREAK BREAK** is never forwarded either.
- Forwarding is best-effort and never delays or blocks the radio transmission itself; if the mesh link is busy or down, the over still goes out on the radio normally.

**What you see as an operator**

When the plugin is on, the message box shows a live character counter (e.g. `MeshCore · 18 / 135`) and limits what you type so the message plus the name prefix fits one mesh packet. The limit is the configured **max packet length** minus your prefix length, so a longer display name leaves a little less room. The counter turns red at the limit.

**Settings (Plugins tab)**

Enable the plugin from the Plugins tab and edit its settings there:

| Setting | Description |
|---------|-------------|
| Device | Serial device of the MeshCore Companion radio (e.g. `/dev/ttyUSB0`). In Docker the port must also be passed into the container (see below). |
| Baud rate | Serial speed of the Companion link (default `115200`). |
| Max packet length | Characters per mesh packet, **including** the sender-name prefix (default `140`). This drives the message-box character limit. |
| Channel index | Which MeshCore channel to transmit on (default `0`). |
| Name separator | Joins the sender name and the message on the mesh (default `": "` → `Alice: hello`). |

Changes reconnect (or disconnect) the serial link immediately — no server restart needed.

- Connect a MeshCore **Companion** radio to the server by USB.
- In a Docker install, the serial device must also be passed into the container: uncomment the MeshCore `devices:` line in `docker-compose.yml` and set it to your host's port. The optional `meshcore` Python package must be installed for the link to come up; without it the plugin still loads and lists, but logs a hint and can't connect when enabled.
- The default max packet length (140) is a starting point — confirm the limit for the MeshCore firmware you are running.

---

## 22c. Meshtastic example plugin

The Meshtastic plugin is the second mesh-bridge example seeded into `/data/plugins` on first run. It works just like MeshCore — every transmitted message is mirrored, outbound only, onto a [Meshtastic](https://meshtastic.org/) mesh, **prefixed with the sender's name** — and is **disabled by default**.

> **Mutually exclusive with MeshCore:** enabling Meshtastic automatically disables MeshCore, and vice versa. Only one mesh bridge runs at a time.

When enabled, it adds the same live character counter under the message box, showing its own hint (e.g. `Meshtastic · 18 / 200`) and capping typing so the prefixed message fits one packet.

**Settings (Plugins tab)**

| Setting | Description |
|---------|-------------|
| Device | Serial device of the Meshtastic radio (e.g. `/dev/ttyUSB0`). In Docker the port must also be passed into the container. |
| Max packet length | Characters per mesh packet, including the sender-name prefix. Drives the message-box character limit. |
| Channel index | Which Meshtastic channel to transmit on. |
| Name separator | Joins the sender name and the message on the mesh. |

Meshtastic has no baud-rate setting (the device link is configured differently from MeshCore). Changes reconnect the link immediately — no restart.

---

## 22d. Writing your own plugin

The two mesh-bridge plugins above are seeded into `/data/plugins` as references — copy one as a starting point for your own. A plugin is a directory with a `plugin.py` that subclasses `BasePlugin` and hooks into the RX/TX pipeline (receiving messages, queueing transmissions, capping the message box, and reacting to settings changes). It exposes its settings declaratively — the app renders the form, so a plugin ships no browser code. For the full hook reference, the settings-form schema, the TX-composition / character-limit API, and packaging your plugin as an installable `.zip`, see the authoring guide at [`docs/plugins.md`](docs/plugins.md).

---

## 23. FCC compliance and remote access

Hearthwave allows family members to send text-to-speech messages to the base station over the internet. This section explains how that is designed to comply with FCC Part 95 GMRS regulations and what it means for your licence.

> A full rule-by-rule legality breakdown — with verbatim 47 CFR Part 95E citations, the remote-control vs. repeater-linking distinction, and disclosure of every automated transmission — is published at [Legality & FCC compliance](https://xpiatio.github.io/Hearthwave/legality.html).

### What it is: remote control, not an internet gateway

An internet repeater gateway (sometimes called RoIP or a VoIP bridge) takes audio received from a radio in one location, streams it across the public internet, and retransmits it from a different radio elsewhere. The FCC prohibits this type of internet interconnection on GMRS under Part 95.1749 — GMRS is licensed as a localized family and community service, not a globally-linked network.

Hearthwave does not do this. When a family member sends a message from a phone or browser over the internet, that message travels to your local base station server and is spoken by the TTS engine through the local radio. Nothing received from the air is forwarded across the internet to another transmitter. The base station is the end destination, not a bridge.

This is equivalent to a licensed operator sitting at the base station microphone — except the "microphone" is a text input accessed remotely. The FCC calls this a **remote control point** (§ 95.1745), which is permitted provided the station is protected against unauthorized transmissions.

### Access controls

Because family members can trigger transmissions from outside the home, Hearthwave requires authentication for every connection:

- Each family member has their own password-protected account
- Session tokens are validated before any radio access is granted
- Accounts can be restricted to listen-only mode to prevent TX entirely
- Accounts lock after three incorrect password attempts
- Only your administrator can create new accounts

Do not share your password or admin credentials with anyone outside your licensed family unit. Under a GMRS licence, only family members covered by that licence may initiate transmissions.

### What administrators should verify

If you expose Hearthwave to the public internet (outside your home network):

1. **Use TLS** — run a reverse proxy (nginx, Caddy) with a valid HTTPS certificate in front of the app; without it, session tokens travel in plaintext
2. **Restrict accounts to your licensed family unit** — do not create TX-capable accounts for unlicensed individuals
3. **Use listen-only accounts for monitoring** — if anyone outside the licence needs to hear the station, create a listen-only account so they can listen but cannot key the radio

The NCS plugin contacts `api.weather.gov` for SKYWARN alerts and the FCC API for callsign verification. Both are outbound read-only requests from your server and do not create any radio interconnection.

---

## 24. Transcription vocabulary biasing

Both transcription passes — the fast live pass and the optional higher-accuracy final pass — are biased toward radio vocabulary: the NATO phonetic alphabet (Alpha through Zulu), common procedure words (Roger, Wilco, Over, Out, Break, etc.), and standard Q-codes (QRM, QRN, QSB, QSY, etc.). On top of that built-in list, Hearthwave automatically includes the callsigns of all your saved contacts, so the recognizer is primed for the station IDs it is most likely to hear on your channel.

Because Whisper's initial-prompt budget is limited, callsigns are prioritized over general keywords. Only the most-recently-added contacts (approximately 15) are included when the contact list is long — if you have many saved stations, the newest or most active ones are most likely to benefit.

### How to use

Vocabulary biasing is active by default — no setup required. The built-in radio keywords are always present. Your contacts' callsigns are added automatically as you build your contact book.

The bias refreshes live: adding, editing, or deleting a contact or a saved phrase updates the vocabulary immediately for the next transmission. If you want to force a rebuild — for example after importing a batch of contacts — use the **Rescan vocabulary** button in **Settings → server config** (near the saved-phrases box). After rescanning, a confirmation shows how many terms and callsigns are now active.

To add your own domain-specific terms (net names, repeater IDs, local place names, unusual callsign prefixes), enter them in the **Saved phrases** box in server config. Each entry contributes to the vocabulary budget alongside the built-in keywords.

---

## 25. Deployment profiles and GPU acceleration (admin)

Hearthwave ships with three Docker deployment profiles. The profile you choose determines which compose file and setup script to run, and whether the STT final pass can be offloaded to a GPU.

### Deployment profiles

| Profile | Compose file | Setup script | Image source |
|---|---|---|---|
| **CPU** (default) | `docker-compose.yml` | `setup.sh` / `setup-cpu.sh` | Prebuilt — pulled from registry |
| **AMD GPU (ROCm)** | `docker-compose.rocm.yml` | `setup-rocm.sh` | Built locally (~28 GB) — **not published** |
| **NVIDIA GPU (CUDA)** | `docker-compose.cuda.yml` | `setup-cuda.sh` | **Stub only — not yet validated** |

The CPU profile is recommended for most users. The ROCm profile is available for servers with a supported AMD GPU and requires building the Docker image locally — it is not available as a prebuilt download.

> **CUDA note:** The NVIDIA CUDA profile is a documented stub. The compose file and setup script are in place but have not been validated. Do not rely on it for production use.

### GPU-accelerated final pass (AMD ROCm)

The whole-utterance final pass — where a larger Whisper model re-transcribes each completed transmission in full — can run on an AMD GPU via ROCm. The live streaming pass always stays on CPU, where it runs fastest on most hardware.

**Why this matters:** On a CPU-only host, the final pass competes with the streaming pass for CPU cores. On a Radeon 680M (a typical integrated APU), this raised streaming latency by about 105% while a final pass was running. Offloading the final pass to the GPU reduced that to roughly 3%. The win is contention relief, not raw transcription speed.

### `stt_final_device` setting

Control where the final pass runs with the `stt_final_device` key in `data/config.json` (System tab of Settings is the recommended way to change it):

| Value | Behaviour |
|---|---|
| `auto` (default) | Uses the GPU if a ROCm GPU is detected; falls back to CPU otherwise |
| `gpu` | Always attempts GPU; falls back to CPU if loading fails |
| `cpu` | Always uses CPU |

Setting `stt_final_device` to `cpu` takes effect on the next STT worker restart and requires no rebuild or redeployment.

### ROCm prerequisites

To use the ROCm profile your server must meet these requirements:

- An AMD GPU with the **amdgpu / ROCm kernel driver** loaded on the host
- The host user running Docker must be in the **`render` group** (the container uses `/dev/kfd` for GPU access)
- **`HSA_OVERRIDE_GFX_VERSION`** — set by `setup-rocm.sh` to `10.3.0` by default. This override is required for GPUs not officially listed in ROCm's supported-hardware table (such as the Radeon 680M / gfx1035). Adjust if your GPU uses a different GFX version.

The ROCm Docker image is built locally by `setup-rocm.sh`. This takes considerable time and disk space (~28 GB) and is a one-time operation. The image is not pushed to any registry; it stays on your machine.

### Starting with the ROCm profile

```bash
# Build the image and stage the HF-format final-pass model
./setup-rocm.sh

# Start the stack
docker compose -f docker-compose.rocm.yml up -d
```

The final-pass model (`distil-large-v3`) is staged in HF transformers format by `setup-rocm.sh` alongside the CT2 model used by the CPU path.

### Automatic fallback

If no ROCm GPU is detected (or if the GPU fails to load at runtime), the final pass falls back to CPU automatically. The streaming pass is never affected — if even the CPU final pass fails, the server falls back to plain finals (the last live partial). Failures in the final pass never interrupt transcription.

### Rollback

To switch back to CPU-only operation at any time:

- **No rebuild needed:** set `stt_final_device` to `cpu` in Settings (System tab) and restart the STT worker.
- **Full rollback:** set `COMPUTE_BACKEND=cpu` and restart with `docker-compose.yml` instead of `docker-compose.rocm.yml`.

---

## 26. STT calibration wizard (admin)

Picking the right **Gain control**, **Noise profile denoise**, and **Whisper model** settings (see [section 21](#21-admin-settings-dialog-admin)) for a given radio, room, and noise environment normally means changing one setting at a time and listening for whether transcription got better or worse. The calibration wizard automates this: it has you read a fixed, known passage into the radio, then objectively scores several setting combinations against what Whisper actually heard.

### How to use

1. Open **Settings → System tab** (admin) and click **Run STT calibration…**.
2. The wizard displays a short passage (the preamble to the Declaration of Independence — chosen because it is long enough and phonetically varied enough to be a meaningful test). Click **Start Recording**.
3. Key up your radio and read the passage aloud at a natural pace, the way you'd normally talk on the air. When you're done, click **Stop & Analyze**.
4. Hearthwave replays what it captured through several combinations of gain mode, noise-profile denoise, and Whisper model, and shows a results table ranked by word-error-rate (WER) — the percentage of words each combination got wrong. The lowest-WER row is flagged **Recommended**.
5. Click **Apply** on whichever row you want — the recommended one, or any other if you'd rather trade some accuracy for a faster/lighter model. This saves the setting the same way changing it manually on the System tab would, and restarts the STT worker.

### Notes

- The recording is capped at 3 minutes as a safety net in case **Stop & Analyze** is never clicked; there's no need to rush.
- Testing multiple Whisper models means the wizard loads each one in turn — expect the analysis step to take longer than a sweep of just gain mode and noise profile would.
- Only models already downloaded to `Models/STT` are swept (Hearthwave never downloads models at runtime). To include a model in the sweep, stage it first with `python bootstrap_models.py --model <name>`.
- Nothing is changed until you click **Apply** — running the wizard and closing the dialog without applying leaves your current settings untouched.
- For deeper, scriptable tuning (custom recordings, additional decode parameters, A/B against your own labelled audio) see the offline word-error-rate eval harness referenced in [section 24](#24-transcription-vocabulary-biasing).

---

## 27. AAC interface (symbol-button communication)

The AAC interface turns Hearthwave into an **AAC communication device that transmits** — the same interaction model as the symbol-button speech devices used by many non-speaking people (AAC stands for Augmentative and Alternative Communication). Instead of typing, you tap large picture buttons to build a message, then press one big **SEND** button and Hearthwave speaks it over the radio in your voice.

It is a per-user setting: one family member can use the AAC screen full-time while everyone else keeps the standard interface.

### Turning it on and off

1. Open **Settings → Preferences** and switch on **AAC Interface (symbol buttons)**, then **Save**.
2. The whole app is replaced by the AAC screen. The setting is remembered per user — signing in from any device (or reloading the page) lands straight on the AAC screen.
3. To leave, tap the **✕** button in the top-right corner. A confirmation appears with two large buttons — **Yes, exit** returns to the standard interface (and turns the preference off). This confirmation exists so the exit can't be hit by accident mid-conversation.

> **Caregiver note:** the Settings dialog is not reachable from inside the AAC screen — the ✕ Exit button is the only way back. Everything an AAC user needs day-to-day (composing, sending, editing buttons) is available without leaving.

### The AAC screen, top to bottom

| Area | What it does |
|---|---|
| Header | Your name and callsign, connection status, ✏️ edit-mode toggle, ✕ exit |
| Recent messages | The last three transmissions heard or sent, updated live |
| Sentence strip | The message you are building, one chip per button press, with **Undo** (removes the last word) and **Clear** |
| Category tabs | Groups of buttons — the starter set is **⭐ Core**, **📻 Radio**, **💬 Status**, **🙋 About me** |
| Button grid | Large emoji + label buttons; tapping one adds its text to the sentence strip |
| SEND | Transmits the sentence strip over the radio, exactly like the standard TRANSMIT button. While the radio is keyed it becomes an **ABORT** button |

### Composing and sending

Tap buttons in any order — each press appends its phrase to the sentence strip. **Undo** removes the most recent press (whole phrase, not one letter); **Clear** empties the strip. Press **SEND** when ready: the message is spoken on the air in your TTS voice, appears in everyone's message log, and the strip clears for the next message.

Buttons can carry placeholders: `{Name}` becomes your operator name and `{callsign}` becomes your callsign at the moment you press SEND — so one **Check in** button says *"This is WRXB123 checking in"* for whoever owns the grid. Any other `{...}` placeholder is silently dropped rather than opening a typing prompt.

If your account is set to **Listen-only mode** ([section 13](#13-settings)), the SEND button stays disabled and says so.

### Editing your buttons

Every user gets their own grid, and it can be reshaped freely:

1. Tap the **✏️ pencil** in the header — edit mode. Button borders turn dashed and SEND is disabled so taps can't transmit.
2. **Change a button:** tap it. A dialog lets you set the emoji, the short label shown on the button, and the (optionally longer) spoken text. **DELETE** removes it after a confirmation.
3. **Add a button:** tap the dashed **＋ Add** tile at the end of the grid.
4. **Categories:** the **Category** button renames the current tab (or deletes it, buttons and all); **＋** next to the tabs adds a new category.
5. Tap the pencil again to leave edit mode.

Every change saves immediately to your account on the station — customize once, and the same grid appears on the tablet, the phone, and the desktop. Limits: 20 categories, 40 buttons per category.

### Tips

- The starter grid is radio-flavored on purpose (QSL, Say again, 73, check-in), but nothing stops you from making it a general communication board — add **I'm hungry**, **Watch TV?**, family names, whatever gets used.
- Emoji come from the standard emoji keyboard on your device — when editing a button, use it to pick any picture you like.
- The AAC screen uses extra-large touch targets everywhere and works well on a wall-mounted or lap tablet.
- Deleting things you regret? The four starter categories can be rebuilt by hand; as a last resort, an admin can restore the default grid by removing the `aac_grid` entry from your user's `prefs` in `/data/users.json` on the server.

---

## 28. Home screen & interface levels

On desktop and tablet, signing in lands you on a **Home screen** — a small grid of activity cards — instead of dropping you straight into the full station console. (Phones keep the mobile bottom-tab layout and AAC Interface users keep the AAC screen; both are unaffected by the Home screen.)

### Activity cards

| Card | Shown when |
|---|---|
| **💬 Chat** | Always. Subtitle shows a new-message count if there's unread chat since you last left Home. |
| **🏠 Family** | Always, for every role including Kid accounts. Subtitle shows "Everyone OK" or a missed-check-in count; the card turns amber if anyone has missed a check-in. See [section 30](#30-family-activity). |
| **🏘 Neighborhood** | Always, for every role including Kid accounts. Subtitle shows "Net running now" or the next scheduled net; a banner appears on the card when a street alert was issued in the last 30 minutes. See [section 31](#31-neighborhood-activity). |
| **🎙 Net Control** | Only for accounts on the **Operator** interface level, and only when the NCS plugin is enabled (see [section 22](#22-plugins)). |

Click a card (or focus it and press **Enter**) to open it:

- **Chat** opens the full station console — chat display, spectrogram, quick messages, message box, and whichever panels you have toggled on.
- **Family** opens the full-screen presence board (see [section 30](#30-family-activity)).
- **Neighborhood** opens the full-screen watch activity (see [section 31](#31-neighborhood-activity)).
- **Net Control** opens the same station console with the NCS panel already showing.

### Returning to Home

- Click the **home icon** in the top bar, or
- Press **Escape** from anywhere in the station console.

Either one takes you back to the Home screen without signing out; your connection and any in-progress typing elsewhere are unaffected.

### Interface level — Simple vs. Operator

Every account has an **Interface level**, set on the **Preferences** tab of Settings (click your account chip → **Settings**): **Simple** or **Operator**. It's a per-user preference, saved to your account like everything else in Preferences — click **Save** in the dialog footer to apply it.

- **Simple** (the default) shows only what a casual family member or watch volunteer needs: the Chat card on Home, and inside the station console the core send/receive controls, contacts, listen-only, read-aloud, and notifications.
- **Operator** unlocks the controls a net-running or technically-minded user wants:

| Adds | Where |
|---|---|
| **Net Control** card | Home screen (also requires the NCS plugin enabled) |
| **STATIONS** (session attendance) panel | Top bar toggle |
| **JOURNAL** panel | Top bar toggle |
| **WATERFALL** (spectrogram) toggle | Top bar toggle |
| **LEVEL** (RX audio level meter) toggle | Top bar toggle |
| **NCS MODE** button | Top bar (admin accounts only, and only when the NCS plugin is enabled) |
| Service mode switch (GMRS ⇄ FRS) | Top bar |
| **LISTEN** / **LISTENING** (STT start/stop) button | Top bar |
| **Clear chat log** button | Top bar (admin accounts only) |

Switching between Simple and Operator doesn't lose any data — panels and settings gated behind Operator simply reappear if you switch back.

---

## 29. Accessibility options

Text size and contrast are per-user preferences on the **Preferences** tab of Settings, alongside the Interface level toggle. Both apply immediately across the whole app, not just chat text.

### Text size

Four steps are available — **A** (100%, default), **A+** (125%), **A++** (150%), **A+++** (200%). Pick one with the text-size buttons in Settings → Preferences. Scaling applies to the entire interface, including the Home screen cards, buttons, and chat log, and the layout reflows to avoid horizontal scrolling at any step.

### High Contrast

The **High Contrast** switch in Settings → Preferences increases color contrast throughout the app — most noticeably a pure black background with white text when combined with dark mode (or a plain white background with black text in light mode), plus stronger, more saturated primary and error colors. It works independently of the dark/light mode toggle ([section 13](#13-settings)), so you can combine either mode with High Contrast on or off.

### Keyboard navigation

The whole app, including the Home screen, is operable from the keyboard:

- **Tab** moves focus into the Home screen's activity card grid; the arrow keys (**↑ ↓ ← →**) move focus between cards without leaving the grid.
- **Enter** (or **Space**) activates the focused card, quick message, or button anywhere in the app.
- **Escape** returns to the Home screen from the station console (see [section 28](#28-home-screen--interface-levels)).
- Focused controls show a visible focus ring (a colored outline) so keyboard users can always see where focus is — this is especially clear with High Contrast enabled.

---

## 30. Family activity

The Family activity is a presence-and-check-in board for the whole household — who's been heard on the radio recently, who's tapped "I'm OK" today, and who's overdue for a check-in. It is available to **every account, including Kid accounts**, at **both interface levels** (Simple and Operator) — unlike Net Control, it is not an Operator-only feature.

### Opening the Family activity

- **Desktop / tablet:** click the **🏠 Family** card on the [Home screen](#28-home-screen--interface-levels). The card's subtitle shows "Everyone OK" or a missed-check-in count, and turns amber if anyone is overdue.
- **Mobile:** tap the **Family** tab in the bottom navigation (see [section 2a](#2a-mobile-interface)) — it's there for both interface levels, not just Operator.
- Click the **back arrow** (top-left) or press **Escape** to return to Home (or to Chat, on mobile).

### The presence board

Every family member with an account gets a card showing their avatar, name, a status chip, and a relative "last heard" time.

| Status chip | Meaning |
|---|---|
| **OK ✓** *(with time)* | This person tapped **I'm OK** today. |
| **On air** | This person transmitted within the last 10 minutes — takes priority over a same-day OK. |
| **No word** | Neither of the above. |
| **Missed check-in** *(amber)* | That member has a check-in reminder (set by an admin) whose deadline has passed today with no OK check-in yet. This overrides whatever the chip would otherwise say, so an overdue check-in is never hidden behind an old "OK". |

A day rollover clears "Missed check-in" automatically — it's recomputed continuously from the reminder time and today's check-in, not a log you have to clear by hand.

> **What updates "last heard":** only that person's *own* transmission does — Hearthwave does not try to guess presence from a callsign it hears spoken by someone else. There's no historical log either; the board always shows current status, not a timeline.

### The "I'm OK" button

The large green **I'm OK** button at the center of the Family activity does three things at once when pressed:
1. Speaks **"Family status: {your name} is okay."** over the air, in your voice — unless your account is in [Listen-only mode](#13-settings), in which case the on-air announcement is skipped but the next two steps still happen.
2. Posts the same line to the shared chat log for every connected user to see.
3. Marks you **OK** on the presence board for today, clearing any "Missed check-in" chip.

**I'm OK is available to every role, including Kid accounts** — it's treated as a safety feature rather than a normal transmission, so it isn't affected by the kid quick-message restriction described below.

### Quick messages in the Family activity

The row of preset buttons below the I'm OK button is a **separate list from the quick-messages bar** used in the main Chat view ([section 5](#5-quick-messages)). This list is stored on your account on the server (not just in your browser), which is what lets a **Kid account** use it as an allow-list:

- **Kid accounts** see this same preset row in place of a free-text message box everywhere in the app — it is the *only* thing a kid account can transmit, sent exactly as written.
- **Adult and Admin accounts** can use the presets here as a shortcut, and still have the normal free-text message box in Chat.

**Migration note:** the first time your account connects after this feature shipped, whatever list you had customized in the Chat quick-messages bar (via its ⚙ editor) was copied once into this server-synced list. After that one-time copy, the two lists are independent — editing your Chat quick-messages bar going forward does **not** change what appears in the Family activity.

### Admin setup

#### Check-in reminders

Admin accounts (who are not also Kid accounts) see a **Check-in reminders** section at the bottom of the Family activity, with one row per family member:

- A **time** field (24-hour `HH:MM`) — the daily deadline by which that person should have tapped I'm OK.
- An **enable** switch — reminders are off by default per member.

Every change saves immediately; there is no separate save step. Only one daily time per member is supported (not a schedule of several reminders a day).

**Notifications:** if [browser notifications](#17-browser-notifications) are enabled and the tab is in the background, a notification fires the moment a member's card flips to "Missed check-in" — once per flip, not repeatedly.

#### Roles and Kid account presets

Roles (**Admin** / **Adult** / **Kid**) are set from **Settings → Users**, described in [section 15](#15-admin--managing-users). An admin can also edit any account's quick-message preset list (the one described above) from that same screen: click the **speech-bubble icon** next to a user's row to open the **Quick Messages** editor, add or remove phrases (up to 20, 1–200 characters each), and click **Save**.

For a **Kid** account, the list can never be saved empty — a kid account needs at least one preset to have anything to transmit — and none of its presets may contain `{` or `}` (placeholders like `{Name}` are a Chat-quick-messages-bar feature only; the server rejects them here). Adult and Admin accounts have no placeholder restriction.

---

## 31. Neighborhood activity

The Neighborhood activity is the base station for a neighborhood watch net: a roster of who's checked in, the next scheduled net, a place to report incidents on the air, a running log of everything that's been reported, and station-wide street alerts. Like the Family activity, it is available to **every account, including Kid accounts**, at **both interface levels** (Simple and Operator) — it is not an Operator-only feature.

### Opening the Neighborhood activity

- **Desktop / tablet:** click the **🏘 Neighborhood** card on the [Home screen](#28-home-screen--interface-levels). The subtitle shows "Net running now" or the day/time of the next scheduled net, and a recent street alert (see below) appears on the card for about 30 minutes after it's issued.
- **Mobile:** tap the **Neighborhood** tab in the bottom navigation (see [section 2a](#2a-mobile-interface)) — it's there for both interface levels, not just Operator.
- Click the **back arrow** (top-left) or press **Escape** to return to Home (or to Chat, on mobile).

### Net status and schedule

The top of the panel shows whether a net is active right now, and if not, when the next one is — computed from the weekly **Net Day** and **Net Time** an admin sets on the Station tab of Settings (see [section 13](#13-settings)). If an admin changes the schedule while you're connected, the card and panel update immediately — no refresh needed.

### Checking in

A single **check-in** button adds you to the roster. There's no form to fill out — your name, callsign, and location come straight from your account profile.

You can check in at any time, not just after a coordinator has started the net: an **early check-in** (before the net officially starts) reserves your spot on the roster and survives into the started net rather than being cleared. Checking in again later (for example, to signal you're still around) just updates your check-in time.

### Reporting an incident

The **Report an incident** button opens a short form with three fields:

- **Category** — one of five: **Suspicious activity**, **Hazard**, **Medical**, **Lost pet or person**, or **Utility outage**.
- **What happened?** — a required description.
- **Location** — a required location (e.g. "corner of 5th and Main").

Sending the report:
1. Speaks a standardized announcement over the air — category, description, location, time, and your callsign — unless your account is in [Listen-only mode](#13-settings), in which case the on-air announcement is skipped but the next two steps still happen.
2. Posts the same announcement to the shared chat log for every connected user to see.
3. Adds it to the incident log (below).

If the server rejects a report (for example, a missing location), the form reopens showing what to fix.

**Incident reports are not available to Kid accounts** — like any other on-air transmission, filing one keys the radio, and that's outside what a Kid account is allowed to do. Kid accounts can still check in and read the incident log and street alerts.

### Incident log

Every report ever sent appears in the **Incident log**, newest first, with a **Filter by category** dropdown (or "All"). Each entry shows the category, the time, the description, the location, and who reported it. The log is shared by every connected user and kept on the server — it's capped at the 500 most recent reports, so the oldest entries roll off automatically rather than growing the file forever.

### Street alerts

A **coordinator** (see below) can send a **street alert** — a short message (1–200 characters) meant for everyone, such as a road closure or a suspicious vehicle sighting. Sending one:

- Speaks "NEIGHBORHOOD ALERT" plus the message over the air (again skipped only in Listen-only mode) and posts it to chat.
- Shows a banner on every connected user's Neighborhood card/panel for about 30 minutes.
- Fires a [browser notification](#17-browser-notifications) for any user who has notifications enabled, even if their tab is in the background.

Street alerts reach **every connected user, including Kid accounts** — this is safety information for the whole household or watch group, not a transmit permission, so it isn't restricted the way sending an incident report is.

### Net status and round-table (coordinator only)

Coordinators additionally see:

- **Start net** / **End net** buttons.
- **Call next neighbor** — advances a simple round-table through the checked-in roster, one at a time.
- **New round** — clears who's been called so the round-table can start over.

**Ending a net saves a journal entry** — the checked-in roster and the net's duration are written to a session journal automatically, the same as ending an NCS net. It appears in the Journals panel ([section 11](#11-journals)) and can be published to the public family journal ([section 12](#12-family-journal-public-page)) like any other journal.

### Coordinator setup (admin)

Being a coordinator is a per-user grant, separate from the Admin/Adult/Kid role — an Admin account does **not** automatically get coordinator controls, and a non-admin Adult can be made a coordinator.

An admin turns this on from **Settings → Users** (see [section 15](#15-admin--managing-users)): a **Coordinator** switch in the Users table, next to the Role dropdown. It saves immediately, like everything else in that table.

- **Kid accounts can never be coordinators** — the switch is disabled on a Kid account's row, and demoting an existing coordinator to Kid automatically clears the grant.
- An admin can grant the coordinator switch to their own account (it isn't disabled on your own row the way the Role dropdown is).

---

## 32. Wall display (kiosk)

A wall display turns a spare tablet — the one on the kitchen counter, say — into an always-on glance screen for the household: who's OK, what the weather and street alerts look like, the last few chat messages, and when the next net is. It runs as its own page, with no login and no access to the rest of the app.

### Setting up a display (admin)

1. Open **Settings → Station tab** (admin only) and scroll to **Wall displays**.
2. Type a name for the tablet (e.g. "Kitchen") and click **Add display**.
3. The new device's token is shown **once**, in a copyable field. Copy it now — Hearthwave does not show it again. If it's lost before the tablet is set up, the only fix is to revoke that display and add a new one.
4. On the tablet itself, browse to `http://<host>/display` and paste the token into the connect screen. The token is then remembered on that device (stored in the browser's local storage), so the tablet reconnects on its own after a reboot or a power cut — no re-pairing needed.

The **Wall displays** table lists every paired device with when it was created and when it was last seen, plus a **Revoke** button. Revoking disconnects that display immediately; it will have to be re-paired with a fresh token to come back online.

### What it shows

- **Family presence tiles** — one per household member, with the same status chips as the [Family activity](#30-family-activity): **OK**, **On air**, **No word**, or **Missed check-in**.
- A **weather / street alert banner**, when one is active.
- The **last three chat messages**.
- The **next scheduled net** (or "Net running now" while one is in progress).
- A large **clock**.

The display dims to a dark theme automatically between 7 PM and 7 AM, and the whole layout drifts a few pixels every so often — a standard anti-burn-in measure for a screen that shows the same layout for hours at a stretch. None of this needs any setup; it just runs.

### Tap to wake

The display is normally passive — nothing on it responds to touch. Tapping anywhere wakes it into an interactive mode for 45 seconds, during which:

- **Tapping a family member's tile** brings up a large **"Mark {name} as OK?"** confirmation with **Yes** / **No**. Tapping **Yes** does the same three things the Family activity's I'm OK button does: speaks it on the air, posts it to chat, and updates that person's presence.
- A row of **household quick-message** buttons appears, if any are configured (see below). Tapping one sends that exact message.

If nothing is tapped again, the display reverts to its passive glance layout after the 45 seconds run out.

### Household quick messages (admin)

The buttons on the wall display come from a **Household Quick Messages** list, configured by an admin in the same **Settings → Station tab → Wall displays** section — one message per line. Leaving the list empty hides the quick-message row on every display. Every message a display sends is checked against this exact list on the server, so a display can never transmit anything outside what an admin has put there.

### What a display can't do

A wall display is a read-and-tap glance screen, not a client login. It has no access to Settings, cannot transmit outside its quick-message allowlist, and can't see user accounts or any other part of the app. A quick message shows up in chat under the display's own name (e.g. "Kitchen"). A Mark-OK is different: it proxies that household member's own check-in, so it posts under the member's name, not the display's.

---
