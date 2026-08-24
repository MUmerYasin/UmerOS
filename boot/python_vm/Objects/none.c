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
    1, NULL,                       /* PyObject_HEAD */
    "NoneType",                    /* tp_name */
    sizeof(PyNoneObject),          /* tp_basicsize */
    0,                             /* tp_itemsize */
    NULL,                          /* tp_new */
    none_dealloc,                  /* tp_dealloc */
    none_repr,                     /* tp_repr */
    none_str,                      /* tp_str */
    NULL,                          /* tp_richcompare */
    (PyObjectHash (*)(PyObject*))none_hash, /* tp_hash */
    none_bool,                     /* tp_bool */
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,  /* number ops */
    NULL, NULL, NULL, NULL, NULL,                            /* more number + sequence */
    NULL,                          /* tp_length */
    NULL, NULL, NULL,              /* tp_concat, tp_repeat, tp_item */
    NULL, NULL,                    /* tp_getattro, tp_setattro */
    NULL,                          /* tp_call */
    NULL,                          /* tp_base */
    Py_TPFLAGS_DEFAULT             /* tp_flags */
};

void PyNone_Init(void) {
    Py_None->ob_type = &PyNone_Type;
}

int PyNone_Check(PyObject *op) {
    return (op == Py_None);
}
