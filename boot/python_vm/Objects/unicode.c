/*
 * unicode.c - UmerOS Python Unicode (str) Type
 */

#include "../Include/umeros_python.h"

typedef struct {
    PyObject ob_base;
    char *value;
    Py_ssize_t length;
    Py_ssize_t hash;
    uint8_t hash_computed;
} PyUnicodeObject;

static void unicode_dealloc(PyObject *op) {
    PyUnicodeObject *self = (PyUnicodeObject *)op;
    if (self->value) free(self->value);
    free(op);
}

static PyObject* unicode_repr(PyObject *op) {
    PyUnicodeObject *self = (PyUnicodeObject *)op;
    char *buf = (char *)malloc(self->length + 3);
    if (!buf) {
        PyErr_SetString_MemoryError("out of memory");
        return NULL;
    }
    buf[0] = '\'';
    memcpy(buf + 1, self->value, self->length);
    buf[self->length + 1] = '\'';
    buf[self->length + 2] = '\0';
    PyObject *result = PyUnicode_FromStringAndSize(buf, self->length + 2);
    free(buf);
    return result;
}

static PyObject* unicode_str(PyObject *op) {
    Py_INCREF(op);
    return op;
}

static Py_ssize_t unicode_length(PyObject *op) {
    PyUnicodeObject *self = (PyUnicodeObject *)op;
    return self->length;
}

static int unicode_bool(PyObject *op) {
    PyUnicodeObject *self = (PyUnicodeObject *)op;
    return self->length > 0;
}

static Py_ssize_t unicode_hash(PyObject *op) {
    PyUnicodeObject *self = (PyUnicodeObject *)op;
    if (self->hash_computed) return self->hash;

    Py_ssize_t hash = 0;
    for (Py_ssize_t i = 0; i < self->length; i++) {
        hash = hash * 31 + (unsigned char)self->value[i];
    }
    self->hash = hash;
    self->hash_computed = 1;
    return hash;
}

static PyObject* unicode_concat(PyObject *left, PyObject *right) {
    PyUnicodeObject *l = (PyUnicodeObject *)left;
    PyUnicodeObject *r = (PyUnicodeObject *)right;
    Py_ssize_t new_len = l->length + r->length;
    char *new_val = (char *)malloc(new_len + 1);
    if (!new_val) {
        PyErr_SetString_MemoryError("out of memory");
        return NULL;
    }
    memcpy(new_val, l->value, l->length);
    memcpy(new_val + l->length, r->value, r->length);
    new_val[new_len] = '\0';
    PyObject *result = PyUnicode_FromStringAndSize(new_val, new_len);
    free(new_val);
    return result;
}

static PyObject* unicode_repeat(PyObject *op, Py_ssize_t count) {
    PyUnicodeObject *self = (PyUnicodeObject *)op;
    if (count <= 0) {
        return PyUnicode_FromStringAndSize("", 0);
    }
    Py_ssize_t new_len = self->length * count;
    char *new_val = (char *)malloc(new_len + 1);
    if (!new_val) {
        PyErr_SetString_MemoryError("out of memory");
        return NULL;
    }
    for (Py_ssize_t i = 0; i < count; i++) {
        memcpy(new_val + i * self->length, self->value, self->length);
    }
    new_val[new_len] = '\0';
    PyObject *result = PyUnicode_FromStringAndSize(new_val, new_len);
    free(new_val);
    return result;
}

static PyObject* unicode_getitem(PyObject *op, PyObject *index) {
    PyUnicodeObject *self = (PyUnicodeObject *)op;
    if (!PyLong_Check(index)) {
        PyErr_SetString_TypeError("string indices must be integers");
        return NULL;
    }
    Py_ssize_t i = PyLong_AsLong(index);
    if (i < 0) i += self->length;
    if (i < 0 || i >= self->length) {
        PyErr_SetString_IndexError("string index out of range");
        return NULL;
    }
    char buf[2] = { self->value[i], '\0' };
    return PyUnicode_FromStringAndSize(buf, 1);
}

static int unicode_compare(PyObject *left, PyObject *right) {
    PyUnicodeObject *l = (PyUnicodeObject *)left;
    PyUnicodeObject *r = (PyUnicodeObject *)right;
    Py_ssize_t min_len = l->length < r->length ? l->length : r->length;
    int result = memcmp(l->value, r->value, min_len);
    if (result != 0) return result;
    if (l->length < r->length) return -1;
    if (l->length > r->length) return 1;
    return 0;
}

PyTypeObject PyUnicode_Type = {
    PyObject_HEAD_INIT(NULL)
    .tp_name = "str",
    .tp_basicsize = sizeof(PyUnicodeObject),
    .tp_dealloc = unicode_dealloc,
    .tp_repr = unicode_repr,
    .tp_str = unicode_str,
    .tp_bool = unicode_bool,
    .tp_hash = unicode_hash,
    .tp_length = unicode_length,
    .tp_item = unicode_getitem,
    .tp_concat = unicode_concat,
    .tp_repeat = unicode_repeat,
    .tp_compare = unicode_compare,
    .tp_flags = TPFLAGS_DEFAULT | TPFLAGS_HAVE_SEQ,
    .tp_doc = "string objects"
};

PyObject* PyUnicode_FromString(const char *v) {
    Py_ssize_t len = strlen(v);
    return PyUnicode_FromStringAndSize(v, len);
}

PyObject* PyUnicode_FromStringAndSize(const char *v, Py_ssize_t size) {
    PyUnicodeObject *op = (PyUnicodeObject *)PyObject_New(&PyUnicode_Type);
    if (op == NULL) return NULL;
    op->value = (char *)malloc(size + 1);
    if (op->value == NULL) {
        free(op);
        PyErr_SetString_MemoryError("out of memory");
        return NULL;
    }
    memcpy(op->value, v, size);
    op->value[size] = '\0';
    op->length = size;
    op->hash = 0;
    op->hash_computed = 0;
    return (PyObject *)op;
}

const char* PyUnicode_AsString(PyObject *op) {
    if (op == NULL || Py_TYPE(op) != &PyUnicode_Type) {
        PyErr_SetString_TypeError("expected str");
        return NULL;
    }
    return ((PyUnicodeObject *)op)->value;
}

Py_ssize_t PyUnicode_GetLength(PyObject *op) {
    if (op == NULL || Py_TYPE(op) != &PyUnicode_Type) {
        PyErr_SetString_TypeError("expected str");
        return -1;
    }
    return ((PyUnicodeObject *)op)->length;
}

int PyUnicode_Check(PyObject *op) {
    return (op != NULL && Py_TYPE(op) == &PyUnicode_Type);
}
