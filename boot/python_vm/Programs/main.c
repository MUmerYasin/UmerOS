/*
 * main.c - UmerOS Python Interpreter Entry Point
 *
 * Reads Python source code from file or stdin,
 * compiles to bytecode, and executes.
 *
 * Usage:
 *   umerospython                        # Interactive REPL
 *   umerospython script.py              # Execute script file
 *   umerospython -c "code"              # Execute code string
 *   umerospython -m module              # Run module as __main__
 *   umerospython --quiet script.py      # Suppress REPL banner
 *   umerospython --verbose script.py    # Verbose compilation output
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <signal.h>
#include <sys/stat.h>
#include <windows.h>
#include "../Include/umeros_python.h"
#include "../Include/pycode.h"
#include "../Include/pyvm.h"

/* Forward declarations */
extern void PyErrors_Init(void);
extern void PyBool_Init(void);
extern void PyNone_Init(void);
extern void PyBuiltins_Init(void);
extern PyObject* PyBuiltins_GetDict(void);
extern PyObject* Py_CompileString(const char *source, const char *filename);
extern PyObject* PyEval_EvalCode(PyCodeObject *code, PyObject *globals, PyObject *locals);
extern void Compiler_Test(void);

/* Sys module forward declarations */
extern void SysModule_Init(void);
extern PyObject* SysModule_GetDict(void);
extern void SysModule_AddToPath(const char *dir);
extern PyObject* SysModule_GetPath(void);

/* Global flags */
static int quiet_mode = 0;
static int verbose_mode = 0;
static int force_mode = 0;

/* Singleton lock file */
#define LOCK_FILE ".umeros_python.lock"
static char lock_path[4096];
static int lock_held = 0;

/* Persistent REPL history */
#define HISTORY_MAX 1000
#define HISTORY_FILE ".umeros_history"

static char *history[HISTORY_MAX];
static int history_count = 0;

static const char* GetHistoryPath(void) {
    const char *home = getenv("HOME");
    if (!home) home = getenv("USERPROFILE");
    if (!home) home = ".";

    static char path[4096];
    snprintf(path, sizeof(path), "%s/%s", home, HISTORY_FILE);
    return path;
}

static void LoadHistory(void) {
    const char *path = GetHistoryPath();
    FILE *fp = fopen(path, "r");
    if (!fp) return;

    char buf[4096];
    while (fgets(buf, sizeof(buf), fp) && history_count < HISTORY_MAX) {
        /* strip trailing newline */
        Py_ssize_t len = strlen(buf);
        while (len > 0 && (buf[len-1] == '\n' || buf[len-1] == '\r')) {
            buf[--len] = '\0';
        }
        if (len == 0) continue;
        history[history_count] = strdup(buf);
        if (history[history_count]) history_count++;
    }
    fclose(fp);
}

static void SaveHistory(void) {
    const char *path = GetHistoryPath();
    FILE *fp = fopen(path, "w");
    if (!fp) return;
    for (int i = 0; i < history_count; i++) {
        fprintf(fp, "%s\n", history[i]);
    }
    fclose(fp);
}

static void AddToHistory(const char *line) {
    /* Deduplicate: skip if identical to last entry */
    if (history_count > 0 && strcmp(history[history_count - 1], line) == 0) {
        return;
    }
    if (history_count >= HISTORY_MAX) {
        /* Shift out oldest */
        free(history[0]);
        for (int i = 1; i < history_count; i++) {
            history[i - 1] = history[i];
        }
        history_count--;
    }
    history[history_count] = strdup(line);
    if (history[history_count]) history_count++;
}

static void FreeHistory(void) {
    for (int i = 0; i < history_count; i++) {
        free(history[i]);
        history[i] = NULL;
    }
    history_count = 0;
}

/* ============================================================
 * Singleton Lock File Implementation
 * ============================================================ */

/* Get path to the lock file */
static const char* GetLockPath(void) {
    const char *home = getenv("HOME");
    if (!home) home = getenv("USERPROFILE");
    if (!home) home = ".";

    snprintf(lock_path, sizeof(lock_path), "%s/%s", home, LOCK_FILE);
    return lock_path;
}

