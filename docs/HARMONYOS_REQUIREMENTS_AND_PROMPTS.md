# HarmonyOS NEXT Architecture & Deep Implementation Blueprints for UmerOS

> **Document Edition:** 2.0.0 (Comprehensive Research & Implementation Edition)  
> **Target OS:** UmerOS (Python-First Classical/Quantum Hybrid OS with Flutter Desktop Shell)  
> **Primary References:** Huawei HarmonyOS NEXT (HongMeng 5.0), OpenHarmony 5.x Distributed Subsystems, and Huawei DevEco Specifications  

---

## 1. Executive Summary & Foundational Paradigms

**HarmonyOS NEXT** represents a radical departure from monolithic, single-hardware operating systems (such as Linux, Windows, macOS, or Android):
1. **Zero Legacy / Pure Native Core**: Stripped of Android Open Source Project (AOSP) code and the monolithic Linux kernel, running on the **HongMeng Microkernel** with formal verification.
2. **Distributed Everything**: Operates on the paradigm that physical devices (laptops, desktops, phones, tablets, smart displays, quantum simulators) are mere peripheral peripherals of a single unified **"Super Device"**.
3. **Star Shield Zero-Trust Security**: Eliminates invasive app permissions using **Permissionless Pickers** and enforces mathematical **Data Security (S1–S4) vs. Device Security Level (SL1–SL5)** cross-node routing rules.
4. **Harmony Intelligence**: AI (Celia / Pangu) is not an app; it is an omnipresent OS service capable of reading screen semantic trees, understanding cross-window contexts, and executing chained application intents.
5. **Fluid Real-Time Latency**: The **Deterministic Latency Engine** dynamically re-allocates CPU/memory bandwidth to guarantee zero-jitter 120 FPS UI rendering, pre-empting background batch tasks.
6. **Live Window (实况窗) & UDMF**: Real-time status capsule pills in the status bar/dock and standard Unified Data Management Framework for frictionless cross-app and cross-device drag-and-drop.

---

## 2. Comprehensive Subsystem Comparison Matrix

| # | Architecture Dimension | HarmonyOS NEXT (HongMeng) | Current UmerOS Baseline | Gap & Engineering Target in UmerOS |
|---|---|---|---|---|
| **1** | **Microkernel IPC Engine** | **Synchronous Fastpath IPC**: Direct register passing, thread-handoff scheduling, formally verified memory isolation. | Python async queue & HMAC IPC bus (`kernel/ipc_bus.py`). | **Lacks direct thread-handoff fastpath, zero-copy memory buffers, and formal capability checking.** |
| **2** | **Inter-Device Soft Bus** | **Distributed Soft Bus (DSoftBus)**: Dynamic peer mesh discovery across BLE, Wi-Fi, Ethernet; unified streaming/byte channel. | Local host networking (`network/network_stack.py`, `tcp_server.py`). | **No ad-hoc peer mesh discovery, zero-config device pairing, or unified cross-device softbus.** |
| **3** | **Hardware Virtualization** | **Distributed Hardware Pool**: Virtual Camera, Virtual Display, Virtual Audio, cross-device mouse/keyboard roaming. | Local simulated device drivers (`drivers/`). | **No peripheral pooling or interactive "Super Device" radar control center in Flutter.** |
| **4** | **Task & UI Mobility** | **Cross-Device Ability Continuation**: Migrate live running app state (cursor, scroll, data) between nodes with zero data loss. | Local Flutter shell apps (`ui/flutter_ui/lib/src/apps/`). | **No Ability state serialization lifecycle hooks or cross-node task migration orchestrator.** |
| **5** | **Distributed Data Engine** | **HMDFS & Distributed Data Object (DDO)**: In-memory CRDT objects + virtual `/dfs/<node_id>` peer filesystem trees. | Local QFS, RAM-based simulated filesystems, local SQLite. | **No peer-to-peer VFS mounting or real-time reactive distributed key-value synchronization.** |
| **6** | **Unified Data Framework** | **UDMF & Uniform Type Descriptors (UTD)**: Cross-app/cross-device drag-and-drop data abstraction. | Flutter standard clipboard & ad-hoc MIME data. | **No OS-level typed data drag-and-drop bus with standardized format descriptors.** |
| **7** | **Desktop Presentation** | **Atomic Services (Service Cards / Meta-Services)**: Zero-install, reactive 1x1, 2x1, 4x2 cards pinned directly to the desktop. | Windowed applications only (`DraggableWindow` in `desktop_shell.dart`). | **No desktop-embedded interactive service card canvas or micro-app widget architecture.** |
| **8** | **Live Real-Time Indicators** | **Live Window / Live View (实况窗)**: Status bar dynamic capsules that expand into interactive task trackers. | Standard notifications / snackbars. | **No persistent interactive status capsules for long-running jobs (e.g., quantum simulations, file sync).** |
| **9** | **Security & Privacy** | **Star Shield (Permissionless Pickers & DSLM)**: Ephemeral scoped tokens + Device Security Level (SL1–SL5) matching Data Risk (S1–S4). | Capability manager & HMAC checks; standard POSIX file paths. | **Missing permissionless picker sandbox and strict cross-device security level attestation.** |
| **10** | **System-Native AI** | **Harmony Intelligence & Intent Engine**: Screen semantic tree perception, cross-app intent chaining, floating HUD. | Standalone chat window app (`ai_assistant_app.dart`, `ai/`). | **AI cannot perceive active window contents, read UI trees, or execute multi-app workflow chains.** |
| **11** | **Scheduling & Frame Pacing** | **Deterministic Latency Engine**: Real-time QoS tiers prioritizing user touch & VSync over background workloads. | Quantum-inspired heuristic scheduler (`kernel/scheduler.py`). | **Scheduler is unaware of Flutter frame render deadlines (16.6ms/8.3ms) and cannot dynamically throttle background jobs.** |
| **12** | **Language & Scripting Layer** | **Cangjie & ArkTS**: Statically typed, memory-safe, native machine code compilation with macro DSLs and native C/Python interop. | Pure Python + Flutter/Dart. | **Lacks a statically typed, safe scripting DSL for writing sandboxed UmerOS kernel extensions.** |

