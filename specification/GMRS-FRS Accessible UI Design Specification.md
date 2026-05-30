# **GMRS/FRS Accessible (ADA) User Interface Specification**

**Date:** May 30, 2026  
**Document Version:** V5.0 (Updated for Stateless Local Storage and Flat-File Registry)  
**Target Audience:** Senior citizens, touchscreen operators, families, and individuals with visual or fine-motor challenges using consumer GMRS/FRS hardware over shared network interfaces.

## ---

**1\. Strategic Accessibility & Senior-Focused Mandates**

* **Visual Clarity & Contrast (WCAG 2.1 AA):** Replaces all dense matrix-green, terminal layouts, and small glowing fonts with a high-contrast flat layout. Viewport typography enforces a strict base sizing of 18px to 32px for clear legibility. Color is never utilized as the sole indicator of status change.  
* **Touch Target Constraints:** All interactive elements, inputs, buttons, and settings switches enforce a minimum target boundary of 48x48 pixels to allow reliable thumb or full-finger taps on tablet or wall mounts, preventing adjacent selection errors.  
* **Audio Accommodations (Hardware-Accelerated Text-to-Speech):** Integrates an audible "Read Aloud" toggle interface feeding incoming string buffers directly into a local deep-learning speech model. Incoming messages are audibly spoken by the station client immediately upon decoding over the airwaves.  
* **Radical Simplification of Telemetry:** Abstracts all technical jargon (such as baud rates, FSK frequencies, COM ports, and ALSA sub-devices) away from the primary operator dashboard, moving them behind an "Advanced Settings" barrier. Telemetry data is translated into plain, conversational English status trackers.

## ---

**2\. Hardware-Accelerated Speech Processing Engine**

To eliminate user interface stuttering, audio frame drops, or data packet corruption during local audio processing, the application utilizes a multi-tier local compute execution chain. The system programmatically discovers available computing hardware at boot time and registers the most efficient option: NVIDIA CUDA, AMD ROCm/DirectML, Intel OpenVINO, dedicated hardware Neural Processing Units (NPUs), or an optimized quantized CPU fallback.

## ---

**3\. Zero-Database Multi-User Network Configuration**

To maximize station reliability and eliminate configuration overhead, the system runs as a completely database-free, stateless router. Multi-user execution is handled through decentralized client storage paired with a synchronized server-side flat file:

### **A. Stateless Client Session Profiles (Browser LocalStorage)**

* **Persistent Client Storage:** Identity metrics including **Operator Name**, **Station Location**, and **FCC Call Sign** reside strictly within the individual device's persistent browser space (localStorage). Profiles survive system reboots and tab closures automatically without server-side authentication overhead.  
* **Dynamic Profile Switching:** A highly visible "Change Operator" touch trigger bypasses standard password/username login filters, clearing and re-initializing the local browser state fields instantly to accommodate shared household tablets.  
* **Payload Packaging:** The frontend client injects these locally stored profile fields as plain metadata headers directly into the active WebSocket JSON structure upon every transmission event.

### **B. Shared Server Flat-File Synchronization (In-Memory JSON Array)**

* **Flat-File Storage Layer:** The shared \*\*Contacts Registry\*\* is maintained entirely inside a single plain-text JSON text file (contacts.json) mapped to a persistent Docker volume, bypassing the weight of an active database engine.  
* **In-Memory Active Sync:** The Python server loads this text array into system memory on startup. When a contact is modified or added via any local interface, the backend updates its in-memory dictionary, commits an immediate atomic overwrite to the flat file, and broadcasts the fresh array across all active WebSocket nodes simultaneously.

## ---

**4\. Operational Dashboard Layout**

The layout is structured as a single-page touchscreen interface divided into three clean, horizontal target zones:  
\+---------------------------------------------------------------------------------------+  
| \[ CHANGE OPERATOR \]          STATION STATUS: READY                      \[ VOICE ON \]  |  
\+---------------------------------------------------------------------------------------+  
|                                                                                       |  
|   11:14 AM  \[ Grandma \]:  I am leaving Meijer now. Heading to the car.                |  
|                                                                                       |  
|   11:14 AM  \[ Station \]:  MESSAGE DECODED CLEARLY                                     |  
|                                                                                       |  
|   11:15 AM  \[ Incoming \]: Is anyone near Jenison Park? Over.                          |  
|                                                                                       |  
\+---------------------------------------------------------------------------------------+  
|  \[✅ Radio Cable Connected\]     \[🔊 Radio Volume is Perfect\]     \[📡 Channel: Clear\]  |  
|  \+---------------------------------------------------------------------------------+  |  
|  |  Type Your Message Below: LEAVING THE HOUSE NOW\_                                |  |  
|  \+---------------------------------------------------------------------------------+  |  
|  |                                                                                 |  |  
|  |                       \[ GIANT BUTTON: PRESS TO SEND MESSAGE \]                   |  |  
|  |                                                                                 |  |  
\+---------------------------------------------------------------------------------------+

## ---

**5\. Human-Readable Conversational Mapping**

* **Instead of "Audio RX \-12dB":** Display a simple label reading "🔊 Radio Volume is Perfect"  
* **Instead of "Error: Frame Drop / Corrupted Packet":** Display a temporary warning banner reading "⚠️ Signal static detected. Try sending again."  
* **Instead of "Serial PTT Attached to /dev/ttyUSB0":** Display a verification note reading "✅ Radio Cable Connected"  
* **Instead of "Transmitting Audio FSK Array":** Freeze screen state modifications and display a bold, flashing full-width overlay reading "⚠️ SENDING MESSAGE NOW... PLEASE WAIT" until the radio buffer clears.