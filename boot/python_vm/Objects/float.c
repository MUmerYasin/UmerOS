/*
 * float.c - UmerOS Python Float Type
 */

#include "../Include/umeros_python.h"

typedef struct {
    PyObject ob_base;
    double value;
} PyFloatObject;

static void float_dealloc(PyObject *op) { free(op); }

static PyObject* float_repr(PyObject *op) {
    PyFloatObject *self = (PyFloatObject *)op;
    char buf[64];
    snprintf(buf, sizeof(buf), "%g", self->value);
    return PyUnicode_FromString(buf);
}

static PyObject* float_str(PyObject *op) { return float_repr(op); }

static int float_bool(PyObject *op) {
    PyFloatObject *self = (PyFloatObject *)op;
    return self->value != 0.0;
}

static Py_ssize_t float_hash(PyObject *op) {
    PyFloatObject *self = (PyFloatObject *)op;
    return (Py_ssize_t)(long)self->value;
}

static PyObject* float_negative(PyObject *op) {
    PyFloatObject *self = (PyFloatObject *)op;
    return PyFloat_FromDouble(-self->value);
}

static PyObject* float_positive(PyObject *op) {
    Py_INCREF(op);
    return op;
}

static PyObject* float_absolute(PyObject *op) {
    PyFloatObject *self = (PyFloatObject *)op;
    return PyFloat_FromDouble(self->value < 0 ? -self->value : self->value);
}

static PyObject* float_add(PyObject *left, PyObject *right) {
    PyFloatObject *l = (PyFloatObject *)left;
    PyFloatObject *r = (PyFloatObject *)right;
    return PyFloat_FromDouble(l->value + r->value);
}

static PyObject* float_subtract(PyObject *left, PyObject *right) {
    PyFloatObject *l = (PyFloatObject *)left;
    PyFloatObject *r = (PyFloatObject *)right;
    return PyFloat_FromDouble(l->value - r->value);
}

static PyObject* float_multiply(PyObject *left, PyObject *right) {
    PyFloatObject *l = (PyFloatObject *)left;
    PyFloatObject *r = (PyFloatObject *)right;
    return PyFloat_FromDouble(l->value * r->value);
}

static PyObject* float_true_divide(PyObject *left, PyObject *right) {
    PyFloatObject *l = (PyFloatObject *)left;
    PyFloatObject *r = (PyFloatObject *)right;
    if (r->value == 0.0) {
        PyErr_SetString(PyExc_ZeroDivisionError, "float division by zero");
        return NULL;
    }
    return PyFloat_FromDouble(l->value / r->value);
}

static PyObject* float_modulo(PyObject *left, PyObject *right) {
    PyFloatObject *l = (PyFloatObject *)left;
    PyFloatObject *r = (PyFloatObject *)right;
    if (r->value == 0.0) {
        PyErr_SetString(PyExc_ZeroDivisionError, "float modulo by zero");
        return NULL;
    }
    double result = fmod(l->value, r->value);
    return PyFloat_FromDouble(result);
}

static PyObject* float_power(PyObject *left, PyObject *right) {
    PyFloatObject *l = (PyFloatObject *)left;
    PyFloatObject *r = (PyFloatObject *)right;
    return PyFloat_FromDouble(pow(l->value, r->value));
}

static int float_compare(PyObject *left, PyObject *right) {
    PyFloatObject *l = (PyFloatObject *)left;
    PyFloatObject *r = (PyFloatObject *)right;
    if (l->value < r->value) return -1;
    if (l->value > r->value) return 1;
    if (l->value == r->value) return 0;
    return (l->value < r->value) ? -1 : 1;
}

PyTypeObject PyFloat_Type = {
    PyObject_HEAD_INIT(NULL)
    .tp_name = "float",
    .tp_basicsize = sizeof(PyFloatObject),
    .tp_dealloc = float_dealloc,
    .tp_repr = float_repr,
    .tp_str = float_str,
    .tp_bool = float_bool,
    .tp_hash = float_hash,
    .tp_negative = float_negative,
    .tp_positive = float_positive,
    .tp_absolute = float_absolute,
    .tp_add = float_add,
    .tp_subtract = float_subtract,
    .tp_multiply = float_multiply,
    .tp_true_divide = float_true_divide,
    .tp_modulo = float_modulo,
    .tp_power = float_power,
    .tp_compare = float_compare,
    .tp_flags = TPFLAGS_DEFAULT | TPFLAGS_HAVE_NUM,
    .tp_doc = "floating-point numbers"
};

PyObject* PyFloat_FromDouble(double v) {
    PyFloatObject *op = (PyFloatObject *)PyObject_New(&PyFloat_Type);
    if (op == NULL) return NULL;
    op->value = v;
    return (PyObject *)op;
}

double PyFloat_AsDouble(PyObject *op) {
    if (op == NULL) {
        PyErr_SetString_TypeError("expected float");
        return -1.0;
    }
    if (Py_TYPE(op) == &PyFloat_Type) {
        return ((PyFloatObject *)op)->value;
    }
    PyErr_SetString_TypeError("expected float");
    return -1.0;
}

int PyFloat_Check(PyObject *op) {
    return (op != NULL && Py_TYPE(op) == &PyFloat_Type);
}
