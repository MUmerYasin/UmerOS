/*
 * vm.c - UmerOS Python Virtual Machine
 *
 * Bytecode interpreter loop.
 * Executes compiled Python bytecode.
 *
 * Note: Thread state, frame alloc/free, and thread frame management
 * are defined in Objects/object.c. This file only contains the
 * VM evaluation loop and its internal helpers.
 */

#include "../Include/umeros_python.h"
#include <stdio.h>

/* External builtins registry */
extern PyObject* PyBuiltins_GetDict(void);

/* ==================== VM INTERNAL STACK ==================== */

static int Stack_Push(PyObject ***stacktop, PyObject *value) {
    Py_INCREF(value);
    *(*stacktop) = value;
    (*stacktop)++;
    return 0;
}

static PyObject* Stack_Pop(PyObject ***stacktop) {
    (*stacktop)--;
    PyObject *value = *(*stacktop);
    return value;
}

/* ==================== VM INTERNAL FRAME HELPERS ==================== */

static PyObject* VM_GetGlobal(PyFrameObject *frame, const char *name) {
    PyObject *builtins = PyDict_GetItemString(frame->f_globals, "__builtins__");
    if (builtins) {
        PyObject *value = PyDict_GetItemString(builtins, name);
        if (value) { Py_INCREF(value); return value; }
    }
    PyObject *value = PyDict_GetItemString(frame->f_globals, name);
    if (value) { Py_INCREF(value); return value; }
    PyErr_Format(PyExc_NameError, "name '%s' is not defined", name);
    return NULL;
}

static int VM_SetGlobal(PyFrameObject *frame, const char *name, PyObject *value) {
    return PyDict_SetItemString(frame->f_globals, name, value);
}

static const char* VM_AsString(PyObject *obj) {
    if (!PyUnicode_Check(obj)) return NULL;
    return PyUnicode_AsString(obj);
}

/* ==================== MAIN EVALUATION LOOP ==================== */