---

## 3. Detailed Specifications & Implementation Prompts

Below are the **12 complete engineering blueprints**, each accompanied by an **executable prompt** designed to be copy-pasted directly into your agent to build the capability into UmerOS.

---

### Module 1: High-Performance Synchronous IPC Fastpath & Thread-Handoff

#### Architecture & HarmonyOS Benchmark
The HongMeng Microkernel achieves high throughput by avoiding the traditional microkernel IPC bottleneck. Rather than buffering messages through intermediate queues and incurring dual context switches, it uses **thread-handoff scheduling**: when Thread A sends a synchronous IPC call to Service B, the kernel immediately donates Thread A's remaining CPU time slice to Thread B, passing arguments directly via CPU registers or shared memory pages.

#### UmerOS Blueprint
* **Location**: `kernel/ipc/`
* `ipc_fastpath.py`: Direct synchronous invocation channel bypassing async message loops for intra-node priority calls.
* `shared_memory_transport.py`: Zero-copy ring buffer using `mmap` or shared memory arrays for large quantum state vectors and video frames.

#### Ready-to-Use Implementation Prompt
```markdown
### TASK: Implement High-Performance Synchronous IPC Fastpath and Shared Memory Transport in UmerOS

#### Context & Goal:
Upgrade UmerOS's `kernel/ipc_bus.py` with a HarmonyOS-inspired Synchronous IPC Fastpath and Zero-Copy Shared Memory transport. This ensures ultra-low latency communication between the Python kernel services and high-frequency subsystems (like Quantum simulation and Flutter UI events).

#### Requirements:
1. **Package Creation**: Create `kernel/ipc/` with:
   - `__init__.py`
   - `fastpath.py`: Implements `SynchronousIPCFastpath`.
   - `shm_transport.py`: Implements `SharedMemoryChannel` using Python `multiprocessing.shared_memory` or `mmap`.
   - `message_protocol.py`: Packed binary message headers `(magic: uint32, msg_id: uint64, sender_pid: uint32, target_pid: uint32, payload_size: uint32, checksum: uint32)`.
2. **Thread Handoff Simulator (`fastpath.py`)**:
   - Provide `call_sync(target_pid, method, args, timeout_ms=50)` that blocks the calling thread, yields control directly to the handler, and retrieves the return value with zero queue delay.
   - Maintain a capability authorization cache to validate sender permissions in O(1) time.
3. **Zero-Copy Payload Exchange (`shm_transport.py`)**:
   - For payloads > 64 KB (e.g., quantum state vectors, display frames), automatically allocate a shared memory ring buffer and pass memory descriptors rather than copying bytes over JSON/HMAC.
4. **Integration with `kernel/umer_kernel.py`**:
   - Register the fastpath transport inside the kernel boot sequence.
5. **Testing**:
   - Create `tests/test_ipc_fastpath.py` benchmarking throughput and latency against standard async queue IPC.
```

---

### Module 2: Distributed Soft Bus (UmerSoftBus)

#### Architecture & HarmonyOS Benchmark
HarmonyOS's **Distributed Soft Bus (DSoftBus)** unifies Bluetooth Low Energy, Wi-Fi Direct, and Ethernet into a single virtual bus. It provides continuous background discovery, mutual cryptographic handshakes, dynamic multi-path routing, and transparent channel switching if one network interface degrades.

