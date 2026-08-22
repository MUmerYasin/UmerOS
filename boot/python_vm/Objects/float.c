/*
 * float.c - UmerOS Python Float Type
 *
 * Implements the float type with IEEE 754 double precision.
 */

#include "umeros_python.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* ==================== FLOAT TYPE ==================== */

static PyObject* float_repr(PyObject *self) {
    double val = PyFloat_AsDouble(self);
    char buf[64];
    snprintf(buf, sizeof(buf), "%.17g", val);
    size_t len = strlen(buf);
    char *str_buf = (char *)malloc(len + 1);
    if (!str_buf) return NULL;
    memcpy(str_buf, buf, len + 1);
    return (PyObject *)PyUnicode_FromStringAndSize(str_buf, (Py_ssize_t)len);
}

static PyObject* float_str(PyObject *self) {
    return float_repr(self);
}

static long float_hash(PyObject *self) {
    double val = PyFloat_AsDouble(self);
    return (long)val;
}

static PyObject* float_add(PyObject *left, PyObject *right) {
    if (PyFloat_Check(right)) {
        double l = PyFloat_AsDouble(left);
        double r = PyFloat_AsDouble(right);
        return (PyObject *)PyFloat_FromDouble(l + r);
    } else if (PyLong_Check(right)) {
        double l = PyFloat_AsDouble(left);
        double r = (double)PyLong_AsLong(right);
        return (PyObject *)PyFloat_FromDouble(l + r);
    }
    PyErr_SetString_TypeError("unsupported operand type(s) for +");
    return NULL;
}

static PyObject* float_subtract(PyObject *left, PyObject *right) {
    if (PyFloat_Check(right)) {
        double l = PyFloat_AsDouble(left);
        double r = PyFloat_AsDouble(right);
        return (PyObject *)PyFloat_FromDouble(l - r);
    } else if (PyLong_Check(right)) {
        double l = PyFloat_AsDouble(left);
        double r = (double)PyLong_AsLong(right);
        return (PyObject *)PyFloat_FromDouble(l - r);
    }
    PyErr_SetString_TypeError("unsupported operand type(s) for -");
    return NULL;
}

static PyObject* float_multiply(PyObject *left, PyObject *right) {
    if (PyFloat_Check(right)) {
        double l = PyFloat_AsDouble(left);
        double r = PyFloat_AsDouble(right);
        return (PyObject *)PyFloat_FromDouble(l * r);
    } else if (PyLong_Check(right)) {
        double l = PyFloat_AsDouble(left);
        double r = (double)PyLong_AsLong(right);
        return (PyObject *)PyFloat_FromDouble(l * r);
    }
    PyErr_SetString_TypeError("unsupported operand type(s) for *");
    return NULL;
}

static PyObject* float_true_divide(PyObject *left, PyObject *right) {
    if (PyFloat_Check(right)) {
        double l = PyFloat_AsDouble(left);
        double r = PyFloat_AsDouble(right);
        if (r == 0.0) {
            PyErr_SetString_ZeroDivisionError("float division by zero");
            return NULL;
        }
        return (PyObject *)PyFloat_FromDouble(l / r);
    } else if (PyLong_Check(right)) {
        double l = PyFloat_AsDouble(left);
        long r = PyLong_AsLong(right);
        if (r == 0) {
            PyErr_SetString_ZeroDivisionError("float division by zero");
            return NULL;
        }
        return (PyObject *)PyFloat_FromDouble(l / (double)r);
    }
    PyErr_SetString_TypeError("unsupported operand type(s) for /");
    return NULL;
}

static PyObject* float_floor_divide(PyObject *left, PyObject *right) {
    if (PyFloat_Check(right)) {
        double l = PyFloat_AsDouble(left);
        double r = PyFloat_AsDouble(right);
        if (r == 0.0) {
            PyErr_SetString_ZeroDivisionError("float floor division by zero");
            return NULL;
        }
        return (PyObject *)PyLong_FromLong((long)floor(l / r));
    } else if (PyLong_Check(right)) {
        double l = PyFloat_AsDouble(left);
        long r = PyLong_AsLong(right);
        if (r == 0) {
            PyErr_SetString_ZeroDivisionError("float floor division by zero");
            return NULL;
        }
        return (PyObject *)PyLong_FromLong((long)floor(l / (double)r));
    }
    PyErr_SetString_TypeError("unsupported operand type(s) for //");
    return NULL;
}

