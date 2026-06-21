# Hearthwave User Manual

> **Version:** v2.8.0

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
22. [Plugin system](#22-plugin-system)
    - [22a. MeshCore mesh bridge](#22a-meshcore-mesh-bridge)
23. [FCC compliance and remote access](#23-fcc-compliance-and-remote-access)
24. [Transcription vocabulary biasing](#24-transcription-vocabulary-biasing)
25. [Deployment profiles and GPU acceleration (admin)](#25-deployment-profiles-and-gpu-acceleration-admin)

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
   - The call sign and location you enter here are saved to your personal profile **and** used to seed the station defaults in **Admin Settings**. Both can be adjusted independently afterward.
3. Click **Create Account**. Your admin account is created and you are signed in automatically.

After setup, go to **ADMIN → Users** to create accounts for other family members.

### Returning users — Login screen

The **login screen** appears automatically. Select your name from the profile list, enter your password, and click **Sign In**.

- Each family member has their own account with a unique password.
- Your preferences (dark mode, profanity filter, listen-only mode, etc.) are stored in your account and follow you across all devices — phone, tablet, laptop.
- If you enter the wrong password three times, your account is locked for 15 minutes. Contact your administrator to unlock it sooner.

**New to the station?** Your administrator creates your account and gives you your initial password. You can change it any time via the account menu (see [Your account](#14-your-account)).

The login screen shows the **Hearthwave logo** and an **About** link beneath the sign-in form. The About link displays the running version (e.g. *v2.8.0*) and opens the **About Hearthwave** dialog with project links and FCC information. Once signed in, you can reopen this dialog any time from the **logo in the top bar** or the **About Hearthwave** entry in the account menu.

If the server is unreachable, the status bar shows **OFFLINE** in amber. Refresh the page or contact your administrator.

---

## 2. The interface

The Hearthwave interface adapts to your screen size — desktop and mobile use
different layouts but share the same feature set.

### Desktop layout

The desktop shows all panels simultaneously:

```
┌──────────────────────────── TopBar ─────────────────────────────┐
│ [≡ panels]  Callsign ●  [PTT]  [ABORT TX]  [Spectrogram]  [👤] │
├───────────────┬──────────────────────────┬───────────────────────┤
│ Draggable     │  Chat Display            │  Side panels          │
│ panels        │  (scrollable RX/TX log)  │  NCS / Journals /     │
│               │                          │  Attendance           │
├───────────────┴──────────────────────────┴───────────────────────┤
│ Status · Config · Pending Stations · Quick Messages              │
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
- **Draggable panels** — NCS, Journals, Attendance, and any installed plugins.
  Drag the panel handle to reorder. Each panel has a coloured gradient header:
  NCS and Admin use a blue gradient; Config, Journals, and Attendance use a
  darker navy gradient.
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

On phones and narrow tablets Hearthwave shows a single-column view:

```
┌────────────────── TopBar (sticky) ──────────────────┐
│ [≡]  Callsign ●        [PTT]  [ABORT TX]            │
└──────────────────────────────────────────────────────┘
│                                                      │
│              Chat Display (scrollable)               │
│                                                      │
└──────────────────────────────────────────────────────┘
┌────────── Bottom Navigation ─────────────────────────┐
│ Chat  │  NCS  │  Journals  │  Status  │  Settings    │
└──────────────────────────────────────────────────────┘
```

- Tap **[≡]** (top-left) to open the settings drawer: dark mode, listen-only,
  STT, read-aloud, notifications.
- The **PTT** button and **ABORT TX** button are always visible in the top bar.
- Bottom navigation switches between Chat, NCS, Journals, Status, and Settings
  views.
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

**Voice preview:** Open the Config panel and use the **Voice Test** button to hear your current TTS voice without keying the radio. To change your personal voice, see [Your account](#14-your-account).

**Listen-only mode:** When active, all TX controls are hidden. Your setting does not affect other users — each person controls their own TX access independently.

**Message length limit (MeshCore):** When the MeshCore plugin is enabled (see [section 22a](#22a-meshcore-mesh-bridge)), a live character counter appears under the message box (e.g. `MeshCore · 18 / 135`) and typing is capped so the message — plus the sender-name prefix added on the mesh — fits a single mesh packet. The counter turns red at the limit. With the plugin off there is no limit and no counter.

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

> **Connecting the radio:** Hearthwave connects to the radio's **combo (speaker/mic) jack** — typically a Kenwood-style **K1** cable — either through the computer's built-in 3.5 mm jack or a USB sound card. A USB connection *to the radio itself* is not required. For a VOX-keyed radio, enable the **VOX primer tone** (see [Admin Settings](#21-admin-settings-dialog-admin)) so the radio opens before speech begins. Full wiring options are in the [README](README.md#connecting-the-radio).

### Radio & content (per-user)
| Setting | Description |
|---------|-------------|
| Profanity filter | Masks profanity in your sent and received text (other users unaffected) |
| Listen-only mode | Disables TX for your account only |
| Fuzzy callsign matching | Station-wide; when Whisper mishears a single character in a callsign (e.g. `WSLZ235` → `WSLZ233`), the chip in chat and the pending/attendance entry are corrected to the known canonical form |

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

### Panel layout (per-user)

The **Config**, **Stations**, and **Journal** panels on the left side of the screen can be reordered by dragging. Grab the drag handle on a panel header and move it up or down. The order is saved to your account and restored across devices.

### Station identity (admin only)
The **callsign**, **name**, **location**, **default TTS voice**, **Gemini API key**, and **journals directory** are set on the **Station tab** of the **Admin Settings** dialog. These are shared by all users. Changes are persisted to `config.json`.

The **Default TTS Voice** dropdown sets which Piper voice the station uses when a user has not chosen a personal voice. Click the **mic icon** next to the dropdown to preview the selected voice without keying the radio.

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

> **Station vs. personal callsign:** Each user can have their own call sign and location. Your personal call sign takes precedence over the station-wide callsign for your transmissions. If your profile has no call sign set, the station callsign (from Admin Settings) is used as a fallback.

**TTS Voice:** Choose your personal Piper voice from the dropdown. Click **Sample** to hear it before saving — no radio is keyed. Select *Station Default* to fall back to whichever voice the administrator has configured. Each family member can use a different voice.

**Speech speed:** Enable **Custom speed** and adjust the slider to set a personal TTS pace — lower values produce faster speech, higher values produce slower speech. Leave it on *Station Default* to use the speed configured by the admin.

### Change password
Enter a new password (minimum 8 characters). You must confirm it. Your current sessions remain active after a password change.

### Sign out
Ends your session on this device. Your preferences are saved and will be restored when you sign in again, even on a different device.

> **Tip:** Signing out does not affect other users or the radio. The station continues to receive and the other family members stay connected.

---

## 15. Admin — managing users

Admin accounts have access to the **Admin Settings** dialog via the account chip menu or the **ADMIN** button in the top bar. The dialog has two tabs: **Station** (station identity, user accounts, NCS / SKYWARN) and **System** (audio, STT, PTT, and advanced server settings — see [section 21](#21-admin-settings-dialog-admin)). The **NCS MODE** button in the top bar opens the NCS panel alongside the main interface without entering the settings dialog.

### User accounts

The **User Accounts** table lists all family member accounts.

**Creating a new account:**
1. Click **New User**.
2. Choose an avatar emoji, enter the display name, operator name, call sign, and location.
3. Set a password (minimum 8 characters, confirmed).
4. Check **Admin** if this person should be able to change station settings.
5. Click **Create**.

**Resetting a lockout:** If someone is locked out after too many wrong passwords, click the **unlock icon** (🔓) next to their name. They can sign in immediately.

**Deleting an account:** Click the **delete icon** (🗑) next to a user. You cannot delete your own account.

> **Security note:** For public internet access, put a TLS reverse proxy (nginx, Caddy) in front of the app. Passwords are hashed with PBKDF2-SHA256 (260,000 iterations, per-user salt) but session tokens travel in plaintext over HTTP without TLS.

### NCS / SKYWARN (admin only)

The **NCS / SKYWARN** section at the bottom of the Admin panel configures the Net Control Station plugin:

| Field | Description |
|-------|-------------|
| NWS County Zone | NWS zone code for SKYWARN alert polling (e.g. `MIZ025`). Empty = disabled. Find your zone at weather.gov. |

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

The **Admin Settings** dialog is accessible to admin accounts only. Open it from the account chip menu or via the **ADMIN** button in the top bar. It combines the former Admin panel and Server Config panel into a single tabbed dialog with two tabs:

- **Station tab** — station identity (callsign, name, location, default TTS voice, Gemini API key, journals directory), user accounts, and NCS / SKYWARN zone. Each section has its own **Save** button.
- **System tab** — technical server-side settings (audio devices, STT, PTT, VOX, and advanced options). Each section has its own **Save** button.

### System tab settings

| Setting | Description |
|---------|-------------|
| VAD threshold | Sensitivity of voice activity detection. Lower = more sensitive; higher = requires stronger signal. Changing this restarts the STT worker. |
| Whisper model | Which Whisper model the server uses for live (streaming) transcription. Changing this restarts the STT worker. |
| Final-pass model | Optional larger model that re-transcribes each completed transmission in full once the other station unkeys, replacing the live partial text with a more accurate final. The final pass never truncates a long transmission or drops a callsign the live pass already heard — if it returns a short or empty result, the complete live text is kept. Choose **Off** for single-pass, or a larger model such as `distil-large-v3` (recommended). The model must be staged first (see below) and adds ~1.5 GB RAM only while active. Changing this restarts the STT worker. |
| Final-pass device | Where the whole-utterance final pass runs: `auto` (GPU if a ROCm GPU is present, else CPU), `gpu`, or `cpu`. Requires the ROCm deployment profile to use GPU. See [section 25](#25-deployment-profiles-and-gpu-acceleration-admin). |
| Adaptive squelch | Tracks the channel noise floor and opens at 3× it, so weak carriers pre-trigger audio capture instead of clipping the first word. Leave off on consistently strong signals; enable on noisy or distant channels. Restarts the STT worker. |
| TX conditioning | Band-limits, compresses, and levels synthesized speech before it drives the radio's microphone input — clearer over narrowband FM. Browser read-aloud is unaffected. Takes effect immediately. |
| STT debug capture | Saves raw / segmented / processed audio plus transcripts for each utterance, for offline word-error-rate evaluation. For tuning only — leave off in normal operation. Restarts the STT worker. |
| Saved Phrases | A list of phrases Whisper is pre-loaded with as vocabulary hints to improve recognition accuracy. Common radio phrases ("break break", "QSL", "copy that") are included by default. Add any group-specific phrases — net names, operator handles, local shorthand — to help Whisper recognise them consistently. Changes take effect immediately without an STT restart. |
| PTT mode | How PTT is keyed: `manual`, `serial`, or `vox` (voice-operated transmit — keys automatically based on audio level). |
| PTT port / line | Serial port and control line used when PTT mode is `serial`. |
| VOX primer tone | When enabled, a short tone is prepended to each transmission so a VOX-keyed radio is fully keyed before the message starts. Silence alone does not reliably trip many VOX radios; the tone guarantees the radio is open when the speech begins. Off by default. Also configurable: tone duration in milliseconds. Enable this only if your radio uses VOX keying. |
| Monitor passthrough | When enabled, audio captured from the radio input is simultaneously played back through the output device. Useful when the radio is not directly audible at the operator position. Does not require a server restart. |
| Attendance tracking | Enable or disable automatic callsign recording in the Stations panel. When disabled, the panel still exists but callsigns are not recorded automatically. |
| MeshCore — forward to mesh | Master on/off for the MeshCore bridge. When on, every transmission is mirrored onto the MeshCore mesh; received radio traffic is never forwarded. Off by default. See [section 22a](#22a-meshcore-mesh-bridge). |
| MeshCore — device | Serial device of the MeshCore Companion radio (e.g. `/dev/ttyUSB0`). In Docker the port must also be passed into the container (see section 22a). |
| MeshCore — baud rate | Serial speed of the Companion link (default `115200`). |
| MeshCore — max packet length | Characters per mesh packet, **including** the sender-name prefix (default `140`). This drives the message-box character limit. |
| MeshCore — name separator | Joins the sender name and the message on the mesh (default `": "` → `Ben: hello`). |
| MeshCore — channel index | Which MeshCore channel to transmit on (default `0`). |

> Changing a MeshCore setting reconnects (or disconnects) the serial link immediately — no server restart needed. Changing the port or baud rebuilds the link in place.

> Changes to VAD threshold, Whisper model, Final-pass model, Adaptive squelch, or STT debug capture trigger a live STT worker restart and will briefly interrupt transcription. TX conditioning and Saved Phrases changes take effect immediately.

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

Then set **Final-pass model** to `distil-large-v3` in this panel (or `whisper_model_final` in `config.json`). On a CPU-only host a long transmission may take roughly its own duration to produce the improved final; live partials are unaffected.

---

## Tips

- **GMRS family licences:** One callsign covers your whole household. Add each person as a separate contact with the same callsign — only the name needs to differ. In NCS mode, each family member checks in as their own entry in the roster.
- **Multiple users:** Each family member signs into their own account. All clients see the same chat in real time — both received audio (RX) and outgoing transmissions (TX) — but each person's profanity filter, listen-only mode, and display preferences are independent.
- **Across devices:** Your settings follow you. Sign in on your phone and get the same preferences as your tablet.
- **Dark environments:** Toggle dark/light mode from the account menu (desktop) or the hamburger settings drawer (mobile). The public `/journal` page automatically adapts to your browser's dark mode preference.
- **Slow or noisy transcription:** Adjust the VAD threshold in the **Server Config** panel (admin). Lower values (e.g. 0.3) are more sensitive; higher (e.g. 0.7) require a stronger signal. The setting can also be changed directly in `config.json` (`vad_threshold`).
- **FCC lookups not working:** The online indicator (dot in the top bar) shows internet connectivity. If it is gray, FCC verification is unavailable until connectivity is restored.
- **Session locked out?** Wait 15 minutes or ask an admin to use **Admin → Users → Reset lockout**.
- **On a phone or tablet:** The app automatically shows the mobile interface — bottom tabs for Chat, NCS, Journals, Status, and Settings. Tap the ≡ menu for dark mode and your account.
- **NCS traffic levels:** Use **IN-n-Out** for stations who only have a moment; use **Short Term** for those who can stay a few minutes but need to leave soon. Both are tracked in the roster and included in the end-of-net journal.
- **Neighborhood watch groups:** Create one account per volunteer. Assign **listen-only** mode to members who should monitor but not transmit, and reserve TX-capable accounts for designated net control operators. The NCS roster and SKYWARN alerts work the same way they do for family nets — the watch's patrol log is automatically saved as a session journal at end of net.

---

## 22. Plugin system

Hearthwave is built around a plugin architecture. New capabilities attach to the radio pipeline at defined hook points without requiring changes to the core server. Two features ship as plugins: the **NCS / SKYWARN** feature described in [section 16](#16-ncs--net-control-station-mode), and the **MeshCore mesh bridge** described in [section 22a](#22a-meshcore-mesh-bridge). They demonstrate what the system can do and serve as the template for future extensions.

### How plugins work

A plugin is a Python class (`BasePlugin`) that overrides one or more async methods. The server calls these methods at fixed points in the RX and TX pipelines:

| Hook | When it fires |
|------|--------------|
| `on_client_message_received` | Any WebSocket message arrives from a connected client |
| `on_audio_rx_start` | Squelch opens — a transmission is beginning |
| `on_audio_rx_chunk` | Each audio chunk segmented by voice activity detection |
| `on_rx_final` | Final transcript and detected callsigns are ready |
| `on_audio_tx_pre_queue` | Synthesized audio is about to be sent to the radio |
| `on_config_changed` | Server config is (re)loaded — at startup and after every admin save |

Plugins can read data at any hook, inject TX audio, send WebSocket messages to clients, or interact with the contacts and attendance stores — all without modifying the core server. `on_config_changed` lets a plugin react to setting changes live (MeshCore connects or disconnects its serial link here when its settings are saved).

On the frontend, plugins can register a React panel via `registerPlugin` in `frontend/src/plugins/index.ts`. The NCS panel (`NCSPanel/`) is an example: it receives WebSocket messages broadcast by the backend plugin and renders the roster, SKYWARN alerts, and controls. A plugin can also cap the core message box without the input depending on it, via the **TX-composition endpoint** (`registerTxComposition`) — MeshCore uses this for its packet-length budget and live character counter.

### Potential future plugins

These are examples of capabilities that could be added as self-contained plugins:

| Plugin | What it would do |
|--------|-----------------|
| **Repeater controller** | Manage a GMRS repeater installation — auto-ID on interval, transmit timeout timer, courtesy tone |
| **Scheduled voice briefing** | Announce NWS hourly forecasts or custom station reminders at configured times, independent of NCS mode |
| **DTMF decoder / paging** | Detect DTMF touch-tones sent over the air and trigger alerts, macros, or gate automations |
| **Transmission logger** | Write every received transmission — timestamp, duration, callsigns, and transcript — to a structured log file or SQLite database for later analysis |
| **EAS tone detector** | Recognize Emergency Alert System two-tone attention signals and surface an immediate on-screen and audio alert to all connected users |
| **AI call summarizer** | Generate a one-sentence briefing for each received transmission and push it alongside the transcript so operators can scan a busy channel at a glance |

If you are a developer and want to build a plugin, see `backend/plugins/base.py` for the `BasePlugin` interface and `backend/plugins/ncs.py` for a complete working example.

---

## 22a. MeshCore mesh bridge

The MeshCore plugin forwards every message you transmit onto a [MeshCore](https://meshcore.co.uk/) LoRa mesh network, so your group stays in contact even where there is no GMRS coverage or internet. It is **off by default** and is enabled by an admin.

**What it does**

- Every message that goes over the air is also sent to the mesh, **prefixed with the sender's name** (e.g. `Ben: heading home`), so mesh-only members know who is talking.
- It is **outbound only** — messages *received* on the radio are never forwarded to the mesh. Only what your station transmits is bridged.
- Because it taps the transmit pipeline after all checks, a message blocked by NCS **BREAK BREAK** is never forwarded either.
- Forwarding is best-effort and never delays or blocks the radio transmission itself; if the mesh link is busy or down, the over still goes out on the radio normally.

**What you see as an operator**

When the plugin is on, the message box shows a live character counter (e.g. `MeshCore · 18 / 135`) and limits what you type so the message plus the name prefix fits one mesh packet. The limit is the configured **max packet length** minus your prefix length, so a longer display name leaves a little less room. The counter turns red at the limit.

**Hardware and setup (admin)**

- Connect a MeshCore **Companion** radio to the server by USB. Set the serial device, baud, max packet length, name separator, and channel on the **System** tab of Admin Settings (see [section 13](#13-settings)). Changes reconnect the link immediately — no restart.
- In a Docker install, the serial device must also be passed into the container: uncomment the MeshCore `devices:` line in `docker-compose.yml` and set it to your host's port. The optional `meshcore` Python package must be installed for the link to come up; without it the plugin stays disabled and logs a hint.
- The default max packet length (140) is a starting point — confirm the limit for the MeshCore firmware you are running.

A Meshtastic bridge is planned and will share the same forwarder foundation.

---

## 23. FCC compliance and remote access

Hearthwave allows family members to send text-to-speech messages to the base station over the internet. This section explains how that is designed to comply with FCC Part 95 GMRS regulations and what it means for your licence.

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

Control where the final pass runs with the `stt_final_device` key in `data/config.json` (System tab of Admin Settings is the recommended way to change it):

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

- **No rebuild needed:** set `stt_final_device` to `cpu` in Admin Settings (System tab) and restart the STT worker.
- **Full rollback:** set `COMPUTE_BACKEND=cpu` and restart with `docker-compose.yml` instead of `docker-compose.rocm.yml`.
