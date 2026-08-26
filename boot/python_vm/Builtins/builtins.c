/*
 * builtins.c - UmerOS Python Built-in Functions
 *
 * Implements print(), len(), type(), int(), float(), str(), bool().
 */

#include "../Include/umeros_python.h"
#include <stdio.h>
#include <stdlib.h>

/* print() implementation */
static PyObject* builtin_print(PyObject *self, PyObject *args, PyObject *kwargs) {
    (void)self;
    (void)kwargs;

    Py_ssize_t nargs = args ? PyList_Size(args) : 0;
    const char *sep = " ";
    const char *end = "\n";

    /* Parse keyword arguments */
    if (kwargs) {
        PyObject *sep_key = PyUnicode_FromString("sep");
        PyObject *end_key = PyUnicode_FromString("end");
        PyObject *sep_val = PyDict_GetItem(kwargs, sep_key);
        PyObject *end_val = PyDict_GetItem(kwargs, end_key);
        if (sep_val && PyUnicode_Check(sep_val)) {
            sep = PyUnicode_AsString(sep_val);
        }
        if (end_val && PyUnicode_Check(end_val)) {
            end = PyUnicode_AsString(end_val);
        }
        Py_DECREF(sep_key);
        Py_DECREF(end_key);
    }

    /* Print each argument */
    for (Py_ssize_t i = 0; i < nargs; i++) {
        PyObject *item = PyList_GetItem(args, i);
        if (item == NULL) {
            PyErr_Print();
            return NULL;
        }

        PyObject *str = PyObject_Str(item);
        if (str == NULL) {
            PyErr_Print();
            return NULL;
        }

        const char *s = PyUnicode_AsString(str);
        if (s) {
            if (i > 0) {
                fputs(sep, stdout);
            }
            fputs(s, stdout);
        }
        Py_DECREF(str);
    }

    fputs(end, stdout);
    Py_INCREF(Py_None);
    return Py_None;
}

/* len() implementation */
static PyObject* builtin_len(PyObject *self, PyObject *args) {
    (void)self;

    if (PyList_Size(args) != 1) {
        PyErr_SetString(PyExc_TypeError, "len() takes exactly one argument");
        return NULL;
    }

    PyObject *obj = PyList_GetItem(args, 0);
    if (obj == NULL) return NULL;

    Py_ssize_t length = PyObject_Length(obj);
    if (length < 0 && PyErr_Occurred()) {
        return NULL;
    }

    return PyLong_FromLong(length);
}

/* type() implementation */
static PyObject* builtin_type(PyObject *self, PyObject *args) {
    (void)self;

    if (PyList_Size(args) != 1) {
        PyErr_SetString(PyExc_TypeError, "type() takes exactly one argument");
        return NULL;
    }

    PyObject *obj = PyList_GetItem(args, 0);
    if (obj == NULL) return NULL;

    return (PyObject *)Py_TYPE(obj);
}

/* int() implementation */
static PyObject* builtin_int(PyObject *self, PyObject *args) {
    (void)self;

    if (PyList_Size(args) != 1) {
        PyErr_SetString(PyExc_TypeError, "int() takes exactly one argument");
        return NULL;
    }

    PyObject *obj = PyList_GetItem(args, 0);
    if (obj == NULL) return NULL;

    if (PyLong_Check(obj)) {
        Py_INCREF(obj);
        return obj;
    }

    if (PyUnicode_Check(obj)) {
        const char *s = PyUnicode_AsString(obj);
        if (s == NULL) return NULL;
        char *end;
        long v = strtol(s, &end, 10);
        if (*end != '\0') {
            PyErr_SetString(PyExc_ValueError, "invalid literal for int()");
            return NULL;
        }
        return PyLong_FromLong(v);
    }

    PyErr_SetString(PyExc_TypeError, "int() argument must be a string or a number");
    return NULL;
}

/* float() implementation */
static PyObject* builtin_float(PyObject *self, PyObject *args) {
    (void)self;

    if (PyList_Size(args) != 1) {
        PyErr_SetString(PyExc_TypeError, "float() takes exactly one argument");
        return NULL;
    }

    PyObject *obj = PyList_GetItem(args, 0);
    if (obj == NULL) return NULL;

    if (PyFloat_Check(obj)) {
        Py_INCREF(obj);
        return obj;
    }

    if (PyLong_Check(obj)) {
        return PyFloat_FromDouble((double)PyLong_AsLong(obj));
    }

    if (PyUnicode_Check(obj)) {
        const char *s = PyUnicode_AsString(obj);
        if (s == NULL) return NULL;
        char *end;
        double v = strtod(s, &end);
        if (*end != '\0') {
            PyErr_SetString(PyExc_ValueError, "invalid literal for float()");
            return NULL;
        }
        return PyFloat_FromDouble(v);
    }

    PyErr_SetString(PyExc_TypeError, "float() argument must be a string or a number");
    return NULL;
}

