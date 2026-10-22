# Known Issues & Roadmap 🐞

This document tracks the current technical gaps and bugs in Sereen. Since this is an open-source project, these are excellent starting points for new contributors.

## 🔴 High Priority (Bugs & Gaps)

### 1. Model-Specific Input Mapping
- **Issue**: `INPUT_CODES` in `escvp.py` are best-effort defaults. Many Epson models use different codes for HDMI1, HDMI2, etc.
- **Goal**: Implement a way to query the projector for its available inputs and map them dynamically.

### 2. Casting Port Variety
- **Issue**: The current casting engine targets port `8889`. Some newer "Smart" projectors use different ports or proprietary handshakes.
- **Goal**: Add a "Port Scanner" for the casting service to find the correct video port.

### 3. Authentication Handling
- **Issue**: Basic password support is implemented, but some projectors require a specific challenge-response handshake for PJLink.
- **Goal**: Enhance `PJLinkSession` to handle complex authentication flows.

## 🟡 Medium Priority (Improvements)

### 4. GUI State Polling
- **Issue**: The GUI only updates state when a command is sent.
- **Goal**: Implement a background timer to poll the projector's power state and update the UI in real-time.

### 5. Advanced Casting Codecs
- **Issue**: Current casting uses `x264enc`, which can be CPU-heavy.
- **Goal**: Add support for hardware-accelerated encoding (VA-API/NVENC).

## 🟢 Low Priority (Features)

### 6. Saved Projector Profiles
- **Issue**: While the CLI supports saved projectors, the GUI currently does not remember them between sessions.
- **Goal**: Integrate `src/sereen/config.py` into the GTK4 sidebar.

### 7. Multi-Projector Sync
- **Issue**: Only one session is active at a time.
- **Goal**: Allow "Group Control" to turn on/off multiple projectors simultaneously.