/* Check if a process with given PID is still running */
static int IsProcessAlive(int pid) {
#ifdef _WIN32
    /* Windows: use OpenProcess */
    HANDLE hProcess = OpenProcess(PROCESS_QUERY_INFORMATION, FALSE, (DWORD)pid);
    if (hProcess == NULL) {
        return 0; /* Process doesn't exist */
    }
    DWORD exitCode;
    BOOL success = GetExitCodeProcess(hProcess, &exitCode);
    CloseHandle(hProcess);
    /* STILL_ACTIVE = 259 on Windows */
    return (success && exitCode == STILL_ACTIVE);
#else
    /* POSIX: kill(pid, 0) checks if process exists */
    return kill(pid, 0) == 0;
#endif
}

/* Read PID from lock file */
static int ReadLockFile(void) {
    const char *path = GetLockPath();
    FILE *fp = fopen(path, "r");
    if (!fp) return 0;

    int pid = 0;
    if (fscanf(fp, "%d", &pid) != 1) {
        pid = 0;
    }
    fclose(fp);
    return pid;
}

/* Write PID to lock file */
static int WriteLockFile(int pid) {
    const char *path = GetLockPath();
    FILE *fp = fopen(path, "w");
    if (!fp) return 0;
    fprintf(fp, "%d\n", pid);
    fclose(fp);
    return 1;
}

/* Remove lock file */
static void RemoveLockFile(void) {
    const char *path = GetLockPath();
    remove(path);
}

/* Check if another instance is already running.
 * Returns 1 if lock is free (we can proceed), 0 if locked. */
static int CheckSingleton(void) {
    int pid = ReadLockFile();
    if (pid == 0) {
        /* No lock file or invalid — we're free to proceed */
        return 1;
    }

    /* Check if the process that holds the lock is still alive */
    if (IsProcessAlive(pid)) {
        fprintf(stderr, "umerospython: another instance is already running (PID %d).\n", pid);
        fprintf(stderr, "Use --force to override, or close the other instance.\n");
        return 0;
    }

    /* Stale lock — process is dead, clean it up */
    fprintf(stderr, "umerospython: removing stale lock (PID %d no longer running).\n", pid);
    RemoveLockFile();
    return 1;
}

/* Acquire the singleton lock.
 * Returns 1 on success, 0 on failure. */
static int AcquireLock(void) {
    int pid = (int)GetCurrentProcessId();

    if (!WriteLockFile(pid)) {
        fprintf(stderr, "umerospython: warning: could not create lock file.\n");
        /* Non-fatal — continue anyway */
        return 1;
    }

    lock_held = 1;
    if (verbose_mode) {
        fprintf(stderr, "[LOCK] Acquired lock (PID %d)\n", pid);
    }
    return 1;
}

/* Release the singleton lock */
static void ReleaseLock(void) {
    if (lock_held) {
        RemoveLockFile();
        lock_held = 0;
        if (verbose_mode) {
            fprintf(stderr, "[LOCK] Released lock\n");
        }
    }
}

/* atexit() handler and signal handler */
static void CleanupLock(void) {
    ReleaseLock();
    FreeHistory();
}

static void SignalHandler(int sig) {
    (void)sig;
    CleanupLock();
    exit(1);
}

/* ============================================================
 * Read entire file into string
 * ============================================================ */
static char* Umeros_ReadFile(const char *filename, Py_ssize_t *out_length) {
    FILE *fp = fopen(filename, "rb");
    if (!fp) {
        return NULL;
    }

    fseek(fp, 0, SEEK_END);
    long length = ftell(fp);
    fseek(fp, 0, SEEK_SET);

    char *buffer = (char *)malloc(length + 1);
    if (!buffer) {
        fclose(fp);
        fprintf(stderr, "MemoryError: unable to read file '%s'\n", filename);
        return NULL;
    }

    size_t nread = fread(buffer, 1, length, fp);
    buffer[nread] = '\0';
    fclose(fp);

    *out_length = (Py_ssize_t)nread;
    return buffer;
}

/* Detect and configure virtual environment.
 * Searches relative to the script dir and cwd for venv/.venv directories.
 * If found, adds <venv>/Lib/site-packages to sys.path.
 */