#### UmerOS Blueprint
* **Location**: `network/softbus/`
* `discovery_beacon.py`: Multicast DNS (mDNS) and UDP broadcast (port 48899) broadcasting device UUID, capabilities, and public keys.
* `channel_manager.py`: TCP/TLS and UDP streaming channels with AES-256-GCM message framing.
* `softbus_bridge.py`: Router that intercepts kernel IPC addresses with prefix `@peer:<uuid>/` and sends them across the wire.

#### Ready-to-Use Implementation Prompt
```markdown
### TASK: Implement Distributed Soft Bus (UmerSoftBus) for Cross-Device Mesh Networking

#### Context & Goal:
Build the UmerSoftBus subsystem allowing multiple UmerOS workstations, VMs, or instances on a LAN/mesh to auto-discover each other without manual IP configuration, establishing encrypted peer-to-peer communication channels.

#### Requirements:
1. **Package Setup**: Create `network/softbus/` with `discovery.py`, `session.py`, `trans_channel.py`, and `softbus_service.py`.
2. **Peer Discovery (`discovery.py`)**:
   - Background broadcast thread using UDP multicast on port 48899 every 3 seconds.
   - Beacon payload includes: `node_id`, `node_name`, `device_class` (Desktop, VM, QuantumNode), `ip_address`, `port`, `capabilities`, `uptime`.
   - Maintain `PeerRegistry` with automatic stale node eviction after 10 seconds of missed heartbeats.
3. **Encrypted Session Protocol (`session.py`)**:
   - ECDH (Elliptic-Curve Diffie-Hellman) key exchange or pre-shared key HMAC authentication.
   - AES-GCM-256 frame encryption for all inter-node payloads.
4. **FastAPI & Flutter Bridge**:
   - Expose endpoints: `GET /api/softbus/peers`, `POST /api/softbus/broadcast`, `POST /api/softbus/send`.
   - Add WebSocket `/ws/softbus/events` streaming peer discovery and disconnection events to Flutter.
5. **Unit & Mesh Tests**:
   - Create `tests/test_softbus_mesh.py` simulating multi-node discovery and secure payload delivery.
```

---

### Module 3: Super Device & Distributed Hardware Virtualization

#### Architecture & HarmonyOS Benchmark
The **Super Device** architecture virtualizes hardware peripherals so that any device in the mesh can use another node's hardware as if it were local:
* **Virtual Camera**: Phone camera streams to PC as a native webcam input device.
* **Virtual Screen / Input Roaming**: Moving the mouse past the right edge of the laptop screen moves the cursor onto the adjacent tablet/desktop screen.
* **Universal Clipboard**: Copying text/images on Node A instantly enables pasting on Node B.

#### UmerOS Blueprint
* **Location**: `drivers/distributed/` & `ui/flutter_ui/lib/src/widgets/super_device/`
* `virtual_clipboard.py`: Real-time cross-device clipboard sync with loop prevention.
* `virtual_input_router.py`: Mouse coordinate edge-detection and keyboard event forwarding.
* `super_device_radar.dart`: Flutter UI featuring a planetary gravitational radar where users drag device icons to connect them.

#### Ready-to-Use Implementation Prompt
```markdown
### TASK: Implement Super Device Hardware Virtualization and Flutter Radar Control Center

#### Context & Goal:
Create a HarmonyOS-style "Super Device" peripheral pool and an interactive Flutter control panel for UmerOS, supporting unified clipboard synchronization, remote screen streaming, and an orbiting planetary UI.

#### Requirements:
1. **Universal Distributed Clipboard (`core/distributed_clipboard.py`)**:
   - Monitor local clipboard changes. When updated, sign and broadcast payload over UmerSoftBus to paired nodes.
   - Prevent infinite echo loops using UUID hashing and origin node tracking.
2. **Virtual Peripheral Forwarder (`drivers/distributed/virtual_input.py`)**:
   - Screen-edge pointer routing: When mouse reaches x == screen_width, broadcast pointer movement events to peer node.
3. **Flutter Super Device Radar Widget (`ui/flutter_ui/lib/src/widgets/super_device_radar.dart`)**:
   - Central glowing circle representing "This UmerOS Node".
   - Orbiting satellite circles representing discovered UmerOS peers (retrieved from `/api/softbus/peers`).
   - Interactive Drag-and-Drop: Drag an orbiting device onto the central circle to snap-bind them. Trigger a connection animation and call `/api/super_device/pair`.
   - Show toggle switches for: "Sync Clipboard", "Share Keyboard/Mouse", "Mount Remote Files".
4. **Dock Integration**:
   - Add a "Super Device" icon in `ui/flutter_ui/lib/src/widgets/dock.dart` opening the radar modal.
```

---

### Module 4: Cross-Device Task Continuation (Ability Migration / "Hopping")