/* str() implementation */
static PyObject* builtin_str(PyObject *self, PyObject *args) {
    (void)self;

    if (PyList_Size(args) != 1) {
        PyErr_SetString(PyExc_TypeError, "str() takes exactly one argument");
        return NULL;
    }

    PyObject *obj = PyList_GetItem(args, 0);
    if (obj == NULL) return NULL;

    return PyObject_Str(obj);
}

/* bool() implementation */
static PyObject* builtin_bool(PyObject *self, PyObject *args) {
    (void)self;

    if (PyList_Size(args) != 1) {
        PyErr_SetString(PyExc_TypeError, "bool() takes exactly one argument");
        return NULL;
    }

    PyObject *obj = PyList_GetItem(args, 0);
    if (obj == NULL) return NULL;

    return PyBool_FromLong(PyObject_IsTrue(obj));
}

/* abs() implementation */
static PyObject* builtin_abs(PyObject *self, PyObject *args) {
    (void)self;

    if (PyList_Size(args) != 1) {
        PyErr_SetString(PyExc_TypeError, "abs() takes exactly one argument");
        return NULL;
    }

    PyObject *obj = PyList_GetItem(args, 0);
    if (obj == NULL) return NULL;

    if (Py_TYPE(obj)->tp_absolute) {
        return Py_TYPE(obj)->tp_absolute(obj);
    }

    PyErr_SetString(PyExc_TypeError, "bad operand type for abs()");
    return NULL;
}

/* min() implementation */
static PyObject* builtin_min(PyObject *self, PyObject *args) {
    (void)self;

    Py_ssize_t nargs = PyList_Size(args);
    if (nargs == 0) {
        PyErr_SetString(PyExc_TypeError, "min() takes at least one argument");
        return NULL;
    }

    PyObject *result = PyList_GetItem(args, 0);
    if (result == NULL) return NULL;

    for (Py_ssize_t i = 1; i < nargs; i++) {
        PyObject *item = PyList_GetItem(args, i);
        if (item == NULL) return NULL;
        if (PyObject_Compare(result, item) > 0) {
            result = item;
        }
    }

    Py_INCREF(result);
    return result;
}

/* max() implementation */
static PyObject* builtin_max(PyObject *self, PyObject *args) {
    (void)self;

    Py_ssize_t nargs = PyList_Size(args);
    if (nargs == 0) {
        PyErr_SetString(PyExc_TypeError, "max() takes at least one argument");
        return NULL;
    }

    PyObject *result = PyList_GetItem(args, 0);
    if (result == NULL) return NULL;

    for (Py_ssize_t i = 1; i < nargs; i++) {
        PyObject *item = PyList_GetItem(args, i);
        if (item == NULL) return NULL;
        if (PyObject_Compare(result, item) < 0) {
            result = item;
        }
    }

    Py_INCREF(result);
    return result;
}

/* Builtin function descriptor */
typedef struct {
    const char *name;
    PyCFunction func;
    int flags;
    const char *doc;
} BuiltinDef;

static BuiltinDef builtin_functions[] = {
    { "print", (PyCFunction)builtin_print, METH_KEYWORDS, "print(*args, sep=' ', end='\\n', file=sys.stdout)" },
    { "len",   (PyCFunction)builtin_len,   METH_NOARGS,   "len(s)" },
    { "type",  (PyCFunction)builtin_type,  METH_O,        "type(object)" },
    { "int",   (PyCFunction)builtin_int,   METH_O,        "int(x=0)" },
    { "float", (PyCFunction)builtin_float, METH_O,        "float(x=0.0)" },
    { "str",   (PyCFunction)builtin_str,   METH_O,        "str(object='')" },
    { "bool",  (PyCFunction)builtin_bool,  METH_O,        "bool(x)" },
    { "abs",   (PyCFunction)builtin_abs,   METH_O,        "abs(x)" },
    { "min",   (PyCFunction)builtin_min,   METH_VARARGS,  "min(s, *args)" },
    { "max",   (PyCFunction)builtin_max,   METH_VARARGS,  "max(s, *args)" },
    { NULL, NULL, 0, NULL }
};

/* Initialize builtins module */
static PyObject *builtin_module = NULL;

void PyBuiltins_Init(void) {
    builtin_module = PyDict_New();
    if (builtin_module == NULL) return;

    for (BuiltinDef *def = builtin_functions; def->name != NULL; def++) {
        PyMethodDef ml;
        ml.ml_name = def->name;
        ml.ml_meth = def->func;
        ml.ml_flags = def->flags;
        ml.ml_doc = def->doc;

        PyObject *func = PyCFunction_New(&ml, NULL);
        if (func) {
            PyDict_SetItemString(builtin_module, def->name, func);
        }
    }
}

PyObject* PyBuiltins_GetDict(void) {
    Py_INCREF(builtin_module);
    return builtin_module;
}

PyObject* PyBuiltins_GetFunction(const char *name) {
    PyObject *func = PyDict_GetItemString(builtin_module, name);
    if (func) Py_INCREF(func);
    return func;
}
