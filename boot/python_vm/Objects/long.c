/*
 * long.c - UmerOS Python Integer Type
 *
 * Variable-precision integer implementation.
 */

#include "../Include/umeros_python.h"

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

static int long_compare(PyObject *left, PyObject *right) {
    PyLongObject *l = (PyLongObject *)left;
    PyLongObject *r = (PyLongObject *)right;
    if (l->value < r->value) return -1;
    if (l->value > r->value) return 1;
    return 0;
}

/* Type object definition */
PyTypeObject PyLong_Type = {
    PyObject_HEAD_INIT(NULL)
    .tp_name = "int",
    .tp_basicsize = sizeof(PyLongObject),
    .tp_dealloc = long_dealloc,
    .tp_repr = long_repr,
    .tp_str = long_str,
    .tp_bool = long_bool,
    .tp_hash = long_hash,
    .tp_length = long_length,
    .tp_negative = long_negative,
    .tp_positive = long_positive,
    .tp_absolute = long_absolute,
    .tp_add = long_add,
    .tp_subtract = long_subtract,
    .tp_multiply = long_multiply,
    .tp_true_divide = long_true_divide,
    .tp_floor_divide = long_floor_divide,
    .tp_modulo = long_modulo,
    .tp_power = long_power,
    .tp_compare = long_compare,
    .tp_flags = TPFLAGS_DEFAULT | TPFLAGS_HAVE_NUM | TPFLAGS_HAVE_SEQ,
    .tp_doc = "integer objects"
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

int PyLong_Check(PyObject *op) {
    return (op != NULL && Py_TYPE(op) == &PyLong_Type);
}