#### Architecture & HarmonyOS Benchmark
HarmonyOS's **Ability Continuation** lets users transfer an ongoing task seamlessly:
1. User taps "Continue on Device B".
2. The active app's `onSaveData(wantParam)` hook serializes its state (document text, cursor index, scroll position, audio playback timestamp).
3. The Distributed Scheduler launches the app on Node B and executes `onRestoreData(wantParam)`.
4. The local window terminates or enters companion mode.

#### UmerOS Blueprint
* **Location**: `ui/flutter_ui/lib/src/core/continuation_contract.dart` & `kernel/task_migration.py`
* Implement `ContinuationParticipant` contract in `text_editor_app.dart`, `terminal_app.dart`, and `quantum_app.dart`.
* Add a "Hop to Node..." button in `draggable_window.dart`.

#### Ready-to-Use Implementation Prompt
```markdown
### TASK: Implement Cross-Device Task Continuation (App Hopping) in UmerOS

#### Context & Goal:
Enable live application migration (hopping) across UmerOS instances so users can transfer open windows (e.g. Text Editor, Terminal session, or Quantum Circuit builder) to another machine with state preserved.

#### Requirements:
1. **Continuation Contract (`ui/flutter_ui/lib/src/core/continuation_contract.dart`)**:
   - Define interface `ContinuationParticipant`:
     - `Map<String, dynamic> onSaveContinuationData();`
     - `void onRestoreContinuationData(Map<String, dynamic> data);`
2. **App Integrations**:
   - `text_editor_app.dart`: Serialize open file path, text buffer, cursor offset, and unsaved changes.
   - `terminal_app.dart`: Serialize current working directory, command history, and environment variables.
   - `quantum_app.dart`: Serialize active quantum circuit gates, qubit count, and simulation parameters.
3. **Backend Migration Dispatcher (`kernel/task_migration.py`)**:
   - Endpoint `POST /api/tasks/migrate`: Takes `app_id`, `state_payload`, and `target_node_id`.
   - Sends payload across UmerSoftBus. Target node receives event via WebSocket, opens the window, and hydrates state.
4. **Window UI Trigger (`ui/flutter_ui/lib/src/widgets/draggable_window.dart`)**:
   - In the window title bar, add a "Migrate (Hop)" button next to maximize/close.
   - Clicking displays a dropdown of paired UmerOS devices; selecting one animates the window flying off-screen and confirms successful handoff.
```

---

### Module 5: Distributed VFS (UmerDFS) & In-Memory Data Objects (DDO)

#### Architecture & HarmonyOS Benchmark
HarmonyOS features **HMDFS (Harmony Distributed File System)** and **Distributed Data Objects (DDO)**:
* Remote folders appear locally under `/mnt/hmdfs/<device_id>/` without requiring manual Samba/NFS mounts.
* Distributed Data Objects allow two apps on different devices to share an in-memory object instance. When Node A mutates `object.status = "done"`, Node B's UI reflects the change via reactive listeners backed by CRDT conflict resolution.

#### UmerOS Blueprint
* **Location**: `fs/dfs/` & `core/distributed_object.py`
* `distributed_vfs.py`: Virtual filesystem adapter implementing POSIX calls (`open`, `read`, `write`, `readdir`) over SoftBus.
* `crdt_object.py`: Conflict-Free Replicated Data Type (LWW-Element-Set) engine.

#### Ready-to-Use Implementation Prompt
```markdown
### TASK: Implement Distributed VFS (UmerDFS) and CRDT-Backed Distributed Data Objects (DDO)

#### Context & Goal:
Implement a distributed filesystem mount and in-memory CRDT data synchronization engine in Python, integrating peer storage directly into the UmerOS File Manager.

#### Requirements:
1. **Distributed VFS Engine (`fs/dfs/distributed_vfs.py`)**:
   - Create `DistributedVFS(BaseFileSystem)` providing virtual directory mapping:
     - Accessing `dfs://<peer_node_id>/shared/` sends chunked read/write requests over UmerSoftBus.
   - Implement client-side LRU chunk caching to optimize repeated reads.
2. **In-Memory Distributed Data Object (`core/crdt_object.py`)**:
   - Create `DistributedDataObject` class implementing reactive key-value storage.
   - Use hybrid logical clocks (HLC) and Last-Write-Wins (LWW) conflict resolution to sync property changes across nodes automatically.
3. **Flutter File Manager Update (`ui/flutter_ui/lib/src/apps/file_manager_app.dart`)**:
   - Add "Network Devices" to the folder tree view.
   - Browsing a peer shows files with thumbnail previews and progress bars during drag-and-drop file transfers.
4. **Tests (`tests/test_distributed_vfs.py`)**:
   - Test virtual directory listing, remote chunked reads, write propagation, and offline fallback behavior.
