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
extern void Compiler_Test(void);

/* Read entire file into string */
static char* ReadFile(const char *filename, Py_ssize_t *out_length) {
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

/* Interactive REPL */
static void RunREPL(void) {
    printf("UmerOS Python 3.x (UmerOS built-in interpreter)\n");
    printf("Type \"help\", \"copyright\", \"credits\" or \"license\" for more information.\n");

    fprintf(stderr, "[REPL] creating globals dict\n"); fflush(stderr);
    PyObject *globals = PyDict_New();
    fprintf(stderr, "[REPL] getting builtins dict\n"); fflush(stderr);
    PyObject *builtins = PyBuiltins_GetDict();
    fprintf(stderr, "[REPL] setting __builtins__ in globals\n"); fflush(stderr);
    PyDict_SetItemString(globals, "__builtins__", builtins);
    fprintf(stderr, "[REPL] globals setup complete\n"); fflush(stderr);

    char line[4096];

    while (1) {
        printf(">>> ");
        fflush(stdout);

        fprintf(stderr, "[REPL] waiting for fgets\n"); fflush(stderr);
        if (!fgets(line, sizeof(line), stdin)) {
            fprintf(stderr, "[REPL] fgets returned NULL\n"); fflush(stderr);
            printf("\n");
            break;
        }
        fprintf(stderr, "[REPL] got line: '%s'\n", line); fflush(stderr);

        /* Remove trailing newline */
        Py_ssize_t len = strlen(line);
        while (len > 0 && (line[len-1] == '\n' || line[len-1] == '\r')) {
            line[--len] = '\0';
        }
        fprintf(stderr, "[REPL] stripped newline, len=%d\n", (int)len); fflush(stderr);

        /* Empty line */
        if (len == 0) { fprintf(stderr, "[REPL] empty line, continue\n"); fflush(stderr); continue; }

        /* Check for exit */
        if (strcmp(line, "exit()") == 0 || strcmp(line, "quit()") == 0) {
            fprintf(stderr, "[REPL] exit/quit detected\n"); fflush(stderr);
            break;
        }

        /* Check for multi-line (incomplete statement) */
        int paren_count = 0;
        for (Py_ssize_t i = 0; i < len; i++) {
            if (line[i] == '(') paren_count++;
            else if (line[i] == ')') paren_count--;
        }
        fprintf(stderr, "[REPL] paren_count=%d\n", paren_count); fflush(stderr);

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
        fprintf(stderr, "[REPL] calling Py_CompileString\n"); fflush(stderr);
        PyCodeObject *code = (PyCodeObject *)Py_CompileString(line, "<stdin>");
        fprintf(stderr, "[REPL] Py_CompileString returned %p\n", (void*)code); fflush(stderr);
        if (code) {
            fprintf(stderr, "[REPL] calling PyEval_EvalCode\n"); fflush(stderr);
            PyObject *result = PyEval_EvalCode(code, globals, globals);
            fprintf(stderr, "[REPL] PyEval_EvalCode returned %p\n", (void*)result); fflush(stderr);
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

    Py_ssize_t length;
    char *source = ReadFile(filename, &length);
    if (!source) {
        return 1;
    }

    PyObject *globals = PyDict_New();
    PyObject *builtins = PyBuiltins_GetDict();
    PyDict_SetItemString(globals, "__builtins__", builtins);

    PyDict_SetItemString(globals, "__name__",
                         PyUnicode_FromString("__main__"));

    PyDict_SetItemString(globals, "__file__",
                         PyUnicode_FromString(filename));

    PyCodeObject *code = (PyCodeObject *)Py_CompileString(source, filename);
    free(source);

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
    fprintf(stderr, "[MAIN] main() enter, argc=%d\n", argc);
    fflush(stderr);
    /* Initialize the interpreter */
    fprintf(stderr, "[MAIN] calling PyErrors_Init\n"); fflush(stderr);
    PyErrors_Init();
    fprintf(stderr, "[MAIN] calling PyBool_Init\n"); fflush(stderr);
    PyBool_Init();
    fprintf(stderr, "[MAIN] calling PyNone_Init\n"); fflush(stderr);
    PyNone_Init();
    fprintf(stderr, "[MAIN] calling PyBuiltins_Init\n"); fflush(stderr);
    PyBuiltins_Init();
    fprintf(stderr, "[MAIN] init complete\n"); fflush(stderr);

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
