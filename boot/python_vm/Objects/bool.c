/*
 * bool.c - UmerOS Python Boolean Type
 *
 * Implements the bool type (True/False singletons).
 * bool is a subclass of int in CPython.
 */

#include "../Include/umeros_python.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* Forward declaration */
extern PyTypeObject PyBool_Type;

/* ==================== GLOBAL SINGLETONS ==================== */

static PyObject _py_true_struct  = { 1, &PyBool_Type };
static PyObject _py_false_struct = { 1, &PyBool_Type };
PyObject *Py_True  = &_py_true_struct;
PyObject *Py_False = &_py_false_struct;

/* ==================== BOOL TYPE ==================== */

static PyObject* bool_repr(PyObject *self) {
    if (Py_IsTrue(self)) {
        return (PyObject *)PyUnicode_FromStringAndSize("True", 4);
    } else {
        return (PyObject *)PyUnicode_FromStringAndSize("False", 5);
    }
}

static PyObject* bool_str(PyObject *self) {
    return bool_repr(self);
}

static PyObject* bool_bool(PyObject *self) {
    Py_INCREF(self);
    return self;
}

static PyObject* bool_neg(PyObject *self) {
    long val = Py_IsTrue(self) ? -1 : 0;
    return (PyObject *)PyLong_FromLong(val);
}

static PyObject* bool_add(PyObject *left, PyObject *right) {
    if (!PyBool_Check(left)) {
        PyErr_SetString_TypeError("unsupported operand type(s) for +");
        return NULL;
    }
    if (PyBool_Check(right)) {
        long r = Py_IsTrue(right) ? 1 : 0;
        long l = Py_IsTrue(left) ? 1 : 0;
        return (PyObject *)PyLong_FromLong(l + r);
    } else if (PyLong_Check(right)) {
        long l = Py_IsTrue(left) ? 1 : 0;
        long r = PyLong_AsLong(right);
        return (PyObject *)PyLong_FromLong(l + r);
    } else if (PyFloat_Check(right)) {
        double l = Py_IsTrue(left) ? 1.0 : 0.0;
        double r = PyFloat_AsDouble(right);
        return (PyObject *)PyFloat_FromDouble(l + r);
    }
    PyErr_SetString_TypeError("unsupported operand type(s) for +");
    return NULL;
}

static PyObject* bool_subtract(PyObject *left, PyObject *right) {
    if (!PyBool_Check(left)) {
        PyErr_SetString_TypeError("unsupported operand type(s) for -");
        return NULL;
    }
    if (PyBool_Check(right)) {
        long r = Py_IsTrue(right) ? 1 : 0;
        long l = Py_IsTrue(left) ? 1 : 0;
        return (PyObject *)PyLong_FromLong(l - r);
    } else if (PyLong_Check(right)) {
        long l = Py_IsTrue(left) ? 1 : 0;
        long r = PyLong_AsLong(right);
        return (PyObject *)PyLong_FromLong(l - r);
    } else if (PyFloat_Check(right)) {
        double l = Py_IsTrue(left) ? 1.0 : 0.0;
        double r = PyFloat_AsDouble(right);
        return (PyObject *)PyFloat_FromDouble(l - r);
    }
    PyErr_SetString_TypeError("unsupported operand type(s) for -");
    return NULL;
}

static PyObject* bool_multiply(PyObject *left, PyObject *right) {
    if (!PyBool_Check(left)) {
        PyErr_SetString_TypeError("unsupported operand type(s) for *");
        return NULL;
    }
    if (PyBool_Check(right)) {
        long r = Py_IsTrue(right) ? 1 : 0;
        long l = Py_IsTrue(left) ? 1 : 0;
        return (PyObject *)PyLong_FromLong(l * r);
    } else if (PyLong_Check(right)) {
        long l = Py_IsTrue(left) ? 1 : 0;
        long r = PyLong_AsLong(right);
        return (PyObject *)PyLong_FromLong(l * r);
    } else if (PyFloat_Check(right)) {
        double l = Py_IsTrue(left) ? 1.0 : 0.0;
        double r = PyFloat_AsDouble(right);
        return (PyObject *)PyFloat_FromDouble(l * r);
    }
    PyErr_SetString_TypeError("unsupported operand type(s) for *");
    return NULL;
}

/* ==================== TYPE OBJECT ==================== */

PyTypeObject PyBool_Type = {
    { 1, NULL },
    "bool",
    sizeof(PyObject),
    0,
    NULL,                       /* tp_new */
    NULL,                       /* tp_dealloc */
    bool_repr,                  /* tp_repr */
    bool_str,                   /* tp_str */
    NULL,                       /* tp_richcompare */
    NULL,                       /* tp_hash */
    bool_bool,                  /* tp_bool */
    bool_add,                   /* tp_add */
    bool_subtract,              /* tp_subtract */
    bool_multiply,              /* tp_multiply */
    NULL,                       /* tp_true_divide */
    NULL,                       /* tp_floor_divide */
    NULL,                       /* tp_remainder */
    NULL,                       /* tp_power */
    bool_neg,                   /* tp_negative */
    NULL,                       /* tp_positive */
    NULL,                       /* tp_absolute */
    NULL,                       /* tp_and */
    NULL,                       /* tp_xor */
    NULL,                       /* tp_or */
    NULL,                       /* tp_lshift */
    NULL,                       /* tp_rshift */
    NULL,                       /* tp_length */
    NULL,                       /* tp_concat */
    NULL,                       /* tp_repeat */
    NULL,                       /* tp_item */
    NULL,                       /* tp_getattro */
    NULL,                       /* tp_setattro */
    NULL,                       /* tp_call */
    NULL,                       /* tp_base */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE | Py_TPFLAGS_BOOL_SUBCLASS |
        Py_TPFLAGS_LONG_SUBCLASS,
};

/* ==================== BOOL FUNCTIONS ==================== */

PyObject* PyBool_FromLong(long ok) {
    PyObject *obj = ok ? Py_True : Py_False;
    Py_INCREF(obj);
    return obj;
}

/* ==================== INITIALIZATION ==================== */

static int bool_initialized = 0;

void bool_init(void) {
    if (bool_initialized) return;
    bool_initialized = 1;

    Py_True->ob_refcnt  = 1000000;
    Py_False->ob_refcnt = 1000000;
}
