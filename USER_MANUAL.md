# Radio-TTY User Manual

This manual covers day-to-day operation of Radio-TTY. For installation and server setup, see [README.md](README.md).

---

## Table of contents

1. [Getting started](#1-getting-started)
2. [The interface](#2-the-interface)
3. [Receiving transmissions (RX)](#3-receiving-transmissions-rx)
4. [Sending a message (TX)](#4-sending-a-message-tx)
5. [Station identification (FCC ID)](#5-station-identification-fcc-id)
6. [Contacts](#6-contacts)
7. [Pending stations](#7-pending-stations)
8. [Spectrogram](#8-spectrogram)
9. [Session attendance](#9-session-attendance)
10. [Journals](#10-journals)
11. [Settings](#11-settings)
12. [Text shortcuts reference](#12-text-shortcuts-reference)

---

## 1. Getting started

Open your browser and navigate to the Radio-TTY host address — typically `http://192.168.x.x` or a hostname your administrator provides. No login is required.

**First-time setup:**

1. When prompted, enter your **operator name** (your first name or handle). This is stored locally in your browser and pre-fills the callsign field on every message you send.
2. Enter your **callsign** in the callsign field at the bottom of the screen. This appears on all outgoing messages and is used for FCC identification.
3. Your name and callsign persist across sessions in your browser. Other operators on different devices each have their own settings.

If the server is unreachable, the status bar shows **Disconnected** in red. Refresh the page or contact the station administrator.

---

## 2. The interface

```
┌────────────────────────────────────────────────────────┐
│  Radio-TTY        [service badge]  [online dot]  ☀ 📱 │  ← Top bar
├────────────────────────────────────────────────────────┤
│  [Pending stations bar — amber chips, hidden when empty]│
├────────────────────────────────────────────────────────┤
│                                                        │
│                   Chat display                         │
│                                                        │
│  WQZX999 > Hello this is Bravo                        │
│  KD9ABC  > Good morning                               │
│                                                        │
│                                         [▼ scroll FAB] │
├─────────────────────────┬──────────────────────────────┤
│    Spectrogram          │   Contacts / Attendance /    │
│                         │   Config / Journals tabs     │
├────────────────────────────────────────────────────────┤
│  Callsign [________] Name [________]                   │
│  [THIS IS]  Message [_____________________] [SEND]     │
└────────────────────────────────────────────────────────┘
```

**Top bar icons:**
- **Service badge** — shows GMRS or FRS; tap to switch service mode
- **Online dot** — green = internet available (FCC lookup enabled), gray = offline
- **Sun/moon icon** — toggle dark/light mode
- **Phone icon** — toggle touch mode (larger buttons for tablet/touchscreen use)

---

## 3. Receiving transmissions (RX)

Received audio is automatically transcribed by Whisper and displayed in the chat area. You do not need to do anything — transcription runs continuously in the background.

**Partial transcripts** appear in gray as the system processes audio in real time. The final transcript replaces them once the transmission ends.

**Callsign highlighting:** Recognized callsigns in received text appear as amber chips. Hover or tap a chip to see FCC verification status and contact details.

**The scroll button (▼)** appears in the bottom-right of the chat area when you have scrolled up to read history. Tap it to jump back to the latest message. The chat auto-scrolls when you are already at the bottom.

---

## 4. Sending a message (TX)

1. Confirm your **Callsign** and **Name** fields are filled in at the bottom of the screen.
2. Type your message in the message box.
3. Press **Enter** or tap **SEND**.

The system will:
- Expand any TTY abbreviations and Q-signals (see [Text shortcuts reference](#12-text-shortcuts-reference))
- Apply a profanity filter if enabled
- Wrap the message with your callsign per FCC rules
- Synthesize speech using the configured Piper voice
- Key the radio via PTT and transmit

The status bar shows **Transmitting** (red) while the radio is keyed and returns to **Idle** when done.

**Targeting a specific station:** If the contacts list is open and you select a contact, the target callsign and name are pre-filled for you. The outgoing message will be addressed to that station.

**Placeholder tokens:** You can include `{1}`, `{2}`, etc. in your message as fill-in-the-blank slots. When you send, the system prompts you to fill in each slot before transmitting. Useful for templates like: `Heading to {1} — ETA {2} minutes`.

**Voice preview:** You can hear how your message will sound before transmitting. Open the Config panel and use the **Voice Test** button.

**Listen-only mode:** When enabled (via Settings), all TX controls are disabled. The radio can still receive.

---

## 5. Station identification (FCC ID)

GMRS regulations require your station to identify with your callsign at least every 15 minutes.

Radio-TTY handles this automatically — every outgoing message is wrapped with your callsign. The 15-minute timer resets on each transmission.

**Manual "THIS IS" ID:** Tap the **THIS IS** button to send a standalone identification in NATO phonetics (e.g., *"This is Whiskey Quebec Zulu X-Ray 9 9 9"*). Use this when required by net control or at the start of a session. The 15-minute timer resets when you send a THIS IS ID.

---

## 6. Contacts

The **Contacts** tab shows your shared station contact list. All operators on all connected devices see the same list.

**Contact fields:**
| Field | Description |
|-------|-------------|
| Callsign | Primary callsign |
| Name | Operator name |
| Location | City/state or grid square |
| GMRS callsign | GMRS-specific callsign (if different) |
| HAM callsign | Amateur radio callsign (if different) |
| Verified | FCC verification status (✓ = verified) |

**Adding a contact:**
1. Click **Add** in the Contacts tab.
2. Fill in the callsign at minimum.
3. Click **FCC Look Up** to auto-fill name, location, and verification status from the FCC database (requires internet).
4. Click **Save**.

**Editing or deleting:** Click the row to open the edit dialog.

**Verify All:** Click **Verify All** to run an FCC database check on every contact in the list. Verification results are saved automatically.

**Sort by suffix:** Click **Sort by Suffix** to sort the list by the numeric/letter suffix of the callsign rather than alphabetically — useful for GMRS family callsigns that share a prefix.

**Import / Export:** Use the Import (JSON or CSV) and Export buttons to move contacts between systems or make a backup.

---

## 7. Pending stations

When the system detects an unrecognized callsign in a received transmission, it appears as an **amber chip** in the Pending Stations bar below the top bar.

- **Click a chip** to open the Add Contact dialog pre-filled with whatever info was extracted from the transcript (callsign, name, location).
- **Right-click a chip** (or tap the × on the chip) to dismiss it without adding.
- **Dismiss All** clears the entire pending bar.

If internet is available and a name was detected, the system automatically runs an FCC lookup in the background and may add the contact automatically. A notification appears in chat when this happens.

---

## 8. Spectrogram

The spectrogram panel shows a real-time waterfall display of incoming audio.

**Color indicators on the left edge:**
- **Amber stripe** — squelch is open (audio is above the noise floor)
- **White stripe** — VAD (voice activity detection) is active; speech is being segmented

**Configuring the spectrogram** (Config tab):
| Setting | Options | Description |
|---------|---------|-------------|
| Colormap | Viridis / Grayscale | Color scheme |
| Freq Range | Voice / Full | Voice = 300–3400 Hz, Full = 0–8 kHz |
| Time Window | 10s / 30s / 60s | How much history is visible |

---

## 9. Session attendance

The **Attendance** tab tracks which stations have been heard during the current session. Each row shows the callsign, name, and last-heard time.

**Clear attendance:** Resets the list for a new session or net.

Attendance data is in-memory only and is not persisted between server restarts.

---

## 10. Journals

The **Journals** tab lets you generate and save AI-written summaries of radio sessions. This feature requires a Google Gemini API key configured by your administrator.

**Generating a journal:**
1. At the end of a session, open the Journals tab.
2. Click **Generate Journal**. The system sends the session transcript and detected callsigns to Gemini.
3. Review the generated title and summary.
4. Click **Save** to write it to the journals directory on the server.

**Viewing past journals:** Saved journals appear in the list. Click one to read or delete it.

---

## 11. Settings

Open the **Config** tab to access runtime settings. Changes take effect immediately and are saved to the server.

### Audio
| Setting | Description |
|---------|-------------|
| Input device | Which microphone/audio interface the server listens on |
| System Audio Loopback | Capture audio from a PulseAudio sink (for radios connected via virtual cable) |
| Monitor | Enable/disable audio passthrough monitoring |

### Radio & content
| Setting | Description |
|---------|-------------|
| Service mode | GMRS or FRS — affects callsign UI display |
| Listen-only mode | Disables all TX; receive only |
| Profanity filter | Masks profanity in both sent and received text |
| Fuzzy callsign matching | Attempts to match near-misses like "KILO DELTA 9" to known callsigns |

### Voice
| Setting | Description |
|---------|-------------|
| Voice Test | Preview the current TTS voice using typed text without keying the radio |

### Spectrogram
See [Spectrogram](#8-spectrogram) above.

### Station identity (admin)
The **callsign**, **name**, **location**, **Gemini API key**, and **journals directory** are set here. These are server-wide settings — all operators see the same values. Changes are persisted to `config.json`.

---

## 12. Text shortcuts reference

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

You do not need to type phonetics manually — type the callsign normally and the system handles the rest.

---

## Tips

- **Multiple operators:** Each person opens Radio-TTY in their own browser and sets their own callsign and name. All clients see the same chat in real time.
- **Tablet/touchscreen:** Enable Touch Mode (phone icon in the top bar) for larger buttons.
- **Dark environments:** Enable Dark Mode (sun/moon icon in the top bar).
- **Slow/noisy transcription:** The VAD threshold can be adjusted in `config.json` (`vad_threshold`). Lower values (e.g. 0.3) are more sensitive; higher (e.g. 0.7) require stronger signal.
- **FCC lookups not working:** The online indicator (dot in the top bar) shows internet connectivity. If it is gray, FCC verification is unavailable until connectivity is restored.