```

---

### Module 6: Unified Data Management Framework (UDMF) & Uniform Type Descriptors (UTD)

#### Architecture & HarmonyOS Benchmark
HarmonyOS's **UDMF** eliminates data parsing ambiguities between applications. Instead of raw clipboard strings or unstructured drag-and-drop events, UDMF defines **Uniform Type Descriptors (UTD)** (hierarchical type IDs like `general.plain-text`, `general.image`, `general.file`, `system.quantum-circuit`). When a user drags an item between apps or across devices, UDMF standardizes metadata, access validation, and memory-efficient transfer.

#### UmerOS Blueprint
* **Location**: `core/udmf/` & `ui/flutter_ui/lib/src/core/udmf/`
* `utd_registry.py`: Hierarchy of standardized data types.
* `unified_data_channel.py`: Drag-and-drop and clipboard payload container.

#### Ready-to-Use Implementation Prompt
```markdown
### TASK: Implement Unified Data Management Framework (UDMF) and Uniform Type Descriptors (UTD)

#### Context & Goal:
Build a standardized Unified Data Management Framework for UmerOS, establishing typed, secure, cross-app and cross-device drag-and-drop and data exchange.

#### Requirements:
1. **UTD Registry (`core/udmf/utd_registry.py`)**:
   - Define hierarchical type descriptors:
     - `general.entity` -> `general.text` -> `general.plain-text`, `general.html`
     - `general.media` -> `general.image`, `general.audio`, `general.video`
     - `general.file` -> `general.document`
     - `umeros.quantum-qasm`, `umeros.task-state`
   - Provide conversion methods between MIME types, file extensions, and UTD identifiers.
2. **Unified Data Object Container (`core/udmf/unified_data.py`)**:
   - Implement `UnifiedData`: Encapsulates multiple type representations of the same data (e.g. rich text + plain text + thumbnail) with access authorization checks.
3. **Flutter Drag-and-Drop Bus (`ui/flutter_ui/lib/src/core/udmf/udmf_bridge.dart`)**:
   - Wrap Flutter's `Draggable` and `DragTarget` with UDMF type checking (e.g., only accept drops if UTD conforms to `general.image`).
4. **Testing**:
   - Create `tests/test_udmf.py` verifying UTD inheritance checks and serialization/deserialization.
```

---

### Module 7: Atomic Services & Live Service Cards (Meta-Services)

#### Architecture & HarmonyOS Benchmark
**Atomic Services** are installation-free, card-based micro-applications that live directly on the desktop wallpaper canvas or in the notification center. They feature:
* Fixed grid form factors (1x1 Small, 2x1 Medium, 2x2 Large, 4x2 Wide).
* Live updates via background push or timer without opening an app window.
* In-place interactive controls (play/pause, toggles, quick inputs).
* "Expand to App" button smoothly transitioning the card into its full desktop application.

#### UmerOS Blueprint
* **Location**: `ui/flutter_ui/lib/src/widgets/atomic_cards/`
* `atomic_card_host.dart`: Interactive desktop grid manager.
* Built-in cards: System Vitals, Quantum State Monitor, AI Context Pill, Super Device Mesh Status.

#### Ready-to-Use Implementation Prompt
```markdown
### TASK: Implement Atomic Services and Desktop Service Cards for the Flutter Shell

#### Context & Goal:
Create a HarmonyOS-style "Atomic Services" card system on the UmerOS desktop canvas. Users can place, resize, and interact with lightweight live cards directly on the desktop background.

#### Requirements:
1. **Card Component Architecture (`ui/flutter_ui/lib/src/widgets/atomic_cards/`)**:
   - Create `AtomicCardBase` widget:
     - Supports sizes: `CardSize.small` (160x160), `CardSize.medium` (340x160), `CardSize.large` (340x340).
     - Glassmorphism design (frosted glass blur, subtle border highlight).
     - Action header with "Expand to App" button and flip-card settings button.
2. **Implement 4 Production Cards**:
   - `SystemVitalsCard`: Live mini-charts of CPU%, RAM%, temperature, and active kernel tasks.
   - `QuantumMonitorCard`: Real-time state vector probability histogram and quick "Run Benchmark" button.
   - `SuperDeviceMeshCard`: Nearby online peers list with one-tap toggle to share clipboard/files.
   - `AIQuickAgentCard`: One-line voice/text query box that displays instant answers.
3. **Desktop Canvas Layer (`ui/flutter_ui/lib/src/core/desktop_shell.dart`)**:
   - Render cards between the wallpaper background and the floating window stack.
   - Support dragging cards to reorder on a snap-to-grid layout.
   - Persist card positions in `prefs_service.dart`.