PyObject* PyEval_EvalFrame(PyFrameObject *frame) {
    if (!frame || !frame->f_code || !frame->f_code->code) {
        PyErr_SetString(PyExc_SystemError, "no code to execute");
        return NULL;
    }

    fprintf(stderr, "[VM] ENTRY: frame=%p code=%p\n", (void*)frame, (void*)frame->f_code);
    fflush(stderr);

    uint8_t *bytecode = frame->f_code->code;
    Py_ssize_t code_len = frame->f_code->code_size;
    PyObject **consts = frame->f_code->consts;
    Py_ssize_t n_consts = frame->f_code->n_consts;
    PyObject ***stack = &frame->f_stacktop;

    fprintf(stderr, "[VM] stack=%p stacktop=%p\n", (void*)stack, (void*)frame->f_stacktop);
    fflush(stderr);

    frame->f_lasti = 0;

    /* DEBUG: dump bytecode */
    fprintf(stderr, "\n");
    for (Py_ssize_t i = 0; i < n_consts; i++) {
        if (consts[i] == Py_None) fprintf(stderr, "None");
        else fprintf(stderr, "<object>");
        fprintf(stderr, "\n");
    }

    while (frame->f_lasti < code_len) {
        Py_ssize_t instr_off = frame->f_lasti;
        Opcode op = (Opcode)bytecode[frame->f_lasti++];
        int arg = -1;

        /* Always read argument byte — our compiler emits 2 bytes per instruction */
        if (frame->f_lasti < code_len) {
            arg = bytecode[frame->f_lasti++];
            if (arg > 255 && frame->f_lasti < code_len) {
                arg = (arg << 8) | bytecode[frame->f_lasti++];
            }
        }



        fprintf(stderr, "[VM] op=%d arg=%d stacktop=%p\n", op, arg, (void*)*stack);
        fflush(stderr);

        switch (op) {
            case OP_LOAD_CONST: {
                if (arg < 0 || arg >= n_consts) {
                    PyErr_SetString(PyExc_IndexError, "LOAD_CONST: bad constant index");
                    return NULL;
                }
                PyObject *value = consts[arg];
                Py_INCREF(value);
                Stack_Push(stack, value);
                break;
            }

            case OP_POP_TOP: {
                PyObject *value = Stack_Pop(stack);
                Py_DECREF(value);
                break;
            }

            case OP_LOAD_NAME: {
                if (arg < 0 || arg >= n_consts) {
                    PyErr_SetString(PyExc_IndexError, "LOAD_NAME: bad name index");
                    return NULL;
                }
                const char *name = VM_AsString(consts[arg]);
                if (!name) {
                    PyErr_SetString(PyExc_SystemError, "LOAD_NAME: name is not a string");
                    return NULL;
                }
                PyObject *value = VM_GetGlobal(frame, name);
                if (value == NULL) {
                    if (PyErr_ExceptionMatches(PyExc_NameError)) {
                        PyErr_Clear();
                        Py_INCREF(Py_None);
                        Stack_Push(stack, Py_None);
                    } else {
                        return NULL;
                    }
                } else {
                    Stack_Push(stack, value);
                    Py_DECREF(value);
                }
                break;
            }

            case OP_STORE_NAME: {
                if (arg < 0 || arg >= n_consts) {
                    PyErr_SetString(PyExc_IndexError, "STORE_NAME: bad name index");
                    return NULL;
                }
                const char *name = VM_AsString(consts[arg]);
                if (!name) {
                    PyErr_SetString(PyExc_SystemError, "STORE_NAME: name is not a string");
                    return NULL;
                }
                PyObject *value = Stack_Pop(stack);
                VM_SetGlobal(frame, name, value);
                Py_DECREF(value);
                break;
            }

            case OP_LOAD_GLOBAL: {
                if (arg < 0 || arg >= n_consts) {
                    PyErr_SetString(PyExc_IndexError, "LOAD_GLOBAL: bad name index");
                    return NULL;
                }
                const char *name = VM_AsString(consts[arg]);
                if (!name) {
                    PyErr_SetString(PyExc_SystemError, "LOAD_GLOBAL: name is not a string");
                    return NULL;
                }
                fprintf(stderr, "[VM] LOAD_GLOBAL name='%s'\n", name);
                fflush(stderr);
                PyObject *value = VM_GetGlobal(frame, name);
                if (value == NULL) {
                    fprintf(stderr, "[VM] LOAD_GLOBAL: VM_GetGlobal returned NULL\n");
                    fflush(stderr);
                    if (PyErr_ExceptionMatches(PyExc_NameError)) {
                        PyErr_Clear();
                        Py_INCREF(Py_None);
                        Stack_Push(stack, Py_None);
                    } else {
                        return NULL;
                    }
                } else {
                    fprintf(stderr, "[VM] LOAD_GLOBAL: found value=%p type=%p\n", (void*)value, (void*)Py_TYPE(value));
                    fflush(stderr);
                    Stack_Push(stack, value);
                    Py_DECREF(value);
                }
                break;
            }

            case OP_STORE_GLOBAL: {
                if (arg < 0 || arg >= n_consts) {
                    PyErr_SetString(PyExc_IndexError, "STORE_GLOBAL: bad name index");
                    return NULL;
                }
                const char *name = VM_AsString(consts[arg]);
                if (!name) {
                    PyErr_SetString(PyExc_SystemError, "STORE_GLOBAL: name is not a string");
                    return NULL;
                }
                PyObject *value = Stack_Pop(stack);
                VM_SetGlobal(frame, name, value);
                Py_DECREF(value);
                break;
            }

            case OP_CALL_FUNCTION: {
                fprintf(stderr, "[VM] CALL_FUNCTION nargs=%d\n", arg);
                fflush(stderr);
                if (arg < 0) {
                    PyErr_SetString(PyExc_SystemError, "CALL_FUNCTION: bad argument");
                    return NULL;
                }
                PyObject *args = PyList_New(arg);
                if (!args) { fprintf(stderr, "[VM] CALL_FUNCTION: PyList_New failed\n"); fflush(stderr); return NULL; }
                for (int i = arg - 1; i >= 0; i--) {
                    PyObject *item = Stack_Pop(stack);
                    PyList_SetItem(args, i, item);
                }
                PyObject *callable = Stack_Pop(stack);
                fprintf(stderr, "[VM] CALL_FUNCTION: callable=%p type=%p\n", (void*)callable, callable ? (void*)Py_TYPE(callable) : NULL);
                fflush(stderr);
                PyObject *result = PyObject_Call(callable, args, NULL);
                fprintf(stderr, "[VM] CALL_FUNCTION: result=%p\n", (void*)result);
                fflush(stderr);
                Py_DECREF(args);
                Py_DECREF(callable);
                if (!result) return NULL;
                Stack_Push(stack, result);
                Py_DECREF(result);
                break;
            }

            case OP_RETURN_VALUE: {
                PyObject *retval = Stack_Pop(stack);
                return retval;
            }

            case OP_BINARY_ADD: {
                PyObject *right = Stack_Pop(stack);
                PyObject *left = Stack_Pop(stack);
                PyObject *result = PyNumber_Add(left, right);
                Py_DECREF(left); Py_DECREF(right);
                if (!result) return NULL;
                Stack_Push(stack, result); Py_DECREF(result);
                break;
            }

            case OP_BINARY_SUBTRACT: {
                PyObject *right = Stack_Pop(stack);
                PyObject *left = Stack_Pop(stack);
                PyObject *result = PyNumber_Subtract(left, right);
                Py_DECREF(left); Py_DECREF(right);
                if (!result) return NULL;
                Stack_Push(stack, result); Py_DECREF(result);
                break;
            }

            case OP_BINARY_MULTIPLY: {
                PyObject *right = Stack_Pop(stack);
                PyObject *left = Stack_Pop(stack);
                PyObject *result = PyNumber_Multiply(left, right);
                Py_DECREF(left); Py_DECREF(right);
                if (!result) return NULL;
                Stack_Push(stack, result); Py_DECREF(result);
                break;
            }

            case OP_BINARY_TRUE_DIVIDE: {
                PyObject *right = Stack_Pop(stack);
                PyObject *left = Stack_Pop(stack);
                PyObject *result = PyNumber_TrueDivide(left, right);
                Py_DECREF(left); Py_DECREF(right);
                if (!result) return NULL;
                Stack_Push(stack, result); Py_DECREF(result);
                break;
            }

            case OP_BINARY_FLOOR_DIVIDE: {
                PyObject *right = Stack_Pop(stack);
                PyObject *left = Stack_Pop(stack);
                PyObject *result = PyNumber_FloorDivide(left, right);
                Py_DECREF(left); Py_DECREF(right);
                if (!result) return NULL;
                Stack_Push(stack, result); Py_DECREF(result);
                break;
            }

            case OP_BINARY_MODULO: {
                PyObject *right = Stack_Pop(stack);
                PyObject *left = Stack_Pop(stack);
                PyObject *result = PyNumber_Remainder(left, right);
                Py_DECREF(left); Py_DECREF(right);
                if (!result) return NULL;
                Stack_Push(stack, result); Py_DECREF(result);
                break;
            }

            case OP_BINARY_POWER: {
                PyObject *right = Stack_Pop(stack);
                PyObject *left = Stack_Pop(stack);
                PyObject *result = PyNumber_Power(left, right);
                Py_DECREF(left); Py_DECREF(right);
                if (!result) return NULL;
                Stack_Push(stack, result); Py_DECREF(result);
                break;
            }

            case OP_COMPARE_OP: {
                PyObject *right = Stack_Pop(stack);
                PyObject *left = Stack_Pop(stack);
                PyObject *result = NULL;
                int cmp = PyObject_Compare(left, right);
                switch (arg) {
                    case 0: result = PyBool_FromLong(cmp < 0); break;
                    case 1: result = PyBool_FromLong(cmp <= 0); break;
                    case 2: result = PyBool_FromLong(cmp == 0); break;
                    case 3: result = PyBool_FromLong(cmp != 0); break;
                    case 4: result = PyBool_FromLong(cmp > 0); break;
                    case 5: result = PyBool_FromLong(cmp >= 0); break;
                }
                Py_DECREF(left); Py_DECREF(right);
                if (!result) return NULL;
                Stack_Push(stack, result); Py_DECREF(result);
                break;
            }

            case OP_JUMP_IF_FALSE: {
                PyObject *cond = Stack_Pop(stack);
                int is_true = PyObject_IsTrue(cond);
                Py_DECREF(cond);
                if (is_true == 0 && arg >= 0) {
                    frame->f_lasti = arg;
                } else if (is_true < 0) {
                    return NULL;
                }
                break;
            }

            case OP_JUMP_IF_TRUE: {
                PyObject *cond = Stack_Pop(stack);
                int is_true = PyObject_IsTrue(cond);
                Py_DECREF(cond);
                if (is_true == 1 && arg >= 0) {
                    frame->f_lasti = arg;
                } else if (is_true < 0) {
                    return NULL;
                }
                break;
            }

            case OP_JUMP: {
                if (arg >= 0) {
                    frame->f_lasti = arg;
                }
                break;
            }

            case OP_NOP:
                break;

            default:
                PyErr_Format(PyExc_SystemError,
                    "unexpected opcode: %d at position %d",
                    (int)op, (int)(frame->f_lasti - 1));
                return NULL;
        }
    }

    Py_INCREF(Py_None);
    return Py_None;
}

/* Execute a code object */
PyObject* PyEval_EvalCode(PyCodeObject *code, PyObject *globals, PyObject *locals) {

    if (!globals) {
        globals = PyDict_New();
        if (globals) {
            PyObject *builtins = PyBuiltins_GetDict();
            if (builtins) {
                PyDict_SetItemString(globals, "__builtins__", builtins);
                Py_DECREF(builtins);
            }
        }
    }
    if (!locals) {
        Py_INCREF(globals);
        locals = globals;
    } else {
        Py_INCREF(locals);
    }

    PyFrameObject *frame = PyFrame_New(code, globals, locals);
    if (!frame) {
        Py_DECREF(locals);
        return NULL;
    }

    PyThreadState *tstate = PyThreadState_Get();
    PyThreadState_PushFrame(tstate, frame);

    PyObject *result = PyEval_EvalFrame(frame);

    PyThreadState_PopFrame(tstate);
    Py_DECREF(locals);
    PyFrame_Free(frame);

    return result;
}
