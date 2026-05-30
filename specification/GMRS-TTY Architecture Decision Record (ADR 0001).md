# **Architecture Decision Record: Accessible Consumer-Focused Monorepo Architecture**

**Status:** Approved / Updated (v5.0 \- Zero-Database Flat-File Architecture)  
**Date:** May 30, 2026  
**Author:** Benjamin Zomberg

## **1\. Context**

The GMRS-TTY prototype application bridges real-time software audio modem operations with a messaging terminal interface. To deploy this successfully within the non-technical consumer GMRS/FRS space, the application must be simple enough for senior citizens, highly reactive on touchscreen devices (like tablets or mobile nodes), and fully ADA compliant. This dictates shifting away from complex developer metrics or desktop-bound layouts toward a robust, accessible, network-agnostic design.  
Furthermore, running modern local text-to-speech (TTS) models requires considerable computational power. The backend requires a dynamic, hardware-agnostic strategy to leverage whatever compute silicon is available on the operator's computer. Finally, because multiple household operators need to interface with the central radio station machine from separate devices over the local home network simultaneously, the app must segregate unique client configurations from globally shared radio network databases without introducing the overhead, file-locking risks, or execution footprint of an active database engine (e.g., SQLite, MySQL).

## **2\. Decision**

We will construct the system using a decoupled client-server architecture inside a single Git repository (monorepo), governed by strict accessibility, flexible hardware-acceleration, and completely database-free, stateless user configurations:

1. **Abstraction and Simplification:** The React frontend will completely hide technical digital signal processing (DSP) properties. The server tier (Python) will translate low-level audio device state metrics into high-level conversational signals before pushing them through the WebSocket connection.  
2. **Touchscreen-First & WCAG Compliance:** The UI tier will implement strict WCAG 2.1 AA layout rules, featuring massive typography scaling (up to 32px), mandatory 48x48px touch targets, and inline Text-to-Speech (TTS) capabilities using native browser audio tools.  
3. **Multi-Backend Automated Fallback Chain:** The Python server's speech synthesis subsystem will feature a structured hardware execution lookup path. At startup, the server will query system capabilities sequentially: NVIDIA CUDA, AMD ROCm/DirectML, Intel OpenVINO, Dedicated Neural Processing Units (NPUs), and finally optimized, quantized CPU execution engines.  
4. **Zero-Database Client-Contained Architecture:** To eliminate database footprint and data file corruption vectors during abrupt power losses, individual identity profiles (Operator Name, Station Location, FCC Call Sign) are containerized wholly within individual browser clients using persistent localStorage. The shared global Contacts Directory will be orchestrated by the Python server tier using a single, in-memory, flat-file JSON serialization scheme (contacts.json) read and updated via async atomic overwrites.  
5. **Single Repository Orchestration:** Both tiers will be co-located to maintain strict structural alignment. Docker Compose environment parameters will deploy the exact same code blocks whether running locally on a single machine or split across a low-latency physical multi-node setup.

## **3\. Consequences**

### **Positive / Benefits**

* **Elimination of Database Execution Overhead:** Stripping out database wrappers prevents engine lock-ups, corrupt migration schemas, or hanging database processes, resulting in an exceptionally lightweight, low-overhead station deployment.  
* **Zero-Authentication Profile Architecture:** Bypassing login screens, user credentials, and security timeouts removes severe friction filters for senior operators while ensuring every household machine automatically maintains its own operational footprint natively.  
* **Simplified Backup and Recovery workflows:** Because the shared address database is a human-readable flat text file, users can back up or manually append contacts via basic text editors directly within the mapped Docker volume.

### **Negative / Trade-offs**

* **Flat-File Scale Boundaries:** Utilizing flat JSON text arrays reads all contact cards directly into system RAM. While highly efficient for typical household registries (sub-1000 names), this file serialization scheme does not scale optimally for massive, enterprise-grade directories.  
* **Client-Side Payload Inflation:** Appending unique identity objects to individual transmit actions slightly expands packet overhead compared to maintaining locked, server-bound single-user contexts.  
* **Driver Runtime Package Bulk:** Shipping backend containers optimized for multiple hardware backends (OpenVINO libraries, ONNX runtimes, and PyTorch frameworks) increases the foundational footprint of the compiled backend Docker images.