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

    uint8_t *bytecode = frame->f_code->code;
    Py_ssize_t code_len = frame->f_code->code_size;
    PyObject **consts = frame->f_code->consts;
    Py_ssize_t n_consts = frame->f_code->n_consts;
    PyObject ***stack = &frame->f_stacktop;

    frame->f_lasti = 0;

    while (frame->f_lasti < code_len) {
        Opcode op = (Opcode)bytecode[frame->f_lasti++];
        int arg = -1;

        /* Always read argument byte — our compiler emits 2 bytes per instruction */
        if (frame->f_lasti < code_len) {
            arg = bytecode[frame->f_lasti++];
            if (arg > 255 && frame->f_lasti < code_len) {
                arg = (arg << 8) | bytecode[frame->f_lasti++];
            }
        }

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
                if (arg < 0) {
                    PyErr_SetString(PyExc_SystemError, "CALL_FUNCTION: bad argument");
                    return NULL;
                }
                PyObject *args = PyList_New(arg);
                if (!args) { return NULL; }
                for (int i = arg - 1; i >= 0; i--) {
                    PyObject *item = Stack_Pop(stack);
                    PyList_SetItem(args, i, item);
                }
                PyObject *callable = Stack_Pop(stack);
                PyObject *result = PyObject_Call(callable, args, NULL);
                Py_DECREF(args);
                Py_DECREF(callable);
                if (!result) return NULL;
                Stack_Push(stack, result);
                Py_DECREF(result);
                break;
            }

            case OP_IMPORT_NAME: {
                int names_idx = arg;
                PyObject *modname = GET_NAME(frame, names_idx);
                PyObject *mod = NULL;
                PyObject *globals = frame->f_globals;
                PyObject *locals = frame->f_locals;
                PyObject *builtins_dict = PyBuiltins_GetDict();
                if (builtins_dict) {
                    PyObject *import_fn = PyDict_GetItem(builtins_dict, PyUnicode_FromString("__import__"));
                    if (import_fn) {
                        PyObject *args = PyTuple_New(1);
                        PyTuple_SET_ITEM(args, 0, modname);
                        Py_INCREF(modname);
                        mod = PyObject_Call(import_fn, args, NULL);
                        Py_DECREF(args);
                    }
                    Py_DECREF(builtins_dict);
                }
                if (!mod) {
                    PyErr_Format(PyExc_ImportError, "cannot import module");
                    return NULL;
                }
                Stack_Push(stack, mod);
                Py_DECREF(mod);
                break;
            }

            case OP_IMPORT_FROM: {
                int names_idx = arg;
                PyObject *attr_name = GET_NAME(frame, names_idx);
                PyObject *module = Stack_Pop(stack);
                PyObject *value = NULL;
                if (PyModule_Check(module)) {
                    PyObject *mdict = PyModule_GetDict(module);
                    if (mdict) {
                        value = PyDict_GetItem(mdict, attr_name);
                        if (value) {
                            Py_INCREF(value);
                        }
                        Py_DECREF(mdict);
                    }
                }
                Stack_Push(stack, module);
                if (!value) {
                    PyErr_Format(PyExc_ImportError, "cannot import name %U", attr_name);
                    Py_DECREF(module);
                    return NULL;
                }
                Stack_Push(stack, value);
                Py_DECREF(value);
                Py_DECREF(module);
                Py_DECREF(attr_name);
                break;
            }

            case OP_IMPORT_STAR: {
                PyObject *module = Stack_Pop(stack);
                PyObject *mdict = PyModule_Check(module) ? PyModule_GetDict(module) : NULL;
                if (mdict) {
                    PyObject *keys = PyDict_Keys(mdict);
                    if (keys) {
                        Py_ssize_t len = PyList_GET_SIZE(keys);
                        for (Py_ssize_t i = 0; i < len; i++) {
                            PyObject *key = PyList_GET_ITEM(keys, i);
                            PyObject *val = PyDict_GetItem(mdict, key);
                            if (val && PyUnicode_Check(key)) {
                                const char *key_str = PyUnicode_AsUTF8(key);
                                if (key_str && key_str[0] != '_') {
                                    Py_INCREF(val);
                                    VM_SetGlobal(frame, key_str, val);
                                    Py_DECREF(val);
                                }
                            }
                        }
                        Py_DECREF(keys);
                    }
                    Py_DECREF(mdict);
                }
                Py_DECREF(module);
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