```

---

### Module 8: Live Window / Live View (实况窗) Dynamic Status Capsule

#### Architecture & HarmonyOS Benchmark
The **Live Window (实况窗)** provides continuous, glanceable task tracking without cluttering the screen with alert dialogs. When a long-running operation begins (e.g. Quantum circuit execution, OTA OS update, file sync, or background backup):
* A compact pill/capsule appears in the top menu bar or status bar showing an icon, animation, and progress percentage.
* Clicking or hovering expands the capsule into a floating live card with pause/cancel controls.
* When finished, it animates smoothly into a completion badge and auto-dismisses.

#### UmerOS Blueprint
* **Location**: `ui/flutter_ui/lib/src/widgets/live_view/` & `core/live_window_manager.py`
* `live_view_capsule.dart`: Status bar pill widget with micro-animations.
* `live_window_service.dart`: Stream listener receiving real-time task progress.

#### Ready-to-Use Implementation Prompt
```markdown
### TASK: Implement Live Window / Live View (实况窗) Dynamic Status Capsule

#### Context & Goal:
Build a HarmonyOS-inspired "Live Window" (Live View) system-bar capsule in Flutter and Python to provide real-time glanceable progress for background tasks (quantum simulations, backups, file transfers).

#### Requirements:
1. **Live Task Registry in Python (`core/live_task_manager.py`)**:
   - Class `LiveTaskManager`: Exposes `start_task(task_id, title, icon, total_steps)`, `update_progress(task_id, current_step, status_text)`, `finish_task(task_id)`.
   - Broadcast state changes over WebSocket `/ws/live_tasks`.
2. **Flutter Live View Capsule (`ui/flutter_ui/lib/src/widgets/live_view_capsule.dart`)**:
   - Place in the desktop top status bar next to the clock.
   - When tasks are active, render a sleek animated pill (e.g., rotating quantum atom icon + "Simulating: 42%").
   - Click to expand: Pops open a mini card with progress bar, detailed log string, and "Cancel Task" button.
   - Support multiple simultaneous tasks with a carousel/stack animation.
3. **Hook into Long-Running Tasks**:
   - Connect `quantum/` simulation runs and `backup/` operations to update `LiveTaskManager`.
```

---

### Module 9: Star Shield Security Architecture & Device Security Levels (DSLM)

#### Architecture & HarmonyOS Benchmark
HarmonyOS NEXT's **Star Shield** establishes a zero-trust hardware/software foundation:
1. **Permissionless Pickers**: Eliminates blanket permissions (`READ_STORAGE`, `ACCESS_CAMERA`). When an app needs a file or photo, it calls a privileged system picker. The OS handles selection and hands back a scoped, ephemeral token.
2. **Device Security Level Management (DSLM)**: Classifies nodes from **SL1 (Basic IoT/untrusted)** to **SL5 (Formally verified / Hardware TEE)**. Data is labeled from **S1 (Public)** to **S4 (Critical / Biometrics / Private Keys)**. The kernel enforces:
$$\text{Data Security Level} \le \text{Target Device Security Level}$$
High-risk data is blocked from routing to low-SL devices.

#### UmerOS Blueprint
* **Location**: `security/star_shield/`
* `dslm_authority.py`: Calculates local SL rating and validates remote node attestation certificates.
* `scoped_token_gate.py`: Replaces static filesystem paths with time-limited capability tokens.
* `secure_picker.dart`: Privileged Flutter modal sheet running in an isolated system overlay.

#### Ready-to-Use Implementation Prompt
```markdown
### TASK: Implement Star Shield Permissionless Pickers and DSLM Security Engine

#### Context & Goal:
Implement HarmonyOS Star Shield security architecture in UmerOS, introducing Device Security Level Management (SL1–SL5) matched against Data Sensitivity (S1–S4), and replacing broad permissions with scoped ephemeral pickers.

#### Requirements:
1. **DSLM Security Rating Engine (`security/star_shield/dslm.py`)**:
   - Implement node security evaluation:
     - `SL1`: Basic unverified user space environment.
     - `SL2`: Standard runtime with integrity checks.
     - `SL3`: Signed modules, post-quantum crypto enabled (`liboqs`), clean kernel taint.
     - `SL4`: Hardware-backed credentials and verified boot.
   - Label data payloads with `DataSensitivity` enum: `S1_PUBLIC`, `S2_INTERNAL`, `S3_CONFIDENTIAL`, `S4_CRITICAL`.
   - Inter-node routing gate: If a peer requests `S4` data (e.g. quantum key exchange) but has an attestation of `SL2`, reject the request and log an audit alarm in `kernel/audit.py`.
2. **Scoped Ephemeral Capability Tokens (`security/star_shield/scoped_token.py`)**:
   - Generate HMAC-signed tokens with expiration (default: 60s) granting access to exactly one file or socket.
   - Intercept calls in `fs/` and `kernel/capability_manager.py` to enforce token validation.