static PyObject* float_remainder(PyObject *left, PyObject *right) {
    if (PyFloat_Check(right)) {
        double l = PyFloat_AsDouble(left);
        double r = PyFloat_AsDouble(right);
        if (r == 0.0) {
            PyErr_SetString_ZeroDivisionError("float modulo by zero");
            return NULL;
        }
        return (PyObject *)PyFloat_FromDouble(fmod(l, r));
    } else if (PyLong_Check(right)) {
        double l = PyFloat_AsDouble(left);
        long r = PyLong_AsLong(right);
        if (r == 0) {
            PyErr_SetString_ZeroDivisionError("float modulo by zero");
            return NULL;
        }
        return (PyObject *)PyFloat_FromDouble(fmod(l, (double)r));
    }
    PyErr_SetString_TypeError("unsupported operand type(s) for %");
    return NULL;
}

static PyObject* float_power(PyObject *left, PyObject *right) {
    if (PyFloat_Check(right)) {
        double l = PyFloat_AsDouble(left);
        double r = PyFloat_AsDouble(right);
        return (PyObject *)PyFloat_FromDouble(pow(l, r));
    } else if (PyLong_Check(right)) {
        double l = PyFloat_AsDouble(left);
        long r = PyLong_AsLong(right);
        return (PyObject *)PyFloat_FromDouble(pow(l, (double)r));
    }
    PyErr_SetString_TypeError("unsupported operand type(s) for **");
    return NULL;
}

static PyObject* float_neg(PyObject *self) {
    double val = PyFloat_AsDouble(self);
    return (PyObject *)PyFloat_FromDouble(-val);
}

static PyObject* float_pos(PyObject *self) {
    Py_INCREF(self);
    return self;
}

static PyObject* float_abs(PyObject *self) {
    double val = PyFloat_AsDouble(self);
    return (PyObject *)PyFloat_FromDouble(fabs(val));
}

/* ==================== COMPARISON ==================== */

static PyObject* float_richcompare(PyObject *self, PyObject *other, int op) {
    double l = PyFloat_AsDouble(self);
    double r;
    if (PyFloat_Check(other)) {
        r = PyFloat_AsDouble(other);
    } else if (PyLong_Check(other)) {
        r = (double)PyLong_AsLong(other);
    } else {
        Py_INCREF(Py_NotImplemented);
        return Py_NotImplemented;
    }
    int result = 0;
    switch (op) {
        case Py_LT: result = l <  r; break;
        case Py_LE: result = l <= r; break;
        case Py_EQ: result = l == r; break;
        case Py_NE: result = l != r; break;
        case Py_GT: result = l >  r; break;
        case Py_GE: result = l >= r; break;
    }
    return PyBool_FromLong(result);
}

/* ==================== TYPE OBJECT ==================== */

PyTypeObject PyFloat_Type = {
    { 1, NULL },
    "float",
    sizeof(PyObject),
    0,
    NULL,                       /* tp_new */
    NULL,                       /* tp_dealloc */
    float_repr,                 /* tp_repr */
    float_str,                  /* tp_str */
    float_richcompare,          /* tp_richcompare */
    float_hash,                 /* tp_hash */
    NULL,                       /* tp_bool */
    float_add,                  /* tp_add */
    float_subtract,             /* tp_subtract */
    float_multiply,             /* tp_multiply */
    float_true_divide,          /* tp_true_divide */
    float_floor_divide,         /* tp_floor_divide */
    float_remainder,            /* tp_remainder */
    float_power,                /* tp_power */
    float_neg,                  /* tp_negative */
    float_pos,                  /* tp_positive */
    float_abs,                  /* tp_absolute */
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
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_FLOAT_SUBCLASS,
};

/* ==================== TYPE FUNCTIONS ==================== */

double PyFloat_AsDouble(PyObject *obj) {
    if (!obj) return 0.0;
    if (PyFloat_Check(obj)) {
        /* For our simple float, the value is stored in ob_type pointer abuse
         * or we need a wrapper. Let's use a different approach: store the
         * double in the first field after PyObject_HEAD */
        union { PyObject obj; double val; } *u = (void *)obj;
        return u->val;
    }
    if (PyLong_Check(obj)) {
        return (double)PyLong_AsLong(obj);
    }
    if (PyBool_Check(obj)) {
        return Py_IsTrue(obj) ? 1.0 : 0.0;
    }
    return 0.0;
}

PyObject* PyFloat_FromDouble(double val) {
    PyObject *obj = PyObject_New(&PyFloat_Type);
    if (!obj) return NULL;
    union { PyObject obj; double d; } *u = (void *)obj;
    u->d = val;
    return obj;
}

static int float_initialized = 0;

void float_init(void) {
    if (float_initialized) return;
    float_initialized = 1;
}
