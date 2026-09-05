/*
 * unicode.c - UmerOS Python Unicode (str) Type
 */

#include "../Include/umeros_python.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

static PyObjectHash unicode_hash(PyObject *op) {
    PyUnicodeObject *self = (PyUnicodeObject *)op;
    if (self->hash_computed) return (PyObjectHash)self->hash;

    Py_ssize_t h = 0;
    for (Py_ssize_t i = 0; i < self->length; i++) {
        h = h * 31 + (unsigned char)self->value[i];
    }
    self->hash = h;
    self->hash_computed = 1;
    return (PyObjectHash)h;
}

static PyObject* unicode_richcompare(PyObject *left, PyObject *right, int op) {

    if (!PyUnicode_Check(right)) {
        Py_INCREF(Py_NotImplemented);
        return Py_NotImplemented;
    }
    PyUnicodeObject *l = (PyUnicodeObject *)left;
    PyUnicodeObject *r = (PyUnicodeObject *)right;
    Py_ssize_t min_len = l->length < r->length ? l->length : r->length;
    int cmp = memcmp(l->value, r->value, (size_t)min_len);
    if (cmp == 0) {
        if (l->length < r->length) cmp = -1;
        else if (l->length > r->length) cmp = 1;
    }
    int result = 0;
    switch (op) {
        case Py_LT: result = cmp < 0;  break;
        case Py_LE: result = cmp <= 0; break;
        case Py_EQ: result = cmp == 0; break;
        case Py_NE: result = cmp != 0; break;
        case Py_GT: result = cmp > 0;  break;
        case Py_GE: result = cmp >= 0; break;
    }
    return PyBool_FromLong(result);
}

static PyObject* unicode_concat(PyObject *left, PyObject *right) {
    if (!PyUnicode_Check(right)) {
        PyErr_SetString_TypeError("can only concatenate str to str");
        return NULL;
    }
    PyUnicodeObject *l = (PyUnicodeObject *)left;
    PyUnicodeObject *r = (PyUnicodeObject *)right;
    Py_ssize_t new_len = l->length + r->length;
    char *new_val = (char *)malloc((size_t)(new_len + 1));
    if (!new_val) {
        PyErr_SetString_MemoryError("out of memory");
        return NULL;
    }
    memcpy(new_val, l->value, (size_t)l->length);
    memcpy(new_val + l->length, r->value, (size_t)r->length);
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
    char *new_val = (char *)malloc((size_t)(new_len + 1));
    if (!new_val) {
        PyErr_SetString_MemoryError("out of memory");
        return NULL;
    }
    for (Py_ssize_t i = 0; i < count; i++) {
        memcpy(new_val + i * self->length, self->value, (size_t)self->length);
    }
    new_val[new_len] = '\0';
    PyObject *result = PyUnicode_FromStringAndSize(new_val, new_len);
    free(new_val);
    return result;
}

static PyObject* unicode_getitem(PyObject *op, Py_ssize_t index) {
    PyUnicodeObject *self = (PyUnicodeObject *)op;
    if (index < 0) index += self->length;
    if (index < 0 || index >= self->length) {
        PyErr_SetString_IndexError("string index out of range");
        return NULL;
    }
    char buf[2] = { self->value[index], '\0' };
    return PyUnicode_FromStringAndSize(buf, 1);
}

PyTypeObject PyUnicode_Type = {
    1, NULL, "str",
    sizeof(PyUnicodeObject),
    0,
    NULL,                       /* tp_new */
    unicode_dealloc,            /* tp_dealloc */
    unicode_repr,               /* tp_repr */
    unicode_str,                /* tp_str */
    unicode_richcompare,        /* tp_richcompare */
    unicode_hash,               /* tp_hash */
    unicode_bool,               /* tp_bool */
    NULL,                       /* tp_add */
    NULL,                       /* tp_subtract */
    NULL,                       /* tp_multiply */
    NULL,                       /* tp_true_divide */
    NULL,                       /* tp_floor_divide */
    NULL,                       /* tp_remainder */
    NULL,                       /* tp_power */
    NULL,                       /* tp_negative */
    NULL,                       /* tp_positive */
    NULL,                       /* tp_absolute */
    NULL,                       /* tp_and */
    NULL,                       /* tp_xor */
    NULL,                       /* tp_or */
    NULL,                       /* tp_lshift */
    NULL,                       /* tp_rshift */
    unicode_length,             /* tp_length */
    unicode_concat,             /* tp_concat */
    unicode_repeat,             /* tp_repeat */
    unicode_getitem,            /* tp_item */
    NULL,                       /* tp_getattro */
    NULL,                       /* tp_setattro */
    NULL,                       /* tp_call */
    NULL,                       /* tp_base */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_SEQUENCE | Py_TPFLAGS_UNICODE_SUBCLASS,
};

PyObject* PyUnicode_FromString(const char *v) {
    Py_ssize_t len = (Py_ssize_t)strlen(v);
    return PyUnicode_FromStringAndSize(v, len);
}

PyObject* PyUnicode_FromStringAndSize(const char *v, Py_ssize_t size) {
    PyUnicodeObject *op = (PyUnicodeObject *)PyObject_New(&PyUnicode_Type);
    if (op == NULL) return NULL;
    op->value = (char *)malloc((size_t)(size + 1));
    if (op->value == NULL) {
        free(op);
        PyErr_SetString_MemoryError("out of memory");
        return NULL;
    }
    memcpy(op->value, v, (size_t)size);
    op->value[size] = '\0';
    op->length = size;
    op->hash = 0;
    op->hash_computed = 0;
    return (PyObject *)op;
}

const char* PyUnicode_AsString(PyObject *op) {
    if (op == NULL || !PyUnicode_Check(op)) {
        PyErr_SetString_TypeError("expected str");
        return NULL;
    }
    return ((PyUnicodeObject *)op)->value;
}

Py_ssize_t PyUnicode_GetLength(PyObject *op) {
    if (op == NULL || !PyUnicode_Check(op)) {
        PyErr_SetString_TypeError("expected str");
        return -1;
    }
    return ((PyUnicodeObject *)op)->length;
}

static int unicode_initialized = 0;

void unicode_init(void) {
    if (unicode_initialized) return;
    unicode_initialized = 1;
}