static int DetectVirtualEnvironment(const char *script_dir) {
    const char *search_dirs[2];
    int n_dirs = 0;

    if (script_dir && script_dir[0] != '\0') {
        search_dirs[n_dirs++] = script_dir;
    }
    search_dirs[n_dirs++] = ".";

    for (int i = 0; i < n_dirs; i++) {
        const char *base = search_dirs[i];
        const char *venv_names[] = {"venv", ".venv"};
        for (int v = 0; v < 2; v++) {
            char venv_path[4096];
            snprintf(venv_path, sizeof(venv_path), "%s/%s", base, venv_names[v]);
            struct stat st;
            if (stat(venv_path, &st) == 0 && (st.st_mode & _S_IFDIR)) {
                /* Found venv — compute site-packages path */
                char sp_path[4096];
#ifdef _WIN32
                snprintf(sp_path, sizeof(sp_path), "%s/Lib/site-packages", venv_path);
#else
                snprintf(sp_path, sizeof(sp_path), "%s/lib/python3/site-packages", venv_path);
#endif
                struct stat sp_st;
                if (stat(sp_path, &sp_st) == 0 && (sp_st.st_mode & _S_IFDIR)) {
                    if (verbose_mode) {
                        fprintf(stderr, "[VENV] Found virtual environment: %s\n", venv_path);
                        fprintf(stderr, "[VENV] Adding to sys.path: %s\n", sp_path);
                    }
                    SysModule_AddToPath(sp_path);
                    return 1;
                }
            }
        }
    }
    return 0;
}

/* Interactive REPL */
static void RunREPL(void) {
    if (!quiet_mode) {
        printf("UmerOS Python 3.x (UmerOS built-in interpreter)\n");
        printf("Type \"help\", \"copyright\", \"credits\" or \"license\" for more information.\n");
    }

    LoadHistory();

    PyObject *globals = PyDict_New();
    PyObject *builtins = PyBuiltins_GetDict();
    PyDict_SetItemString(globals, "__builtins__", builtins);
    PyObject *sys_dict = SysModule_GetDict();
    PyDict_SetItemString(globals, "sys", sys_dict);

    char line[4096];

    while (1) {
        printf(">>> ");
        fflush(stdout);

        if (!fgets(line, sizeof(line), stdin)) {
            printf("\n");
            break;
        }

        /* Remove trailing newline */
        Py_ssize_t len = strlen(line);
        while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r')) {
            line[--len] = '\0';
        }
        /* Empty line */
        if (len == 0) continue;

        AddToHistory(line);

        /* Check for exit */
        if (strcmp(line, "exit()") == 0 || strcmp(line, "quit()") == 0) {
            break;
        }

        /* Check for multi-line (incomplete statement) */
        int paren_count = 0;
        for (Py_ssize_t i = 0; i < len; i++) {
            if (line[i] == '(') paren_count++;
            else if (line[i] == ')') paren_count--;
        }
        if (paren_count > 0) {
            /* Read continuation lines */
            while (paren_count > 0) {
                printf("... ");
                fflush(stdout);

                char cont[4096];
                if (!fgets(cont, sizeof(cont), stdin)) break;

                Py_ssize_t clen = strlen(cont);
                while (clen > 0 && (cont[clen-1] == '\n' || cont[clen-1] == '\r')) {
                    cont[--clen] = '\0';
                }

                /* Append to line */
                if (len + clen + 2 < (Py_ssize_t)sizeof(line)) {
                    line[len++] = '\n';
                    memcpy(line + len, cont, clen);
                    len += clen;
                    line[len] = '\0';
                }

                for (Py_ssize_t i = 0; i < clen; i++) {
                    if (cont[i] == '(') paren_count++;
                    else if (cont[i] == ')') paren_count--;
                }
            }
        }

        /* Compile and execute */
        if (verbose_mode) {
            fprintf(stderr, "[REPL] Compiling: %s\n", line);
        }

        PyCodeObject *code = (PyCodeObject *)Py_CompileString(line, "<stdin>");
        if (code) {
            PyObject *result = PyEval_EvalCode(code, globals, globals);
            if (result) {
                if (result != Py_None) {
                    PyObject *str = PyObject_Str(result);
                    if (str) {
                        printf("%s\n", PyUnicode_AsString(str));
                        Py_DECREF(str);
                    }
                }
                Py_DECREF(result);
            } else {
                PyErr_Print();
            }
            Py_DECREF((PyObject *)code);
        } else {
            PyErr_Print();
        }
    }

    SaveHistory();
    FreeHistory();
    Py_DECREF(globals);
}

