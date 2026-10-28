# Page Switching & BLE Name Modification — Design

## Intent

Add a page/tab switching widget at the top of the main window, allowing the user to switch between the existing "BLE Tester" page and a new "BLE Name" page. The BLE Name page provides a dedicated UI for sending command `0x23` (BLE Set Name) to rename the connected device.

## Goals

- User can switch between pages via a tab bar at the top of the window.
- The existing scan + command panel layout is preserved as one page ("BLE Tester").
- A new page ("BLE Name") lets the user type a device name and send the rename command.
- The BLE Name page shows clear warnings about auto-reboot behavior.
- Minimal changes to existing code — no restructuring of ScanPanel or CommandPanel.

## Non-Goals

- No changes to the BLE protocol layer or CH9329 frame handling.
- No persistence of name history or device profiles.
- No automatic reconnection after reboot — the existing disconnect handler is sufficient.

## Anti-Goals

- Do not replace the existing vertical splitter layout with a tab-based layout for scan/command panels — those stay together as one page.
- Do not add a full "settings" page — this is narrowly for BLE name modification.

## Constraints

- PyQt6 only (no third-party UI frameworks).
- Must reuse existing `BLEClient.send()` and signal infrastructure.
- Must follow the existing dark theme styling.

## Design

### Page Switching Mechanism

Use a `QTabWidget` as the central widget of `MainWindow`, replacing the current `QSplitter`-based layout. Each tab contains one "page":

| Tab Index | Tab Title | Content |
|-----------|-----------|---------|
| 0 | "BLE Tester" | The existing `QSplitter` with `ScanPanel` (top) + `CommandPanel` (bottom) |
| 1 | "BLE Name" | New `BLENamePanel` widget |

The `QTabWidget` is placed where the `QSplitter` currently lives — inside the central widget's `QVBoxLayout`, above the status bar.

### BLENamePanel — New Widget

**File:** `src/ui/ble_name_panel.py`

**Layout:**
```
BLENamePanel (QWidget)
└── QVBoxLayout (margins=16, spacing=12)
    ├── Title: QLabel "修改 BLE 设备名称"
    │
    ├── Warning banner (QFrame, styled)
    │   └── QLabel "⚠ 修改名称后设备将自动重启，BLE 连接会断开。
    │               名称写入 Flash，断电后仍然保留。"
    │
    ├── Connection status: QLabel (shows current connection state)
    │
    ├── Name input row (QHBoxLayout)
    │   ├── QLabel "设备名称:"
    │   ├── QLineEdit (self._name_input, maxLength=20, placeholder="输入新名称...")
    │   └── QPushButton "修改名称" (self._send_btn)
    │
    ├── Character count: QLabel "0/20" (updates on text change)
    │
    └── Log area: LogArea (self._log, shows TX/RX/status messages)
```

**Signals:**
- `send_requested(bytes)` — emitted when user clicks "修改名称", carries the complete CH9329 frame bytes for command 0x23.

**Behavior:**
1. User types a name (1–20 ASCII characters). The input is validated in real-time — non-ASCII characters are rejected, length capped at 20.
2. Character count label updates on each keystroke.
3. "修改名称" button is enabled only when: (a) connected, and (b) name is 1–20 characters.
4. On click: builds `CH9329Frame(addr=0x00, cmd=0x23, payload=name.encode('ascii'))`, emits `send_requested(frame_bytes)`.
5. Log area shows the sent frame (TX) and any response (RX) or error.
6. Connection status label updates via `set_connection_state(bool)` method called from MainWindow.

### Changes to MainWindow

**File:** `src/ui/main_window.py`

1. **Replace `_setup_ui`:** Instead of creating a `QSplitter` directly, create a `QTabWidget` and add two tabs:
   - Tab 0: A `QWidget` containing the existing `QSplitter` (ScanPanel + CommandPanel).
   - Tab 1: The new `BLENamePanel`.

2. **Add signal connections in `_setup_signals`:**
   - Connect `BLENamePanel.send_requested` to the same `_on_send_requested` handler used by CommandPanel.
   - Connect `BLEClient.connected` / `disconnected` to `BLENamePanel.set_connection_state`.

3. **Route responses to BLENamePanel:** When a response arrives and the BLE Name tab is active, also route it to `BLENamePanel.append_rx`. Alternatively, always route to both panels (they each have their own log area).

4. **Keep `_parse_response` working as-is** — it only affects CommandPanel's log, which is fine.

### Protocol Details for Command 0x23

| Field | Value |
|---|---|
| **cmd** | `0x23` |
| **name** | `"BLE Set Name"` |
| **Payload** | 1–20 bytes of ASCII text (the new device name) |
| **Response** | Single status byte: `0x00` = success |
| **Auto-reboot** | YES — device reboots immediately after success, dropping BLE connection |

### File Changes Summary

| File | Change |
|------|--------|
| `src/ui/ble_name_panel.py` | **New file** — BLENamePanel widget |
| `src/ui/main_window.py` | Refactor `_setup_ui` to use `QTabWidget`; add signal connections for BLENamePanel |
| No other files | No changes to protocol, BLE client, or existing panels |

## What's Left to the Builder

- Exact styling of the warning banner (color, icon) — follow the existing dark theme.
- Whether to show the response in BLENamePanel's log area or only in CommandPanel's — recommend showing in both for independence.
- Whether to add a "reset to factory name" button (command 0x31 with payload 0x00) — out of scope for now, can be added later.
