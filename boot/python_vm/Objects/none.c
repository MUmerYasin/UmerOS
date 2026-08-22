/*
 * none.c - UmerOS Python None Type
 */

#include "../Include/umeros_python.h"

typedef struct {
    PyObject ob_base;
} PyNoneObject;

/* Singleton instance */
static PyNoneObject _Py_None_struct = {
    .ob_base = { .ob_refcnt = 1, .ob_type = NULL }
};

PyObject *Py_None = (PyObject *)&_Py_None_struct;

static void none_dealloc(PyObject *op) {
    /* Singleton - do not free */
    (void)op;
}

static PyObject* none_repr(PyObject *op) {
    (void)op;
    return PyUnicode_FromString("None");
}

static PyObject* none_str(PyObject *op) {
    return none_repr(op);
}

static int none_bool(PyObject *op) {
    (void)op;
    return 0;
}

static Py_ssize_t none_hash(PyObject *op) {
    (void)op;
    return 0;
}

PyTypeObject PyNone_Type = {
    PyObject_HEAD_INIT(NULL)
    .tp_name = "NoneType",
    .tp_basicsize = sizeof(PyNoneObject),
    .tp_dealloc = none_dealloc,
    .tp_repr = none_repr,
    .tp_str = none_str,
    .tp_bool = none_bool,
    .tp_hash = none_hash,
    .tp_flags = Py_TPFLAGS_DEFAULT
};

void PyNone_Init(void) {
    Py_None->ob_type = &PyNone_Type;
}

int PyNone_Check(PyObject *op) {
    return (op == Py_None);
}