/* Execute a script file */
static int RunScript(const char *filename) {
    if (verbose_mode) {
        fprintf(stderr, "[RUN] Executing script: %s\n", filename);
    }

    Py_ssize_t length;
    char *source = Umeros_ReadFile(filename, &length);
    if (!source) {
        fprintf(stderr, "umerospython: can't open file '%s': No such file or directory\n", filename);
        return 1;
    }

    PyObject *globals = PyDict_New();
    PyObject *builtins = PyBuiltins_GetDict();
    PyDict_SetItemString(globals, "__builtins__", builtins);
    PyObject *sys_dict = SysModule_GetDict();
    PyDict_SetItemString(globals, "sys", sys_dict);

    PyDict_SetItemString(globals, "__name__",
                         PyUnicode_FromString("__main__"));

    PyDict_SetItemString(globals, "__file__",
                         PyUnicode_FromString(filename));

    if (verbose_mode) {
        fprintf(stderr, "[COMPILE] Compiling %s (%ld bytes)\n", filename, (long)length);
    }

    PyCodeObject *code = (PyCodeObject *)Py_CompileString(source, filename);
    free(source);

    if (!code) {
        PyErr_Print();
        Py_DECREF(globals);
        return 1;
    }

    if (verbose_mode) {
        fprintf(stderr, "[EXEC] Running compiled bytecode\n");
    }

    PyObject *result = PyEval_EvalCode(code, globals, globals);
    Py_DECREF((PyObject *)code);
    Py_DECREF(globals);

    if (result) {
        Py_DECREF(result);
        return 0;
    } else {
        PyErr_Print();
        return 1;
    }
}

/* Execute a code string */
static int RunString(const char *code_str) {
    PyObject *globals = PyDict_New();
    PyObject *builtins = PyBuiltins_GetDict();
    PyDict_SetItemString(globals, "__builtins__", builtins);

    /* Add sys module dict */
    PyObject *sys_dict = SysModule_GetDict();
    if (sys_dict) {
        PyDict_SetItemString(globals, "sys", sys_dict);
        Py_DECREF(sys_dict);
    }

    if (verbose_mode) {
        fprintf(stderr, "[COMPILE] Compiling string (%ld bytes)\n", (long)strlen(code_str));
    }

    PyCodeObject *code = (PyCodeObject *)Py_CompileString(code_str, "<string>");
    if (!code) {
        PyErr_Print();
        Py_DECREF(globals);
        return 1;
    }

    if (verbose_mode) {
        fprintf(stderr, "[EXEC] Running compiled bytecode\n");
    }

    PyObject *result = PyEval_EvalCode(code, globals, globals);
    Py_DECREF((PyObject *)code);
    Py_DECREF(globals);

    if (result) {
        Py_DECREF(result);
        return 0;
    } else {
        PyErr_Print();
        return 1;
    }
}

/* Run a module as __main__ (-m flag)
 * Searches sys.path for the module file, falls back to cwd.
 */
static int RunModule(const char *module_name) {
    if (verbose_mode) {
        fprintf(stderr, "[MODULE] Running module: %s\n", module_name);
    }

    /* Try to find the module as a file: module_name.py */
    char filename[4096];

    /* First check current directory */
    snprintf(filename, sizeof(filename), "%s.py", module_name);
    FILE *fp = fopen(filename, "rb");
    if (fp) {
        fclose(fp);
        if (verbose_mode) {
            fprintf(stderr, "[MODULE] Found module file in cwd: %s\n", filename);
        }
        return RunScript(filename);
    }

    /* Search sys.path */
    PyObject *path = SysModule_GetPath();
    if (path) {
        Py_ssize_t n = PyList_Size(path);
        for (Py_ssize_t i = 0; i < n; i++) {
            PyObject *item = PyList_GetItem(path, i);
            if (item && PyType_IsSubtype(Py_TYPE(item), &PyUnicode_Type)) {
                const char *dir = PyUnicode_AsString(item);
                if (dir && dir[0] != '\0') {
                    char fullpath[4096];
                    snprintf(fullpath, sizeof(fullpath), "%s/%s.py", dir, module_name);
                    fp = fopen(fullpath, "rb");
                    if (fp) {
                        fclose(fp);
                        if (verbose_mode) {
                            fprintf(stderr, "[MODULE] Found module file: %s\n", fullpath);
                        }
                        Py_DECREF(path);
                        return RunScript(fullpath);
                    }
                }
            }
        }
        Py_DECREF(path);
    }

    /* Module file not found — report error */
    fprintf(stderr, "No module named %s\n", module_name);
    return 1;
}

