/*
 * long.c - UmerOS Python Integer Type
 *
 * Variable-precision integer implementation.
 */

#include "../Include/umeros_python.h"
#include <stdio.h>
#include <stdlib.h>

/* Integer representation */
typedef struct {
    PyObject ob_base;
    long value;              /* Simple integer value */
    int is_overflow;         /* For future big integer support */
} PyLongObject;

/* Type methods */
static void long_dealloc(PyObject *op) {
    free(op);
}

static PyObject* long_repr(PyObject *op) {
    PyLongObject *self = (PyLongObject *)op;
    char buf[64];
    snprintf(buf, sizeof(buf), "%ld", self->value);
    return PyUnicode_FromString(buf);
}

static PyObject* long_str(PyObject *op) {
    return long_repr(op);
}

static Py_ssize_t long_length(PyObject *op) {
    PyLongObject *self = (PyLongObject *)op;
    /* Number of digits in decimal representation */
    if (self->value == 0) return 1;
    long n = self->value < 0 ? -self->value : self->value;
    Py_ssize_t count = 0;
    while (n > 0) {
        count++;
        n /= 10;
    }
    if (self->value < 0) count++;
    return count;
}

static int long_bool(PyObject *op) {
    PyLongObject *self = (PyLongObject *)op;
    return self->value != 0;
}

static Py_ssize_t long_hash(PyObject *op) {
    PyLongObject *self = (PyLongObject *)op;
    return (Py_ssize_t)self->value;
}

static PyObject* long_negative(PyObject *op) {
    PyLongObject *self = (PyLongObject *)op;
    return PyLong_FromLong(-self->value);
}

static PyObject* long_positive(PyObject *op) {
    Py_INCREF(op);
    return op;
}

static PyObject* long_absolute(PyObject *op) {
    PyLongObject *self = (PyLongObject *)op;
    return PyLong_FromLong(self->value < 0 ? -self->value : self->value);
}

static PyObject* long_add(PyObject *left, PyObject *right) {
    PyLongObject *l = (PyLongObject *)left;
    PyLongObject *r = (PyLongObject *)right;
    return PyLong_FromLong(l->value + r->value);
}

static PyObject* long_subtract(PyObject *left, PyObject *right) {
    PyLongObject *l = (PyLongObject *)left;
    PyLongObject *r = (PyLongObject *)right;
    return PyLong_FromLong(l->value - r->value);
}

static PyObject* long_multiply(PyObject *left, PyObject *right) {
    PyLongObject *l = (PyLongObject *)left;
    PyLongObject *r = (PyLongObject *)right;
    return PyLong_FromLong(l->value * r->value);
}

static PyObject* long_true_divide(PyObject *left, PyObject *right) {
    PyLongObject *l = (PyLongObject *)left;
    PyLongObject *r = (PyLongObject *)right;
    if (r->value == 0) {
        PyErr_SetString(PyExc_ZeroDivisionError, "division by zero");
        return NULL;
    }
    return PyFloat_FromDouble((double)l->value / (double)r->value);
}

static PyObject* long_floor_divide(PyObject *left, PyObject *right) {
    PyLongObject *l = (PyLongObject *)left;
    PyLongObject *r = (PyLongObject *)right;
    if (r->value == 0) {
        PyErr_SetString(PyExc_ZeroDivisionError, "division by zero");
        return NULL;
    }
    return PyLong_FromLong(l->value / r->value);
}

static PyObject* long_modulo(PyObject *left, PyObject *right) {
    PyLongObject *l = (PyLongObject *)left;
    PyLongObject *r = (PyLongObject *)right;
    if (r->value == 0) {
        PyErr_SetString(PyExc_ZeroDivisionError, "division by zero");
        return NULL;
    }
    return PyLong_FromLong(l->value % r->value);
}

static PyObject* long_power(PyObject *left, PyObject *right) {
    PyLongObject *l = (PyLongObject *)left;
    PyLongObject *r = (PyLongObject *)right;
    long result = 1;
    long base = l->value;
    long exp = r->value;
    while (exp > 0) {
        result *= base;
        exp--;
    }
    return PyLong_FromLong(result);
}

static PyObject* long_richcompare(PyObject *left, PyObject *right, int op) {
    PyLongObject *l = (PyLongObject *)left;
    PyLongObject *r = (PyLongObject *)right;
    int result = 0;
    switch (op) {
        case Py_LT: result = l->value < r->value; break;
        case Py_LE: result = l->value <= r->value; break;
        case Py_EQ: result = l->value == r->value; break;
        case Py_NE: result = l->value != r->value; break;
        case Py_GT: result = l->value > r->value; break;
        case Py_GE: result = l->value >= r->value; break;
    }
    PyObject *ret = result ? Py_True : Py_False;
    Py_INCREF(ret);
    return ret;
}

/* Type object definition */
PyTypeObject PyLong_Type = {
    1, NULL,                              /* PyObject_HEAD */
    "int",                                /* tp_name */
    sizeof(PyLongObject),                 /* tp_basicsize */
    0,                                    /* tp_itemsize */
    NULL,                                 /* tp_new */
    long_dealloc,                         /* tp_dealloc */
    long_repr,                            /* tp_repr */
    long_str,                             /* tp_str */
    long_richcompare,                     /* tp_richcompare */
    (PyObjectHash (*)(PyObject*))long_hash, /* tp_hash */
    long_bool,                            /* tp_bool */
    long_add,                             /* tp_add */
    long_subtract,                        /* tp_subtract */
    long_multiply,                        /* tp_multiply */
    NULL, NULL, NULL, NULL, NULL, NULL,   /* pow, neg, pos, abs, and, xor */
    NULL, NULL, NULL, NULL,               /* or, lshift, rshift */
    long_length,                          /* tp_length */
    NULL, NULL, NULL,                     /* concat, repeat, item */
    NULL, NULL,                           /* getattro, setattro */
    NULL,                                 /* tp_call */
    NULL,                                 /* tp_base */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_NUMBER | Py_TPFLAGS_SEQUENCE /* tp_flags */
};

/*
 * Public API.
 */
PyObject* PyLong_FromLong(long v) {
    PyLongObject *op = (PyLongObject *)PyObject_New(&PyLong_Type);
    if (op == NULL) return NULL;
    op->value = v;
    op->is_overflow = 0;
    return (PyObject *)op;
}

PyObject* PyLong_FromUnsignedLong(unsigned long v) {
    return PyLong_FromLong((long)v);
}

PyObject* PyLong_FromDouble(double v) {
    return PyLong_FromLong((long)v);
}

long PyLong_AsLong(PyObject *op) {
    if (op == NULL) {
        PyErr_SetString_TypeError("expected int");
        return -1;
    }
    if (Py_TYPE(op) == &PyLong_Type) {
        return ((PyLongObject *)op)->value;
    }
    PyErr_SetString_TypeError("expected int");
    return -1;
}
