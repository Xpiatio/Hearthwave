# Radio-TTY User Manual

This manual covers day-to-day operation of Radio-TTY as a GMRS family hub — a shared radio operating station where every household member connects from their own device. For installation and server setup, see [README.md](README.md).

---

## Table of contents

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
21. [Server Config panel (admin)](#21-server-config-panel-admin)
22. [Plugin system](#22-plugin-system)

---

## 1. Signing in

Open your browser and navigate to the Radio-TTY host address — typically `http://192.168.x.x` or a hostname your administrator provides.

### First launch — Setup screen

If no accounts exist yet, the **Setup** screen appears instead of the login screen. This happens once, the very first time Radio-TTY is used.

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

If the server is unreachable, the status bar shows **OFFLINE** in amber. Refresh the page or contact your administrator.

---

## 2. The interface

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ [👤 Dad ▾] │ STATIONS  JOURNAL  CONTACTS  WATERFALL [NCS MODE] │ STATUS: READY ●│  ← Top bar
│            [GMRS] [LISTENING] [TX ENABLED] [READ ALOUD] [NOTIFY] │ [🗑]  [☀/🌙] │
├────────────────────────────────────────────────────────────────────────────────┤
│  [Pending stations bar — amber chips, hidden when empty]                       │
├────────────────────────────────────────────────────────────────────────────────┤
│                │                                                                │
│  Spectrogram   │           Chat display                                         │
│  (waterfall)   │                                                                │
│                │  [RX] WQZX999 — Dave > Hello this is Bravo                    │
│                │  [TX] Dad > Good morning                                       │
│                │                                                                │
├────────────────────────────────────────────────────────────────────────────────┤
│  Status: Radio connected · Volume OK · Channel clear                           │
├────────────────────────────────────────────────────────────────────────────────┤
│  [Standing by] [QSL] [Copy that] [QSY to channel {N}]  ⚙                      │  ← Quick messages
├────────────────────────────────────────────────────────────────────────────────┤
│  [THIS IS]  Message [_________________________] [SEND ↵]                       │
└────────────────────────────────────────────────────────────────────────────────┘
```

**Account chip** (e.g. *👤 Dad*) — click to open a menu with:
- **Edit Profile** — change operator name, call sign, location, avatar emoji, TTS voice, speech speed
- **Change Password**
- **Settings** — toggle your personal settings panel
- **Admin** — toggle the Admin panel (admin accounts only)
- **Sign Out**

**Panel toggles** (highlighted when the panel is open):
- **STATIONS** — session attendance panel
- **JOURNAL** — journals panel
- **CONTACTS** — shared contacts list
- **WATERFALL** — spectrogram waterfall (preference saved per browser)
- **NCS MODE** — Net Control Station panel (admin accounts only; red when active)

**Station status** (center) — current state (READY, Transmitting, etc.) with an FCC online indicator dot.

**Radio controls** (right side of top bar):
- **GMRS / FRS** — current service mode; click to toggle
- **LISTENING / LISTEN** — STT active; click to pause automatic transcription
- **TX ENABLED / LISTEN ONLY** — transmit status; click to toggle listen-only for your account
- **READ ALOUD** — when active (blue), incoming RX transcripts are spoken aloud through your browser audio
- **NOTIFY** — when active (blue), browser notifications fire for incoming RX and SKYWARN alerts while the tab is in the background (browser permission required on first enable)

**UI utilities:**
- **Trash icon** — clear the chat log
- **Sun/moon icon** — toggle dark/light mode

---

## 2a. Mobile interface

On smartphones and tablets, Radio-TTY automatically switches to a touch-optimized layout after sign-in. No setting is required — the app detects touch devices and applies the mobile interface for the duration of that session.

```
┌─────────────────────────┐
│ ≡  W1TEST  ●    [PTT]   │  ← Top bar
├─────────────────────────┤
│ [Pending stations bar]  │  (hidden when empty)
├─────────────────────────┤
│                         │
│   Chat / Stations /     │
│   Journal content       │
│                         │
├─────────────────────────┤
│  Chat   Stations Journal │  ← Bottom navigation
└─────────────────────────┘
```

**Top bar:**
- **≡ Menu** — opens a side drawer with toggle switches (Dark mode, Listen only, STT listening, Read aloud, Notifications) and your account menu (Edit Profile, Change Password, Admin, Sign Out)
- **Station callsign** — the current station callsign with a color dot: green = connected, red = offline
- **PTT** — push-and-hold to transmit via your device microphone (Voice PTT); hidden in listen-only mode

**Bottom navigation tabs:**
| Tab | Contents |
|-----|----------|
| **Chat** | Message log, quick messages bar, and message input (send by text) |
| **Stations** | Session attendance list |
| **Journal** | Session journal generation and log |

**Differences from desktop:**
- The spectrogram waterfall is not shown on mobile (CPU/battery considerations)
- Panel drag-and-drop reordering is not available on mobile
- NCS Mode is not accessible from mobile
- All other features — TX, RX, contacts, journals, dark mode, notifications, Voice PTT — work identically

> **Tip:** If you sign in on a touch device and want the full desktop layout, open the browser's desktop mode (site settings or "Request desktop site") and reload the page.

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

1. Type your message in the message box at the bottom of the screen.
2. Press **Enter** or tap **SEND**.

The system will:
- Expand TTY abbreviations and Q-signals (see [Text shortcuts reference](#18-text-shortcuts-reference))
- Apply your profanity filter if enabled
- Wrap the message with the station callsign per FCC rules
- Synthesize speech using the configured Piper voice
- Key the radio via PTT and transmit

The status bar shows **Transmitting** while the radio is keyed and returns to **Idle** when done.

**Chat echo:** Every outgoing transmission appears in the chat area as a `[TX]` entry (shown in blue). All connected users see the same entry in real time. When a message is directed to a specific station, the recipient is shown between the sender and the message text:

| Scenario | Chat display |
|---|---|
| Broadcast | `[TX] [Dad]: Hello everyone` |
| Directed | `[TX] [Dad] → WSLZ233 — Dave: Hello` |

**Targeting a specific station:** Use the **To** dropdown above the message box to address a transmission. The list is sorted alphabetically by callsign; **ALL — Broadcast** is pinned at the top. Your own callsign appears in the list so you can address yourself (useful for testing or self-checks). Selecting a contact pre-fills the callsign and name; the outgoing message is addressed to that station and the recipient label appears in chat for all users.

**Placeholder tokens:** Include `{1}`, `{2}`, etc. as fill-in-the-blank slots. When you send, the system prompts you to fill in each before transmitting. Useful for templates: `Heading to {1} — ETA {2} minutes`.

**Voice preview:** Open the Config panel and use the **Voice Test** button to hear your current TTS voice without keying the radio. To change your personal voice, see [Your account](#14-your-account).

**Listen-only mode:** When active, all TX controls are hidden. Your setting does not affect other users — each person controls their own TX access independently.

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

GMRS regulations require your station to identify with the callsign at least every 15 minutes. Radio-TTY handles this automatically — every outgoing message is wrapped with the station callsign and the timer resets.

**Manual "THIS IS" ID:** Tap the **THIS IS** button to send a standalone identification in NATO phonetics (e.g., *"This is Whiskey Quebec Zulu X-Ray 9 9 9"*). Use this at the start of a session or when required by net control. A `[TX] Station ID` entry appears in chat for all connected users.

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

A GMRS licence covers an entire household, so multiple people share the same callsign. Radio-TTY supports this by allowing **multiple contact records with the same callsign**, each identified by a unique name.

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
2. Click **GENERATE FROM SESSION**. The system sends the transcript and detected callsigns to Gemini.
3. Review and edit the title and summary.
4. Click **SAVE JOURNAL** to persist it on the server.

**Viewing saved journals:** Saved journals appear in the list on the left. Click one to read it.

**Deleting a journal:** Click the **delete icon** (🗑) next to a journal. Click once to arm the delete, click again to confirm.

**Publishing to the family journal:** Click the **publish icon** (⬆) next to a saved journal to post it to the public family journal page. Click once to arm, click again to confirm. A snackbar confirms publication and shows the URL (`/journal`). See [Family journal](#12-family-journal-public-page).

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
The **callsign**, **name**, **location**, **default TTS voice**, **Gemini API key**, and **journals directory** are set in the **Admin** panel. These are shared by all users. Changes are persisted to `config.json`.

The **Default TTS Voice** dropdown sets which Piper voice the station uses when a user has not chosen a personal voice. Click the **mic icon** next to the dropdown to preview the selected voice without keying the radio.

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

Admin accounts have access to the **Admin** item in the account menu (click your name chip → **Admin**), or via the **NCS MODE** button which opens the NCS panel alongside the Admin panel. The Admin panel has three sections: station settings, user accounts, and NCS / SKYWARN.

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

Radio-TTY can fire browser (OS-level) notifications when the tab is in the background — useful when the station is monitoring in another window or on a separate screen.

**Enabling notifications:**
1. Click the **NOTIFY** button in the top bar. It turns blue when active.
2. On first enable, the browser asks for notification permission. Grant it.
3. If you deny permission in the browser, the button shows an error and remains off. You will need to re-enable the permission in your browser settings.

**What triggers a notification:**
- A final RX transcript arrives (shows callsign + first 120 characters of the text)
- A SKYWARN alert fires from the NCS plugin (shows event name)

Notifications only appear when the Radio-TTY tab is **not** in focus. If you are actively looking at the tab, no notification is shown.

**Disabling notifications:** Click **NOTIFY** again. The button returns to the unselected state and notifications stop.

This preference is saved to your account and restored across sessions and devices.

---

## 18. Text shortcuts reference

Radio-TTY automatically expands common TTY, Q-signal, and CW abbreviations before transmitting.

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

Voice PTT lets you speak directly into your browser microphone and transmit through the radio, without typing.

A **PTT** (push-to-talk) button appears in the top bar area when TX is enabled for your account. Listen-only mode hides the PTT button along with other TX controls.

### Using Voice PTT

1. Press and hold the **PTT** button.
2. Speak into your browser microphone.
3. Release to transmit. The server keys PTT, plays your audio through the radio's output device, and Whisper transcribes it.
4. The transcript appears in chat as a **[TX]** entry (labeled with your name) visible to all connected users.

> **Self-echo prevention:** The TTS voice playing through the radio output does not trigger the station's own STT listener. The system waits for the browser to signal that audio playback is complete before resuming transcription, preventing the station from transcribing its own transmissions.

### Limits and behavior

| Parameter | Value |
|-----------|-------|
| Maximum recording length | 120 seconds |
| Minimum recording length | ~300 ms (shorter recordings are rejected) |
| Audio format sent to server | Raw PCM, 16 kHz, chunked base64 |

If the radio's output device runs at a sample rate other than 16 kHz, the server resamples automatically before playback.

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

## 21. Server Config panel (admin)

The **Server Config** panel provides technical server-side settings, separate from the Admin Settings / Station Identity panel. It is accessible to admin accounts only via a button in the top bar.

### Available settings

| Setting | Description |
|---------|-------------|
| VAD threshold | Sensitivity of voice activity detection. Lower = more sensitive; higher = requires stronger signal. Changing this restarts the STT worker. |
| Whisper model | Which Whisper model the server uses for transcription. Changing this restarts the STT worker. |
| PTT mode | How PTT is keyed: `manual`, `serial`, or `vox` (voice-operated transmit — keys automatically based on audio level). |
| PTT port / line | Serial port and control line used when PTT mode is `serial`. |
| Monitor passthrough | When enabled, audio captured from the radio input is simultaneously played back through the output device. Useful when the radio is not directly audible at the operator position. Does not require a server restart. |
| Attendance tracking | Enable or disable automatic callsign recording in the Stations panel. When disabled, the panel still exists but callsigns are not recorded automatically. |

> Changes to VAD threshold or Whisper model trigger a live STT worker restart and will briefly interrupt transcription.

---

## Tips

- **GMRS family licences:** One callsign covers your whole household. Add each person as a separate contact with the same callsign — only the name needs to differ. In NCS mode, each family member checks in as their own entry in the roster.
- **Multiple users:** Each family member signs into their own account. All clients see the same chat in real time — both received audio (RX) and outgoing transmissions (TX) — but each person's profanity filter, listen-only mode, and display preferences are independent.
- **Across devices:** Your settings follow you. Sign in on your phone and get the same preferences as your tablet.
- **Dark environments:** Click the sun/moon icon in the top bar, or your browser's dark mode preference is respected automatically on the public `/journal` page.
- **Slow or noisy transcription:** Adjust the VAD threshold in the **Server Config** panel (admin). Lower values (e.g. 0.3) are more sensitive; higher (e.g. 0.7) require a stronger signal. The setting can also be changed directly in `config.json` (`vad_threshold`).
- **FCC lookups not working:** The online indicator (dot in the top bar) shows internet connectivity. If it is gray, FCC verification is unavailable until connectivity is restored.
- **Session locked out?** Wait 15 minutes or ask an admin to use **Admin → Users → Reset lockout**.
- **On a phone or tablet:** The app automatically shows the mobile interface — bottom tabs for Chat, Stations, and Journal. Tap the ≡ menu for settings and your account.
- **NCS traffic levels:** Use **IN-n-Out** for stations who only have a moment; use **Short Term** for those who can stay a few minutes but need to leave soon. Both are tracked in the roster and included in the end-of-net journal.

---

## 22. Plugin system

Radio-TTY is built around a plugin architecture. New capabilities attach to the radio pipeline at defined hook points without requiring changes to the core server. The **NCS / SKYWARN** feature described in [section 16](#16-ncs--net-control-station-mode) is itself a plugin — it demonstrates what the system can do and serves as the template for future extensions.

### How plugins work

A plugin is a Python class (`BasePlugin`) that overrides one or more async methods. The server calls these methods at fixed points in the RX and TX pipelines:

| Hook | When it fires |
|------|--------------|
| `on_client_message_received` | Any WebSocket message arrives from a connected client |
| `on_audio_rx_start` | Squelch opens — a transmission is beginning |
| `on_audio_rx_chunk` | Each audio chunk segmented by voice activity detection |
| `on_rx_final` | Final transcript and detected callsigns are ready |
| `on_audio_tx_pre_queue` | Synthesized audio is about to be sent to the radio |

Plugins can read data at any hook, inject TX audio, send WebSocket messages to clients, or interact with the contacts and attendance stores — all without modifying the core server.

On the frontend, plugins can register a React panel via `registerPlugin` in `frontend/src/plugins/index.ts`. The NCS panel (`NCSPanel/`) is an example: it receives WebSocket messages broadcast by the backend plugin and renders the roster, SKYWARN alerts, and controls.

### Potential future plugins

These are examples of capabilities that could be added as self-contained plugins:

| Plugin | What it would do |
|--------|-----------------|
| **Meshtastic bridge** | Forward received GMRS transcripts to a LoRa mesh network (Meshtastic / Meshcore); relay inbound mesh text messages back as TTS transmissions over GMRS |
| **Repeater controller** | Manage a GMRS repeater installation — auto-ID on interval, transmit timeout timer, courtesy tone, autopatch logic |
| **EchoLink / AllStar gateway** | Bridge GMRS audio to internet-linked repeater networks via VoIP protocols |
| **Scheduled voice briefing** | Announce NWS hourly forecasts or custom station reminders at configured times, independent of NCS mode |
| **DTMF decoder / paging** | Detect DTMF touch-tones sent over the air and trigger alerts, macros, or gate automations |
| **Transmission logger** | Write every received transmission — timestamp, duration, callsigns, and transcript — to a structured log file or SQLite database for later analysis |
| **EAS tone detector** | Recognize Emergency Alert System two-tone attention signals and surface an immediate on-screen and audio alert to all connected users |
| **AI call summarizer** | Generate a one-sentence briefing for each received transmission and push it alongside the transcript so operators can scan a busy channel at a glance |

If you are a developer and want to build a plugin, see `backend/plugins/base.py` for the `BasePlugin` interface and `backend/plugins/ncs.py` for a complete working example.
