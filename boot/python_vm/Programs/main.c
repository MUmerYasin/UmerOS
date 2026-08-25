/*
 * main.c - UmerOS Python Interpreter Entry Point
 *
 * Reads Python source code from file or stdin,
 * compiles to bytecode, and executes.
 *
 * Usage:
 *   umerospython                  # Interactive REPL
 *   umerospython script.py        # Execute script file
 *   umerospython -c "code"        # Execute code string
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
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

/* Read entire file into string */
static char* ReadFile(const char *filename, Py_ssize_t *out_length) {
    FILE *fp = fopen(filename, "rb");
    if (!fp) {
        fprintf(stderr, "FileNotFoundError: [Errno 2] No such file or directory: '%s'\n", filename);
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

/* Interactive REPL */
static void RunREPL(void) {
    printf("UmerOS Python 3.x (UmerOS built-in interpreter)\n");
    printf("Type \"help\", \"copyright\", \"credits\" or \"license\" for more information.\n");

    PyObject *globals = PyDict_New();
    PyObject *builtins = PyBuiltins_GetDict();
    PyDict_SetItemString(globals, "__builtins__", builtins);

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

    Py_DECREF(globals);
}

/* Execute a script file */
static int RunScript(const char *filename) {
    fprintf(stderr, "[DBG] RunScript entered, filename='%s'\n", filename);
    fflush(stderr);

    Py_ssize_t length;
    char *source = ReadFile(filename, &length);
    if (!source) {
        fprintf(stderr, "[DBG] RunScript: ReadFile returned NULL\n");
        fflush(stderr);
        return 1;
    }
    fprintf(stderr, "[DBG] RunScript: file read OK, length=%d\n", (int)length);
    fflush(stderr);

    fprintf(stderr, "[DBG] RunScript: creating globals dict\n");
    fflush(stderr);
    PyObject *globals = PyDict_New();
    fprintf(stderr, "[DBG] RunScript: getting builtins dict\n");
    fflush(stderr);
    PyObject *builtins = PyBuiltins_GetDict();
    fprintf(stderr, "[DBG] RunScript: setting __builtins__\n");
    fflush(stderr);
    PyDict_SetItemString(globals, "__builtins__", builtins);

    fprintf(stderr, "[DBG] RunScript: setting __name__\n");
    fflush(stderr);
    PyDict_SetItemString(globals, "__name__",
                         PyUnicode_FromString("__main__"));

    fprintf(stderr, "[DBG] RunScript: setting __file__\n");
    fflush(stderr);
    PyDict_SetItemString(globals, "__file__",
                         PyUnicode_FromString(filename));

    fprintf(stderr, "[DBG] RunScript: calling Py_CompileString\n");
    fflush(stderr);
    PyCodeObject *code = (PyCodeObject *)Py_CompileString(source, filename);
    free(source);
    fprintf(stderr, "[DBG] RunScript: Py_CompileString returned %p\n", (void*)code);
    fflush(stderr);

    if (!code) {
        fprintf(stderr, "[DBG] RunScript: compile failed, printing error\n");
        fflush(stderr);
        PyErr_Print();
        Py_DECREF(globals);
        return 1;
    }

    fprintf(stderr, "[DBG] RunScript: bytecode=%p, code_size=%d, n_consts=%d\n",
            (void*)code->code, (int)code->code_size, code->n_consts);
    fflush(stderr);

    fprintf(stderr, "[DBG] RunScript: calling PyEval_EvalCode\n");
    fflush(stderr);
    PyObject *result = PyEval_EvalCode(code, globals, globals);
    fprintf(stderr, "[DBG] RunScript: PyEval_EvalCode returned %p\n", (void*)result);
    fflush(stderr);
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

    PyCodeObject *code = (PyCodeObject *)Py_CompileString(code_str, "<string>");
    if (!code) {
        PyErr_Print();
        Py_DECREF(globals);
        return 1;
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
    printf("usage: umerospython [options] [script | -c code | -]\n");
    printf("\n");
    printf("Options:\n");
    printf("  -h, --help       Show this help message and exit\n");
    printf("  -V, --version    Show version information and exit\n");
    printf("  -c code          Execute the given code string\n");
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

    /* Parse command line arguments */
    if (argc == 1) {
        /* No arguments - interactive REPL */
        RunREPL();
        return 0;
    }

    int i = 1;
    while (i < argc) {
        const char *arg = argv[i];

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