/* Print version info */
static void PrintVersion(void) {
    printf("UmerOS Python interpreter\n");
    printf("Version: %d.%d.%d\n", UMEROS_PYTHON_MAJOR,
           UMEROS_PYTHON_MINOR, UMEROS_PYTHON_PATCH);
    printf("Build:   %s\n", UMEROS_PYTHON_BUILD);
    printf("Compiler: %s\n", UMEROS_PYTHON_COMPILER);
}

/* Print help */
static void PrintHelp(void) {
    printf("usage: umerospython [options] [script | -c code | -m module | -]\n");
    printf("\n");
    printf("Options:\n");
    printf("  -h, --help       Show this help message and exit\n");
    printf("  -V, --version    Show version information and exit\n");
    printf("  -c code          Execute the given code string\n");
    printf("  -m module        Run module as __main__\n");
    printf("  --quiet          Suppress the REPL banner\n");
    printf("  --verbose        Verbose output (show compilation steps)\n");
    printf("  --force          Allow multiple instances (ignore singleton lock)\n");
    printf("  script           Execute the given script file\n");
    printf("  -                Read script from stdin\n");
    printf("\n");
    printf("If no arguments given, start interactive REPL.\n");
}

int main(int argc, char *argv[]) {
    /* Initialize the interpreter */
    PyErrors_Init();
    PyBool_Init();
    PyNone_Init();
    PyBuiltins_Init();
    SysModule_Init();
    DetectVirtualEnvironment(NULL);

    /* Register cleanup handlers */
    atexit(CleanupLock);
    signal(SIGINT, SignalHandler);

    /* Parse global flags first (--quiet, --verbose, --force) */
    for (int i = 1; i < argc; i++) {
        if (strcmp(argv[i], "--quiet") == 0 || strcmp(argv[i], "-q") == 0) {
            quiet_mode = 1;
        } else if (strcmp(argv[i], "--verbose") == 0 || strcmp(argv[i], "-v") == 0) {
            verbose_mode = 1;
        } else if (strcmp(argv[i], "--force") == 0) {
            force_mode = 1;
        }
    }

    /* Acquire singleton lock */
    if (!force_mode) {
        if (!CheckSingleton()) {
            return 1;
        }
        AcquireLock();
    }

    /* Parse command line arguments */
    if (argc == 1) {
        /* No arguments - interactive REPL */
        RunREPL();
        return 0;
    }

    int i = 1;
    while (i < argc) {
        const char *arg = argv[i];

        /* Skip flags already processed */
        if (strcmp(arg, "--quiet") == 0 || strcmp(arg, "-q") == 0) {
            i++;
            continue;
        }
        if (strcmp(arg, "--verbose") == 0 || strcmp(arg, "-v") == 0) {
            i++;
            continue;
        }
        if (strcmp(arg, "--force") == 0) {
            i++;
            continue;
        }

        if (strcmp(arg, "-h") == 0 || strcmp(arg, "--help") == 0) {
            PrintHelp();
            return 0;
        }

        if (strcmp(arg, "-V") == 0 || strcmp(arg, "--version") == 0) {
            PrintVersion();
            return 0;
        }

        if (strcmp(arg, "-c") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "umerospython: expected argument after -c\n");
                return 1;
            }
            return RunString(argv[++i]);
        }

        if (strcmp(arg, "-m") == 0) {
            if (i + 1 >= argc) {
                fprintf(stderr, "umerospython: expected argument after -m\n");
                return 1;
            }
            return RunModule(argv[++i]);
        }

        if (strcmp(arg, "-") == 0) {
            /* Read from stdin */
            char buffer[65536];
            Py_ssize_t total = 0;
            Py_ssize_t nread;

            while ((nread = fread(buffer + total, 1,
                                  sizeof(buffer) - total - 1, stdin)) > 0) {
                total += nread;
            }
            buffer[total] = '\0';

            return RunString(buffer);
        }

        /* Assume it's a script file */
        return RunScript(arg);
    }

    return 0;
}
