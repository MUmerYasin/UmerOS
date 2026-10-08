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

static int Stack_Push(PyFrameObject *frame, PyObject *value) {
    if (frame->f_stacktop - frame->f_stackbase >= MAX_VALUE_STACK) {
        PyErr_SetString(PyExc_SystemError, "value stack overflow");
        return -1;
    }
    Py_INCREF(value);
    *frame->f_stacktop = value;
    frame->f_stacktop++;
    return 0;
}

static PyObject* Stack_Pop(PyFrameObject *frame) {
    if (frame->f_stacktop <= frame->f_stackbase) {
        PyErr_SetString(PyExc_SystemError, "value stack underflow");
        return NULL;
    }
    frame->f_stacktop--;
    return *frame->f_stacktop;
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

    frame->f_lasti = 0;

    while (frame->f_lasti < code_len) {
        Opcode op = (Opcode)bytecode[frame->f_lasti++];
        int arg = -1;

        /* Every instruction carries a 2-byte argument (big-endian),
         * matching Compiler_Emit. Read both bytes unconditionally:
         * a variable-length argument would desync the stream. */
        if (frame->f_lasti + 1 >= code_len) {
            PyErr_SetString(PyExc_SystemError, "truncated instruction");
            return NULL;
        }
        arg = (int)bytecode[frame->f_lasti] << 8;
        arg |= (int)bytecode[frame->f_lasti + 1];
        frame->f_lasti += 2;

        switch (op) {
            case OP_LOAD_CONST: {
                if (arg < 0 || arg >= n_consts) {
                    PyErr_SetString(PyExc_IndexError, "LOAD_CONST: bad constant index");
                    return NULL;
                }
                PyObject *value = consts[arg];
                if (Stack_Push(frame, value) < 0) return NULL;
                break;
            }

            case OP_POP_TOP: {
                PyObject *value = Stack_Pop(frame);
                if (!value) return NULL;
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
                        if (Stack_Push(frame, Py_None) < 0) return NULL;
                    } else {
                        return NULL;
                    }
                } else {
                    if (Stack_Push(frame, value) < 0) {
                        Py_DECREF(value);
                        return NULL;
                    }
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
                PyObject *value = Stack_Pop(frame);
                if (!value) return NULL;
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
                        if (Stack_Push(frame, Py_None) < 0) return NULL;
                    } else {
                        return NULL;
                    }
                } else {
                    if (Stack_Push(frame, value) < 0) {
                        Py_DECREF(value);
                        return NULL;
                    }
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
                PyObject *value = Stack_Pop(frame);
                if (!value) return NULL;
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
                    PyObject *item = Stack_Pop(frame);
                    if (!item) {
                        Py_DECREF(args);
                        return NULL;
                    }
                    PyList_SetItem(args, i, item);
                }
                PyObject *callable = Stack_Pop(frame);
                if (!callable) {
                    Py_DECREF(args);
                    return NULL;
                }
                PyObject *result = PyObject_Call(callable, args, NULL);
                Py_DECREF(args);
                Py_DECREF(callable);
                if (!result) return NULL;
                if (Stack_Push(frame, result) < 0) {
                    Py_DECREF(result);
                    return NULL;
                }
                Py_DECREF(result);
                break;
            }

            case OP_IMPORT_NAME: {
                if (arg < 0 || arg >= n_consts) {
                    PyErr_SetString(PyExc_IndexError, "IMPORT_NAME: bad module index");
                    return NULL;
                }
                const char *name_str = VM_AsString(consts[arg]);
                if (!name_str) {
                    PyErr_SetString(PyExc_SystemError,
                                    "IMPORT_NAME: module name is not a string");
                    return NULL;
                }
                PyObject *modname = PyUnicode_FromString(name_str);
                if (!modname) return NULL;

                PyObject *builtins_dict = PyBuiltins_GetDict();
                PyObject *import_fn = builtins_dict ?
                    PyDict_GetItemString(builtins_dict, "__import__") : NULL;
                PyObject *mod = NULL;
                if (import_fn) {
                    PyObject *args = PyTuple_New(1);
                    if (args) {
                        PyTuple_SetItem(args, 0, modname);
                        mod = PyObject_Call(import_fn, args, NULL);
                        Py_DECREF(args);
                    }
                }
                if (builtins_dict) Py_DECREF(builtins_dict);
                Py_DECREF(modname);

                if (!mod) {
                    if (!PyErr_Occurred()) {
                        PyErr_Format(PyExc_ImportError,
                                     "cannot import module '%s'", name_str);
                    }
                    return NULL;
                }
                if (Stack_Push(frame, mod) < 0) {
                    Py_DECREF(mod);
                    return NULL;
                }
                Py_DECREF(mod);
                break;
            }

            case OP_IMPORT_FROM: {
                if (arg < 0 || arg >= n_consts) {
                    PyErr_SetString(PyExc_IndexError, "IMPORT_FROM: bad name index");
                    return NULL;
                }
                const char *attr_str = VM_AsString(consts[arg]);
                if (!attr_str) {
                    PyErr_SetString(PyExc_SystemError,
                                    "IMPORT_FROM: name is not a string");
                    return NULL;
                }
                PyObject *module = Stack_Pop(frame);
                if (!module) return NULL;

                /* PyImport_ImportModule returns a plain dict as the
                 * module namespace; PyModule_GetDict returns a new ref. */
                PyObject *mdict = NULL;
                if (PyModule_Check(module)) {
                    mdict = PyModule_GetDict(module);
                } else if (PyDict_Check(module)) {
                    Py_INCREF(module);
                    mdict = module;
                }

                PyObject *value = NULL;
                if (mdict) {
                    value = PyDict_GetItemString(mdict, attr_str);
                    if (value) Py_INCREF(value);
                    Py_DECREF(mdict);
                }

                if (Stack_Push(frame, module) < 0) {
                    Py_DECREF(module);
                    Py_XDECREF(value);
                    return NULL;
                }
                Py_DECREF(module);

                if (!value) {
                    PyErr_Format(PyExc_ImportError,
                                 "cannot import name '%s'", attr_str);
                    return NULL;
                }
                if (Stack_Push(frame, value) < 0) {
                    Py_DECREF(value);
                    return NULL;
                }
                Py_DECREF(value);
                break;
            }

            case OP_IMPORT_STAR: {
                PyObject *module = Stack_Pop(frame);
                if (!module) return NULL;
                PyObject *mdict = NULL;
                if (PyModule_Check(module)) {
                    mdict = PyModule_GetDict(module);
                } else if (PyDict_Check(module)) {
                    Py_INCREF(module);
                    mdict = module;
                }
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
                PyObject *retval = Stack_Pop(frame);
                return retval;
            }

            case OP_BINARY_ADD: {
                PyObject *right = Stack_Pop(frame);
                if (!right) return NULL;
                PyObject *left = Stack_Pop(frame);
                if (!left) {
                    Py_DECREF(right);
                    return NULL;
                }
                PyObject *result = PyNumber_Add(left, right);
                Py_DECREF(left); Py_DECREF(right);
                if (!result) return NULL;
                if (Stack_Push(frame, result) < 0) {
                    Py_DECREF(result);
                    return NULL;
                }
                Py_DECREF(result);
                break;
            }

            case OP_BINARY_SUBTRACT: {
                PyObject *right = Stack_Pop(frame);
                if (!right) return NULL;
                PyObject *left = Stack_Pop(frame);
                if (!left) {
                    Py_DECREF(right);
                    return NULL;
                }
                PyObject *result = PyNumber_Subtract(left, right);
                Py_DECREF(left); Py_DECREF(right);
                if (!result) return NULL;
                if (Stack_Push(frame, result) < 0) {
                    Py_DECREF(result);
                    return NULL;
                }
                Py_DECREF(result);
                break;
            }

            case OP_BINARY_MULTIPLY: {
                PyObject *right = Stack_Pop(frame);
                if (!right) return NULL;
                PyObject *left = Stack_Pop(frame);
                if (!left) {
                    Py_DECREF(right);
                    return NULL;
                }
                PyObject *result = PyNumber_Multiply(left, right);
                Py_DECREF(left); Py_DECREF(right);
                if (!result) return NULL;
                if (Stack_Push(frame, result) < 0) {
                    Py_DECREF(result);
                    return NULL;
                }
                Py_DECREF(result);
                break;
            }

            case OP_BINARY_TRUE_DIVIDE: {
                PyObject *right = Stack_Pop(frame);
                if (!right) return NULL;
                PyObject *left = Stack_Pop(frame);
                if (!left) {
                    Py_DECREF(right);
                    return NULL;
                }
                PyObject *result = PyNumber_TrueDivide(left, right);
                Py_DECREF(left); Py_DECREF(right);
                if (!result) return NULL;
                if (Stack_Push(frame, result) < 0) {
                    Py_DECREF(result);
                    return NULL;
                }
                Py_DECREF(result);
                break;
            }

            case OP_BINARY_FLOOR_DIVIDE: {
                PyObject *right = Stack_Pop(frame);
                if (!right) return NULL;
                PyObject *left = Stack_Pop(frame);
                if (!left) {
                    Py_DECREF(right);
                    return NULL;
                }
                PyObject *result = PyNumber_FloorDivide(left, right);
                Py_DECREF(left); Py_DECREF(right);
                if (!result) return NULL;
                if (Stack_Push(frame, result) < 0) {
                    Py_DECREF(result);
                    return NULL;
                }
                Py_DECREF(result);
                break;
            }

            case OP_BINARY_MODULO: {
                PyObject *right = Stack_Pop(frame);
                if (!right) return NULL;
                PyObject *left = Stack_Pop(frame);
                if (!left) {
                    Py_DECREF(right);
                    return NULL;
                }
                PyObject *result = PyNumber_Remainder(left, right);
                Py_DECREF(left); Py_DECREF(right);
                if (!result) return NULL;
                if (Stack_Push(frame, result) < 0) {
                    Py_DECREF(result);
                    return NULL;
                }
                Py_DECREF(result);
                break;
            }

            case OP_BINARY_POWER: {
                PyObject *right = Stack_Pop(frame);
                if (!right) return NULL;
                PyObject *left = Stack_Pop(frame);
                if (!left) {
                    Py_DECREF(right);
                    return NULL;
                }
                PyObject *result = PyNumber_Power(left, right);
                Py_DECREF(left); Py_DECREF(right);
                if (!result) return NULL;
                if (Stack_Push(frame, result) < 0) {
                    Py_DECREF(result);
                    return NULL;
                }
                Py_DECREF(result);
                break;
            }

            case OP_COMPARE_OP: {
                PyObject *right = Stack_Pop(frame);
                if (!right) return NULL;
                PyObject *left = Stack_Pop(frame);
                if (!left) {
                    Py_DECREF(right);
                    return NULL;
                }
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
                if (Stack_Push(frame, result) < 0) {
                    Py_DECREF(result);
                    return NULL;
                }
                Py_DECREF(result);
                break;
            }

            case OP_JUMP_IF_FALSE: {
                PyObject *cond = Stack_Pop(frame);
                if (!cond) return NULL;
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
                PyObject *cond = Stack_Pop(frame);
                if (!cond) return NULL;
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