3. **Privileged System Picker (`ui/flutter_ui/lib/src/pickers/system_file_picker.dart`)**:
   - System dialog that allows users to pick a file without granting the app blanket disk access. Returns only an ephemeral token.
4. **Testing (`tests/test_star_shield.py`)**:
   - Verify that data cross-routing conforms strictly to the `Data Security <= Device SL` rule.
```

---

### Module 10: Harmony Intelligence (Ubiquitous Screen-Aware AI Context Agent)

#### Architecture & HarmonyOS Benchmark
In HarmonyOS NEXT, AI (Celia) is integrated at the system level rather than operating as an isolated chatbot:
* **Screen Perception**: Reads the active window's accessibility/semantic widget tree to understand what the user is looking at.
* **App Intent Registry**: Apps publish structured action schemas (e.g., `text_editor.insert_text`, `file_manager.find_files`, `quantum.run_job`).
* **Cross-App Chaining**: The user can say "Take the code from my open editor, optimize it, and save the result into a new document."
* **Floating Context HUD**: A universal floating pill (`Ctrl + Space`) that pops up over any window.

#### UmerOS Blueprint
* **Location**: `ai/system_agent/` & `ui/flutter_ui/lib/src/widgets/ai_floating_hud.dart`
* `intent_registry.py`: Decorator-based capability registration for all UmerOS apps.
* `screen_context_inspector.py`: Queries Flutter semantic tree data to extract on-screen text and layout.

#### Ready-to-Use Implementation Prompt
```markdown
### TASK: Implement System-Wide AI Context Agent and Cross-App Intent Registry

#### Context & Goal:
Upgrade UmerOS AI from a standalone chat app into a HarmonyOS-inspired system-level contextual intelligence service capable of reading on-screen content and orchestrating multi-app workflows.

#### Requirements:
1. **App Intent Registry (`core/intent_registry.py`)**:
   - Create `@register_intent("app_name.action_name", schema={...})` decorator.
   - Register core app capabilities:
     - `text_editor.get_active_text()`, `text_editor.replace_selection(text)`
     - `file_manager.list_directory(path)`, `file_manager.search(query)`
     - `quantum.simulate_circuit(qasm)`
     - `system.get_vitals()`
2. **Semantic Screen Perception Bridge (`ai/system_agent/screen_perceiver.py`)**:
   - Flutter shell streams the focused window title, active text selection, and semantic tree summary to `/api/ai/screen_context`.
3. **Cross-App Workflow Planner (`ai/system_agent/intent_planner.py`)**:
   - Use the local LLM (`ai/`) to parse natural language instructions into multi-step tool calls:
     - e.g. "Summarize the text currently open in Text Editor and copy it to my clipboard."
   - Execute the calls sequentially through the UmerOS IPC bus.
4. **Floating AI HUD Widget (`ui/flutter_ui/lib/src/widgets/ai_floating_hud.dart`)**:
   - Universal floating capsule triggered via global shortcut `Ctrl + Space`.
   - Offers one-tap contextual suggestion chips based on the active window (e.g. if Terminal has an error -> "Explain Error"; if in Editor -> "Fix Spelling / Refactor").
```

---

### Module 11: Deterministic Latency Engine (Real-Time UI QoS & Frame Pacing)

#### Architecture & HarmonyOS Benchmark
To eliminate UI stutter and dropped frames, HarmonyOS's **Deterministic Latency Engine** uses real-time Quality of Service (QoS) scheduling:
* User touch, keyboard, and pointer events are granted the highest priority (`QoS_UserInteractive`).
* The UI render loop enforces 120 FPS / 60 FPS deadlines.
* Background batch tasks (e.g. heavy quantum state simulations, file indexing, antivirus scans) are automatically throttled whenever interactive rendering demands CPU cycles.

#### UmerOS Blueprint
* **Location**: `kernel/qos/` & `kernel/scheduler.py`
* `qos_levels.py`: Enums `USER_INTERACTIVE`, `USER_INITIATED`, `UTILITY`, `BACKGROUND`.
* Hook into Flutter's `WidgetsBinding.instance.addPersistentFrameCallback` to stream frame timing telemetry to the Python kernel scheduler.

#### Ready-to-Use Implementation Prompt
```markdown
### TASK: Implement Deterministic Latency Engine and Frame-Pacing QoS Scheduler

#### Context & Goal:
Enhance `kernel/scheduler.py` with a Deterministic Latency Engine inspired by HarmonyOS, preventing heavy background quantum simulations or file operations from causing dropped frames in the Flutter UI.

#### Requirements:
1. **Task QoS Hierarchy (`kernel/qos.py`)**:
   - Define QoS tiers:
     - `QoS_INTERACTIVE` (Weight: 100, preemptive)
     - `QoS_RENDER` (Weight: 80, frame-deadline driven)
     - `QoS_UTILITY` (Weight: 40)
     - `QoS_BACKGROUND` (Weight: 10, throttles when interactive tasks are running)
