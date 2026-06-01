# Radio-TTY User Manual

This manual covers day-to-day operation of Radio-TTY. For installation and server setup, see [README.md](README.md).

---

## Table of contents

1. [Signing in](#1-signing-in)
2. [The interface](#2-the-interface)
3. [Receiving transmissions (RX)](#3-receiving-transmissions-rx)
4. [Sending a message (TX)](#4-sending-a-message-tx)
5. [Station identification (FCC ID)](#5-station-identification-fcc-id)
6. [Contacts](#6-contacts)
7. [Pending stations](#7-pending-stations)
8. [Spectrogram](#8-spectrogram)
9. [Session attendance](#9-session-attendance)
10. [Journals](#10-journals)
11. [Family journal (public page)](#11-family-journal-public-page)
12. [Settings](#12-settings)
13. [Your account](#13-your-account)
14. [Admin — managing users](#14-admin--managing-users)
15. [Text shortcuts reference](#15-text-shortcuts-reference)

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

**New to the station?** Your administrator creates your account and gives you your initial password. You can change it any time via the account menu (see [Your account](#13-your-account)).

If the server is unreachable, the status bar shows **OFFLINE** in amber. Refresh the page or contact your administrator.

---

## 2. The interface

```
┌──────────────────────────────────────────────────────────────┐
│ [👤 Dad ▾]  STATIONS  JOURNAL  CONTACTS  CONFIG  ADMIN       │  ← Top bar
│                  STATION STATUS: READY  ●                    │
│         [GMRS]  [LISTENING]  [TX ENABLED]  [🗑]  [☀]        │
├──────────────────────────────────────────────────────────────┤
│  [Pending stations bar — amber chips, hidden when empty]     │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│                     Chat display                             │
│                                                              │
│  WQZX999 — Dave  >  Hello this is Bravo                     │
│  KD9ABC  — Mom   >  Good morning                            │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                    Spectrogram                               │
├──────────────────────────────────────────────────────────────┤
│  Status: Radio connected · Volume OK · Channel clear         │
├──────────────────────────────────────────────────────────────┤
│  [THIS IS]  Message [_________________________] [SEND ↵]     │
└──────────────────────────────────────────────────────────────┘
```

**Top bar — left side:**
- **Account chip** (e.g. *👤 Dad*) — your name; click to edit your profile, change your password, or sign out
- **STATIONS** — toggle the session attendance panel
- **JOURNAL** — toggle the journals panel
- **CONTACTS** — open the shared contacts list
- **CONFIG** — toggle personal settings panel
- **ADMIN** — station settings and user management (admin accounts only)

**Top bar — right side:**
- **GMRS / FRS badge** — current service mode; click to toggle
- **LISTENING / LISTEN** — STT active; click to pause automatic transcription
- **TX ENABLED / LISTEN ONLY** — transmit status; click to toggle listen-only for your account
- **Trash icon** — clear the chat log
- **Sun/moon icon** — toggle dark/light mode

---

## 3. Receiving transmissions (RX)

Received audio is automatically transcribed by Whisper and displayed in the chat area. Transcription runs continuously in the background.

**Partial transcripts** appear while the system processes audio in real time. The final transcript replaces them once the transmission ends.

**Callsign highlighting:** Callsigns in received text appear as amber chips. The system detects all common forms — compact (`WSLZ233`), NATO phonetic (*Whiskey Sierra Lima Zulu Two Three Three*), spaced (`W S L Z 2 3 3`), and hyphenated (`WSLZ-233`) — and collapses them into a single chip showing the compact canonical form.

- **Known contacts** (in your shared contacts list) show an amber chip. Hover or tap for the operator name, location, and any GMRS/HAM cross-references.
- **Verified contacts** show a green **✓** badge immediately after the chip, indicating the callsign has been confirmed against the FCC database.
- **Unknown callsigns** appear as a dimmer chip and are added to the [Pending stations](#7-pending-stations) bar above the chat.
- **Fuzzy correction:** If fuzzy callsign matching is enabled and Whisper mishears a single character (e.g. `WSLZ235` instead of `WSLZ233`), the chip is shown with the corrected canonical form if a known contact is only one character away.

**Profanity filter:** If your profanity filter is enabled (see [Settings](#12-settings)), profanity is masked in received text with asterisks. Other users with the filter off see the unmasked text. This is a per-account setting.

---

## 4. Sending a message (TX)

1. Type your message in the message box at the bottom of the screen.
2. Press **Enter** or tap **SEND**.

The system will:
- Expand TTY abbreviations and Q-signals (see [Text shortcuts reference](#15-text-shortcuts-reference))
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

**Voice preview:** Open the Config panel and use the **Voice Test** button to hear your current TTS voice without keying the radio. To change your personal voice, see [Your account](#13-your-account).

**Listen-only mode:** When active, all TX controls are hidden. Your setting does not affect other users — each person controls their own TX access independently.

---

## 5. Station identification (FCC ID)

GMRS regulations require your station to identify with the callsign at least every 15 minutes. Radio-TTY handles this automatically — every outgoing message is wrapped with the station callsign and the timer resets.

**Manual "THIS IS" ID:** Tap the **THIS IS** button to send a standalone identification in NATO phonetics (e.g., *"This is Whiskey Quebec Zulu X-Ray 9 9 9"*). Use this at the start of a session or when required by net control. A `[TX] Station ID` entry appears in chat for all connected users.

---

## 6. Contacts

The **Contacts** panel shows the shared station contact list. All users on all devices see the same list.

| Field | Description |
|-------|-------------|
| Callsign | Primary callsign |
| Name | Operator name |
| Location | City/state or grid square |
| GMRS callsign | GMRS-specific callsign (if different) |
| HAM callsign | Amateur radio callsign (if different) |
| Verified | FCC verification status (✓ = verified) |

**Adding a contact:**
1. Click **Add** in the Contacts panel.
2. Enter the callsign at minimum.
3. Click **FCC Look Up** to auto-fill name and location from the FCC database (requires internet).
4. Click **Save**.

**Editing / deleting:** Click a row to open the edit dialog.

**Verify All:** Runs an FCC database check on every contact in the list.

**Sort by suffix:** Sorts by the numeric suffix — useful for GMRS family callsigns that share a prefix.

---

## 7. Pending stations

When an unrecognized callsign is detected in a received transmission, it appears as an **amber chip** in the bar below the top bar.

- **Click a chip** to open Add Contact pre-filled with the extracted callsign, name, and location.
- **Tap × on a chip** to dismiss without adding.
- **Dismiss All** clears the entire bar.

If internet is available and a name was detected, the system runs an FCC lookup automatically and may add the contact on its own. A notification appears in chat when this happens.

---

## 8. Spectrogram

The spectrogram shows a real-time waterfall of incoming audio.

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

## 9. Session attendance

The **Stations** panel tracks which callsigns have been heard during the current session.

**Clear attendance:** Resets the list for a new session or net.

Attendance is in-memory only and resets when the server restarts.

---

## 10. Journals

The **Journals** panel lets you generate and save AI-written session summaries. Requires a Google Gemini API key configured by your administrator.

**Generating a journal:**
1. Open the Journals panel at the end of a session.
2. Click **GENERATE FROM SESSION**. The system sends the transcript and detected callsigns to Gemini.
3. Review and edit the title and summary.
4. Click **SAVE JOURNAL** to persist it on the server.

**Viewing saved journals:** Saved journals appear in the list on the left. Click one to read it.

**Deleting a journal:** Click the **delete icon** (🗑) next to a journal. Click once to arm the delete, click again to confirm.

**Publishing to the family journal:** Click the **publish icon** (⬆) next to a saved journal to post it to the public family journal page. Click once to arm, click again to confirm. A snackbar confirms publication and shows the URL (`/journal`). See [Family journal](#11-family-journal-public-page).

---

## 11. Family journal (public page)

The family journal at `/journal` is a public page — no login required. It shows the most recent published session logs and can be bookmarked and shared with anyone.

**URL:** `http://<your-host>/journal`

**What's shown:** Each published entry displays the session date, who published it, the AI-generated summary, and the list of stations on the air. Raw transcripts are not included.

**Capacity:** The page always shows the 10 most recently published journals. Publishing an 11th entry automatically removes the oldest.

**Accessibility:** The page is designed to meet WCAG 2.1 AA standards — it works with screen readers, keyboard navigation, and automatically adapts to your browser's dark mode setting. No JavaScript is required.

---

## 12. Settings

Open the **Config** panel (CONFIG button in the top bar) to manage your personal settings. All changes take effect immediately and are saved to your account.

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

Your personal TTS voice is chosen in **Account → Edit Profile** (see [Your account](#13-your-account)). If you have not selected one, the station-default voice configured by the admin is used.

### Spectrogram (per-user)
| Setting | Description |
|---------|-------------|
| Colormap | Viridis or Grayscale |
| Time window | How much history is visible |

> Frequency range is a station-wide setting controlled by an admin.

### Station identity (admin only)
The **callsign**, **name**, **location**, **default TTS voice**, **Gemini API key**, and **journals directory** are set in the **Admin** panel. These are shared by all users. Changes are persisted to `config.json`.

The **Default TTS Voice** dropdown sets which Piper voice the station uses when a user has not chosen a personal voice. Click the **mic icon** next to the dropdown to preview the selected voice without keying the radio.

---

## 13. Your account

Click your **name chip** in the top-left of the top bar to open the account menu.

### Edit profile
Change your **operator name** (shown in TX messages), **call sign**, **location**, **avatar emoji**, and **TTS voice**. These are personal to your account and affect how your transmissions are identified — other users' transmissions use their own profile values.

> **Station vs. personal callsign:** Each user can have their own call sign and location. Your personal call sign takes precedence over the station-wide callsign for your transmissions. If your profile has no call sign set, the station callsign (from Admin Settings) is used as a fallback.

**TTS Voice:** Choose your personal Piper voice from the dropdown. Click **Sample** to hear it before saving — no radio is keyed. Select *Station Default* to fall back to whichever voice the administrator has configured. Each family member can use a different voice.

### Change password
Enter a new password (minimum 8 characters). You must confirm it. Your current sessions remain active after a password change.

### Sign out
Ends your session on this device. Your preferences are saved and will be restored when you sign in again, even on a different device.

> **Tip:** Signing out does not affect other users or the radio. The station continues to receive and the other family members stay connected.

---

## 14. Admin — managing users

Admin accounts have access to the **ADMIN** button in the top bar. The Admin panel has two sections: station settings and user accounts.

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

---

## 15. Text shortcuts reference

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

## Tips

- **Multiple users:** Each family member signs into their own account. All clients see the same chat in real time — both received audio (RX) and outgoing transmissions (TX) — but each person's profanity filter, listen-only mode, and display preferences are independent.
- **Across devices:** Your settings follow you. Sign in on your phone and get the same preferences as your tablet.
- **Dark environments:** Click the sun/moon icon in the top bar, or your browser's dark mode preference is respected automatically on the public `/journal` page.
- **Slow or noisy transcription:** The VAD threshold can be adjusted in `config.json` (`vad_threshold`). Lower values (e.g. 0.3) are more sensitive; higher (e.g. 0.7) require a stronger signal.
- **FCC lookups not working:** The online indicator (dot in the top bar) shows internet connectivity. If it is gray, FCC verification is unavailable until connectivity is restored.
- **Session locked out?** Wait 15 minutes or ask an admin to use **Admin → Users → Reset lockout**.
