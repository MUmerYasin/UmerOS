/*
 * bool.c - UmerOS Python Boolean Type
 *
 * Booleans are a subclass of int.
 */

#include "../Include/umeros_python.h"

typedef struct {
    PyObject ob_base;
    int value;
} PyBoolObject;

/* Singleton instances */
static PyBoolObject _Py_True_struct = {
    .ob_base = { .ob_refcnt = 1, .ob_type = NULL },
    .value = 1
};

static PyBoolObject _Py_False_struct = {
    .ob_base = { .ob_refcnt = 1, .ob_type = NULL },
    .value = 0
};

PyObject *Py_True = (PyObject *)&_Py_True_struct;
PyObject *Py_False = (PyObject *)&_Py_False_struct;

static void bool_dealloc(PyObject *op) {
    /* Singleton - do not free */
    (void)op;
}

static PyObject* bool_repr(PyObject *op) {
    PyBoolObject *self = (PyBoolObject *)op;
    return PyUnicode_FromString(self->value ? "True" : "False");
}

static PyObject* bool_str(PyObject *op) {
    return bool_repr(op);
}

static int bool_bool(PyObject *op) {
    PyBoolObject *self = (PyBoolObject *)op;
    return self->value;
}

static Py_ssize_t bool_hash(PyObject *op) {
    PyBoolObject *self = (PyBoolObject *)op;
    return (Py_ssize_t)self->value;
}

static PyObject* bool_negative(PyObject *op) {
    PyBoolObject *self = (PyBoolObject *)op;
    return PyLong_FromLong(-self->value);
}

static PyObject* bool_positive(PyObject *op) {
    PyBoolObject *self = (PyBoolObject *)op;
    return PyLong_FromLong(self->value);
}

static PyObject* bool_absolute(PyObject *op) {
    Py_INCREF(op);
    return op;
}

static PyObject* bool_add(PyObject *left, PyObject *right) {
    PyBoolObject *l = (PyBoolObject *)left;
    PyLongObject *r = (PyLongObject *)right;
    return PyLong_FromLong(l->value + ((PyLongObject *)r)->value);
}

static PyObject* bool_multiply(PyObject *left, PyObject *right) {
    PyBoolObject *l = (PyBoolObject *)left;
    PyLongObject *r = (PyLongObject *)right;
    return PyLong_FromLong(l->value * ((PyLongObject *)r)->value);
}

static int bool_compare(PyObject *left, PyObject *right) {
    PyBoolObject *l = (PyBoolObject *)left;
    PyBoolObject *r = (PyBoolObject *)right;
    if (l->value < r->value) return -1;
    if (l->value > r->value) return 1;
    return 0;
}

PyTypeObject PyBool_Type = {
    PyObject_HEAD_INIT(NULL)
    .tp_name = "bool",
    .tp_basicsize = sizeof(PyBoolObject),
    .tp_dealloc = bool_dealloc,
    .tp_repr = bool_repr,
    .tp_str = bool_str,
    .tp_bool = bool_bool,
    .tp_hash = bool_hash,
    .tp_negative = bool_negative,
    .tp_positive = bool_positive,
    .tp_absolute = bool_absolute,
    .tp_add = bool_add,
    .tp_multiply = bool_multiply,
    .tp_compare = bool_compare,
    .tp_flags = TPFLAGS_DEFAULT | TPFLAGS_HAVE_NUM,
    .tp_doc = "bool objects (True, False)"
};

void PyBool_Init(void) {
    Py_True->ob_type = &PyBool_Type;
    Py_False->ob_type = &PyBool_Type;
}

PyObject* PyBool_FromLong(long v) {
    return v ? Py_True : Py_False;
}

int PyBool_Check(PyObject *op) {
    return (op == Py_True || op == Py_False);
}
