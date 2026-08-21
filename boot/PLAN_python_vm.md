# UmerOS Python Virtual Machine - Implementation Plan

## Executive Summary

Build a real, compiled C-based Python 3.x interpreter for UmerOS that lives in
`/boot/python_vm/`. Bytecode compiler + virtual machine. Compiled during UmerOS
installation for the target platform.

**Scope**: Python 3.x core - functions, classes, exceptions, modules,
comprehensions, generators, decorators.

## Architecture

```
Source (.py) -> Lexer -> Parser -> AST -> Compiler -> Bytecode -> VM execution
```

- **Language**: C (zero runtime dependencies)
- **Bytecode**: CPython-compatible opcodes
- **Build**: CMake + Makefile
- **Parser**: PEG (like CPython 3.9+)

## Implementation Phases

| Phase | Weeks | Deliverable |
|-------|-------|-------------|
| 1. Foundation | 1-2 | print("Hello, UmerOS!") works |
| 2. Lexer+Parser | 3-4 | Source to AST parsing |
| 3. Bytecode Compiler | 5-6 | AST to bytecode |
| 4. Virtual Machine | 7-9 | Execute bytecode fully |
| 5. Builtins + Modules | 10-11 | Core builtins and modules |
| 6. Standard Library | 12-14 | Python stdlib subset |
| 7. REPL + Installer | 15-16 | Interactive REPL + runtime manager |

## File Structure

```
boot/python_vm/
  CMakeLists.txt, Makefile
  Include/     - Headers (object.h, pycode.h, pyast.h, pyvm.h)
  Objects/     - Built-in types (int, float, str, list, dict, etc.)
  Compiler/    - Tokenizer, PEG parser, AST, bytecode compiler
  VM/          - Eval loop, frames, opcode dispatch
  Builtins/    - print, len, range, import, etc.
  Modules/     - sys.c, os.c, math.c, time.c
  Lib/         - Python stdlib subset
  Programs/    - main.c, interactive.c (REPL)
```

## Runtime Manager

`boot/python_runtime.py` handles platform detection, building from source,
installing to `/usr/bin/umeros-python`, and symlink management.