2. **Scheduler Priority Inheritance & Dynamic Throttling (`kernel/scheduler.py`)**:
   - If a background task holds an IPC lock or resource required by an interactive task, immediately elevate its QoS to `QoS_INTERACTIVE`.
   - When the scheduler receives high render-load notifications, automatically reduce the time slices allocated to background simulation workers.
3. **Flutter Frame Telemetry Heartbeat (`ui/flutter_ui/lib/src/services/frame_telemetry.dart`)**:
   - Measure each frame render duration in milliseconds.
   - If render duration exceeds 16.6ms (dropped 60 FPS frame), dispatch a pulse to `/api/kernel/frame_telemetry?dropped=true`.
   - The kernel instantly throttles background worker threads to restore UI smoothness.
4. **Tests (`tests/test_qos_scheduler.py`)**:
   - Run a simulated quantum computation benchmark while executing high-frequency interactive events, verifying that interactive latency remains sub-5ms.
```

---

### Module 12: Cangjie-Inspired Type-Safe Scripting Layer for Kernel Extensions

#### Architecture & HarmonyOS Benchmark
Alongside HarmonyOS NEXT, Huawei introduced **Cangjie** (仓颉): a modern, statically typed, memory-safe, multi-paradigm systems language featuring native AI hooks, pattern matching, lightweight macros, and zero-cost C/Python interoperability. It enables developers to write high-performance, type-safe modules without the security pitfalls of raw C.

#### UmerOS Blueprint
* **Location**: `sdk/cangjie_dsl/`
* Implement a Python-native type-safe DSL / compiler shim allowing developers to write sandboxed UmerOS kernel modules and drivers with strict static validation, pattern matching, and runtime safety gates.

#### Ready-to-Use Implementation Prompt
```markdown
### TASK: Implement Type-Safe Kernel Extension DSL and Sandboxed Plugin Engine

#### Context & Goal:
Create a Cangjie-inspired type-safe scripting SDK for UmerOS, allowing developers to author kernel extensions and drivers with strict static typing, pattern matching, and memory safety gates.

#### Requirements:
1. **DSL Definition (`sdk/kernel_dsl/extension_base.py`)**:
   - Define base class `KernelExtension` enforcing strict type annotations on all methods.
   - Provide `@system_capability("cap_name")` decorators that statically verify required permissions before execution.
2. **Sandboxed Plugin Runner (`kernel/plugin_runner.py`)**:
   - Execute user extensions in an isolated worker process with restricted system call access.
   - Enforce resource quotas (max CPU time, max memory footprint) using `kernel/cgroup.py`.
3. **Pattern Matching & Algebraic Data Types (`sdk/kernel_dsl/types.py`)**:
   - Implement typed Result/Option structures (`Success(value)`, `Failure(error)`) and exhaustiveness validation.
4. **Sample Extension**:
   - Build a sample driver `VirtualSensorExtension` in `examples/sample_sensor_extension.py` showcasing the type-safe DSL.
```

---

## 4. Master 4-Phase Implementation Roadmap

To maintain system stability and continuous CI pass rates, implement these modules according to the following dependency graph:

```mermaid
flowchart TD
    subgraph Phase 1: Microkernel & Mesh Foundation
        M1[Module 1: High-Performance Sync IPC Fastpath]
        M2[Module 2: Distributed Soft Bus UmerSoftBus]
        M5[Module 5: Distributed VFS UmerDFS & DDO]
    end

    subgraph Phase 2: Security & Scheduling Engine
        M9[Module 9: Star Shield DSLM & Pickers]
        M11[Module 11: Deterministic Latency QoS Scheduler]
        M6[Module 6: UDMF & Uniform Type Descriptors]
    end

    subgraph Phase 3: Desktop Shell & Presentation
        M7[Module 7: Atomic Services Desktop Cards]
        M8[Module 8: Live Window 实况窗 Status Capsule]
        M3[Module 3: Super Device Virtual Peripheral Radar]
    end

    subgraph Phase 4: Intelligence, Mobility & SDK
        M4[Module 4: Cross-Device Task Continuation]
        M10[Module 10: Ubiquitous Harmony Intelligence Agent]
        M12[Module 12: Type-Safe Kernel Extension DSL]
    end

    Phase 1 --> Phase 2
    Phase 2 --> Phase 3
    Phase 3 --> Phase 4
```

---

## 5. How to Execute These Prompts

To implement any module:
1. Select the module you want to develop (e.g., **Module 1** or **Module 2**).
2. Copy the entire prompt block under that module.
3. Paste it directly into the chat session.
4. The AI assistant will read the specifications, create the Python backend modules and Flutter UI components, wire up the APIs, and execute verification tests.
