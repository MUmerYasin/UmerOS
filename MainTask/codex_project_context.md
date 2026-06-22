# UmerOS Codex Project Context

Generated: 2026-06-22

## Project Goal

UmerOS is a Python-first, AI-native, quantum-inspired operating system research prototype. The local prompts define a realistic engineering approach: Python user-space microkernel prototype, simulated quantum features today, future QPU interfaces only as documented hooks, local-first AI, zero-trust security, compatibility containers, Kivy UI, QFS-style compression, and explicit TODAY / EXPERIMENTAL / FUTURE labeling.

## Prompt And Skill Sources Loaded

- `MainTask/prompt/Umer_OS_Antigravity_Master_Prompt.md`
- `MainTask/prompt/deep-research-report_from_chatgpt.md`
- `MainTask/prompt/deep-research-report.md`
- `MainTask/prompt/full prompt_perplexity.md`
- `MainTask/prompt/umer_os_master_prompt.md`
- `MainTask/prompt/umer_os_master_prompt_Gemini-code.md`
- `MainTask/prompt/Umer_OS_Prompt_deepseek.md`
- `MainTask/prompt/Umer OS_ An Engineering Blueprint for a Python-Based Quantum-Native Operating System with Integrated Runbooks and Skill Requirements.md`
- `Skills/Context File/umer_os_skills.json`
- `Skills/Context File/skills_gemini-code.json`
- `Skills/Context File/umer_skills_deepseek.md`

## Active UmerOS Code Shape

The active entrypoint is `main.py`, which calls `bootloader.init.boot()` and then `kernel.umer_kernel.UmerKernel.start()`.

Important active packages:

- `ai/assistant.py`: local assistant stub and task-success predictor.
- `bootloader/init.py`: environment check and boot metadata.
- `kernel/scheduler.py`: asyncio scheduler plus HybridScheduler draft.
- `kernel/ipc.py`: simple asyncio IPC broker.
- `kernel/hal.py`: ctypes binding to `drivers/hal.c`.
- `quantum/simulator.py`: scheduler duplicate plus simple quantum circuit simulator.
- `filesystem/qfs.py`: in-memory LZMA-backed QFS prototype.
- `security/sandbox.py`: capability/process record sandbox stub.
- `compatibility/container.py`: simulated Linux/Windows/Android app launchers.
- `ui/fluidic_ui.py`: Kivy fallback console UI.

Known live issues:

- `kernel/umer_kernel.py` defines `start()` outside the `UmerKernel` class, so `main.py` fails with `AttributeError: 'UmerKernel' object has no attribute 'start'`.
- `examples/run_demo.py` imports `SimpleQuantumSimulator`, but `quantum/simulator.py` does not define it.
- The installed pytest on Python 3.14 fails because it imports removed module `imp`; use Python 3.12/3.13 or install a compatible pytest.
- `settings.local.json` contains a plaintext OpenRouter API key and should be treated as exposed.

## Old Linux Code Context

`Old Linux Code` is a Linux kernel source snapshot/reference tree, not active UmerOS Python code. It has about 93,684 files and no `.git` directory. Top-level `Makefile` identifies it as:

- `VERSION = 7`
- `PATCHLEVEL = 1`
- `SUBLEVEL = 0`
- `NAME = Baby Opossum Posse`

The top-level structure matches the upstream `torvalds/linux` layout: `arch`, `block`, `certs`, `crypto`, `Documentation`, `drivers`, `fs`, `include`, `init`, `io_uring`, `ipc`, `kernel`, `lib`, `mm`, `net`, `rust`, `samples`, `scripts`, `security`, `sound`, `tools`, `usr`, `virt`, plus top-level `COPYING`, `Kbuild`, `Kconfig`, `MAINTAINERS`, `Makefile`, and `README`.

Largest local Linux subtrees by file count:

- `drivers`: 37,226 files
- `arch`: 18,420 files
- `Documentation`: 11,158 files
- `tools`: 9,233 files
- `include`: 6,605 files

Primary file types:

- `.c`: 36,681
- `.h`: 26,667
- extensionless files: 6,919
- `.yaml`: 5,543
- `.rst`: 3,956
- `.dts`: 3,584
- `.dtsi`: 2,671

Important Linux workflow constraints:

- The Linux source tree itself rejects source directories containing spaces or colons (`Old Linux Code/Makefile`, line 217). The current Windows path `F:\Pension Person Details\UmerOS\Old Linux Code` has both a drive colon and spaces, so it is not a suitable direct kernel build path.
- This Windows environment has no visible `make`, `gcc`, or `perl`; WSL is installed only as a stub and has no Linux distribution configured.
- Local static checks found no `.orig`, `.rej`, `.bak`, object/module build artifacts, Zone.Identifier files, or reparse-point symlinks in `Old Linux Code`.
- Some zero-length files exist; these are likely legitimate placeholders/test fixtures in the kernel tree, not automatically corruption.

Linux AI assistant rules loaded from `Old Linux Code/Documentation/process/coding-assistants.rst`:

- AI agents must not add `Signed-off-by` tags.
- Human submitter must review and certify DCO.
- Kernel-compatible code must be GPL-2.0-only compatible.
- AI involvement may be attributed with an `Assisted-by` tag if preparing upstream-style patches.

## Working Rule For Future Turns

Treat `Old Linux Code` as the Linux kernel reference source. Do not edit it casually. If a Linux-side error appears, first determine whether it is:

1. a local environment/path/toolchain issue,
2. snapshot corruption or missing files,
3. an upstream Linux issue,
4. a UmerOS integration misunderstanding.

When needed, compare against official upstream `torvalds/linux` before changing anything.
