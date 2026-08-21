/*
 * object.c - UmerOS Python Object System
 *
 * Core object operations, reference counting, and type system.
 */

#include "../Include/umeros_python.h"
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>

/* Thread state */
PyThreadState _current_thread = {0};

PyThreadState* PyThreadState_Get(void) {
    return &_current_thread;
}

/* Object allocation */
PyObject* PyObject_New(PyTypeObject *type) {
    PyObject *op = (PyObject *)calloc(1, type->tp_basicsize);
    if (!op) { PyErr_SetString(PyExc_MemoryError, "out of memory"); return NULL; }
    op->ob_refcnt = 1;
    op->ob_type = type;
    return op;
}

PyObject* PyObject_NewVar(PyTypeObject *type, Py_ssize_t size) {
    Py_ssize_t bs = type->tp_basicsize + size * (type->tp_itemsize > 0 ? type->tp_itemsize : 1);
    PyVarObject *op = (PyVarObject *)calloc(1, bs);
    if (!op) { PyErr_SetString(PyExc_MemoryError, "out of memory"); return NULL; }
    op->ob_base.ob_refcnt = 1;
    op->ob_base.ob_type = type;
    op->ob_size = size;
    return (PyObject *)op;
}

void PyObject_Free(PyObject *op) {
    if (!op) return;
    if (op->ob_type && op->ob_type->tp_dealloc)
        op->ob_type->tp_dealloc(op);
    else
        free(op);
}

/* Frame object */
PyFrameObject* PyFrame_New(PyCodeObject *code, PyObject *globals, PyObject *locals) {
    PyFrameObject *f = (PyFrameObject *)calloc(1, sizeof(PyFrameObject));
    if (!f) { PyErr_SetString(PyExc_MemoryError, "out of memory"); return NULL; }
    f->ob_base.ob_refcnt = 1;
    f->f_code = code;
    f->f_globals = globals;
    f->f_locals = locals;
    f->f_back = NULL;
    f->f_block_top = 0;
    return f;
}

void PyFrame_Free(PyFrameObject *frame) { if (frame) free(frame); }

PyObject* PyFrame_GetLocal(PyFrameObject *frame, const char *name) {
    if (!frame || !frame->f_locals) return NULL;
    return PyDict_GetItemString(frame->f_locals, name);
}

void PyFrame_SetLocal(PyFrameObject *frame, const char *name, PyObject *value) {
    if (!frame || !frame->f_locals) return;
    PyObject *k = PyUnicode_FromString(name);
    if (k) { PyDict_SetItem(frame->f_locals, k, value); Py_DECREF(k); }
}

PyObject* PyFrame_GetGlobal(PyFrameObject *frame, const char *name) {
    if (!frame || !frame->f_globals) return NULL;
    return PyDict_GetItemString(frame->f_globals, name);
}

void PyThreadState_PushFrame(PyThreadState *ts, PyFrameObject *f) {
    if (!ts || !f) return;
    f->f_back = ts->frame;
    ts->frame = f;
    ts->recursion_depth++;
}

PyFrameObject* PyThreadState_PopFrame(PyThreadState *ts) {
    if (!ts || !ts->frame) return NULL;
    PyFrameObject *f = ts->frame;
    ts->frame = f->f_back;
    ts->recursion_depth--;
    f->f_back = NULL;
    return f;
}

/* Code object */
PyCodeObject* PyCode_New(uint8_t *code, Py_ssize_t code_size,
                         PyObject **consts, Py_ssize_t n_consts) {
    PyCodeObject *co = (PyCodeObject *)calloc(1, sizeof(PyCodeObject));
    if (!co) { PyErr_SetString(PyExc_MemoryError, "out of memory"); return NULL; }
    co->ob_base.ob_refcnt = 1;
    co->code = code; co->code_size = code_size;
    co->consts = consts; co->n_consts = n_consts;
    co->names = NULL; co->n_names = 0;
    co->filename = "<unknown>"; co->name = "<module>";
    co->argcount = 0; co->flags = 0;
    return co;
}

void PyCode_Free(PyCodeObject *code) {
    if (!code) return;
    if (code->code) free(code->code);
    if (code->consts) {
        for (Py_ssize_t i = 0; i < code->n_consts; i++) Py_XDECREF(code->consts[i]);
        free(code->consts);
    }
    free(code);
}

/* Dict */
typedef struct { PyObject *key; PyObject *value; } DictEntry;
typedef struct { PyObject ob_base; DictEntry *entries; Py_ssize_t size; Py_ssize_t capacity; } PyDictObject;
static PyTypeObject _PyDict_Type = { .tp_name = "dict", .tp_basicsize = sizeof(PyDictObject) };

static void _dict_resize(PyDictObject *d) {
    Py_ssize_t nc = d->capacity == 0 ? 8 : d->capacity * 2;
    DictEntry *e = (DictEntry *)realloc(d->entries, nc * sizeof(DictEntry));
    if (e) { d->entries = e; d->capacity = nc; }
}

PyObject* PyDict_New(void) {
    PyDictObject *d = (PyDictObject *)calloc(1, sizeof(PyDictObject));
    if (!d) { PyErr_SetString(PyExc_MemoryError, "out of memory"); return NULL; }
    d->ob_base.ob_refcnt = 1; d->ob_base.ob_type = &_PyDict_Type;
    return (PyObject *)d;
}

int PyDict_SetItem(PyObject *dict, PyObject *key, PyObject *value) {
    if (!dict || !key) return -1;
    PyDictObject *d = (PyDictObject *)dict;
    for (Py_ssize_t i = 0; i < d->size; i++) {
        if (d->entries[i].key == key) {
            Py_XDECREF(d->entries[i].value); Py_INCREF(value);
            d->entries[i].value = value; return 0;
        }
    }
    if (d->size >= d->capacity) _dict_resize(d);
    Py_INCREF(key); Py_INCREF(value);
    d->entries[d->size].key = key; d->entries[d->size].value = value; d->size++;
    return 0;
}

PyObject* PyDict_GetItem(PyObject *dict, PyObject *key) {
    if (!dict || !key) return NULL;
    PyDictObject *d = (PyDictObject *)dict;
    for (Py_ssize_t i = 0; i < d->size; i++)
        if (d->entries[i].key == key) return d->entries[i].value;
    return NULL;
}

int PyDict_SetItemString(PyObject *dict, const char *key, PyObject *value) {
    PyObject *k = PyUnicode_FromString(key);
    if (!k) return -1;
    int r = PyDict_SetItem(dict, k, value); Py_DECREF(k); return r;
}

PyObject* PyDict_GetItemString(PyObject *dict, const char *key) {
    PyObject *k = PyUnicode_FromString(key);
    if (!k) return NULL;
    PyObject *v = PyDict_GetItem(dict, k); Py_DECREF(k); return v;
}

/* List */
typedef struct { PyObject ob_base; PyObject **items; Py_ssize_t size; Py_ssize_t allocated; } PyListObject;
static PyTypeObject _PyList_Type = { .tp_name = "list", .tp_basicsize = sizeof(PyListObject) };

PyObject* PyList_New(Py_ssize_t size) {
    PyListObject *l = (PyListObject *)calloc(1, sizeof(PyListObject));
    if (!l) { PyErr_SetString(PyExc_MemoryError, "out of memory"); return NULL; }
    l->ob_base.ob_refcnt = 1; l->ob_base.ob_type = &_PyList_Type;
    Py_ssize_t cap = size > 0 ? size : 8;
    l->items = (PyObject **)calloc(cap, sizeof(PyObject *));
    l->size = size; l->allocated = cap;
    for (Py_ssize_t i = 0; i < size; i++) { l->items[i] = Py_None; Py_INCREF(Py_None); }
    return (PyObject *)l;
}

Py_ssize_t PyList_Size(PyObject *list) { return list ? ((PyListObject*)list)->size : 0; }

PyObject* PyList_GetItem(PyObject *list, Py_ssize_t i) {
    if (!list) return NULL;
    PyListObject *l = (PyListObject *)list;
    if (i < 0) i += l->size;
    if (i < 0 || i >= l->size) { PyErr_SetString(PyExc_IndexError, "list index out of range"); return NULL; }
    return l->items[i];
}

int PyList_SetItem(PyObject *list, Py_ssize_t i, PyObject *value) {
    if (!list) return -1;
    PyListObject *l = (PyListObject *)list;
    if (i < 0) i += l->size;
    if (i < 0 || i >= l->size) { PyErr_SetString(PyExc_IndexError, "list index out of range"); return -1; }
    Py_XDECREF(l->items[i]); Py_INCREF(value); l->items[i] = value; return 0;
}

/* Tuple */
typedef struct { PyObject ob_base; PyObject **items; Py_ssize_t size; } PyTupleObject;
static PyTypeObject _PyTuple_Type = { .tp_name = "tuple", .tp_basicsize = sizeof(PyTupleObject) };

PyObject* PyTuple_New(Py_ssize_t size) {
    PyTupleObject *t = (PyTupleObject *)calloc(1, sizeof(PyTupleObject));
    if (!t) { PyErr_SetString(PyExc_MemoryError, "out of memory"); return NULL; }
    t->ob_base.ob_refcnt = 1; t->ob_base.ob_type = &_PyTuple_Type;
    t->items = (PyObject **)calloc(size > 0 ? size : 1, sizeof(PyObject *));
    t->size = size;
    for (Py_ssize_t i = 0; i < size; i++) { t->items[i] = Py_None; Py_INCREF(Py_None); }
    return (PyObject *)t;
}

Py_ssize_t PyTuple_Size(PyObject *t) { return t ? ((PyTupleObject*)t)->size : 0; }

PyObject* PyTuple_GetItem(PyObject *tuple, Py_ssize_t i) {
    if (!tuple) return NULL;
    PyTupleObject *t = (PyTupleObject *)tuple;
    if (i < 0) i += t->size;
    if (i < 0 || i >= t->size) { PyErr_SetString(PyExc_IndexError, "tuple index out of range"); return NULL; }
    return t->items[i];
}

int PyTuple_SetItem(PyObject *tuple, Py_ssize_t i, PyObject *value) {
    if (!tuple) return -1;
    PyTupleObject *t = (PyTupleObject *)tuple;
    if (i < 0) i += t->size;
    if (i < 0 || i >= t->size) { PyErr_SetString(PyExc_IndexError, "tuple index out of range"); return -1; }
    Py_XDECREF(t->items[i]); Py_INCREF(value); t->items[i] = value; return 0;
}

/* Sequence */
Py_ssize_t PySequence_Size(PyObject *seq) {
    if (!seq) return 0;
    if (Py_TYPE(seq) == &_PyList_Type) return PyList_Size(seq);
    if (Py_TYPE(seq) == &_PyTuple_Type) return PyTuple_Size(seq);
    if (Py_TYPE(seq) == &_PyDict_Type) return ((PyDictObject*)seq)->size;
    return 0;
}

PyObject* PySequence_GetItem(PyObject *seq, Py_ssize_t i) {
    if (!seq) return NULL;
    if (Py_TYPE(seq) == &_PyList_Type) return PyList_GetItem(seq, i);
    if (Py_TYPE(seq) == &_PyTuple_Type) return PyTuple_GetItem(seq, i);
    PyErr_SetString(PyExc_TypeError, "object is not a sequence");
    return NULL;
}

int PySequence_Contains(PyObject *seq, PyObject *item) {
    if (!seq || !item) return 0;
    if (Py_TYPE(seq) == &_PyList_Type) {
        PyListObject *l = (PyListObject *)seq;
        for (Py_ssize_t i = 0; i < l->size; i++) if (l->items[i] == item) return 1;
        return 0;
    }
    if (Py_TYPE(seq) == &_PyTuple_Type) {
        PyTupleObject *t = (PyTupleObject *)seq;
        for (Py_ssize_t i = 0; i < t->size; i++) if (t->items[i] == item) return 1;
        return 0;
    }
    return 0;
}

/* Iterator */
int PyIter_Check(PyObject *op) {
    if (!op) return 0;
    return (Py_TYPE(op) == &_PyList_Type || Py_TYPE(op) == &_PyTuple_Type);
}

PyObject* PyIter_Next(PyObject *iter) {
    /* Stub - full implementation requires iterator objects */
    (void)iter;
    return NULL;
}

/* Import */
PyObject* PyImport_ImportModule(const char *name) {
    if (!name) return NULL;
    PyObject *m = PyDict_New();
    if (m) PyDict_SetItemString(m, "__name__", PyUnicode_FromString(name));
    return m;
}

/* String conversion */
PyObject* PyObject_Str(PyObject *op) {
    if (!op) return PyUnicode_FromString("None");
    if (Py_TYPE(op)->tp_str) return Py_TYPE(op)->tp_str(op);
    if (Py_TYPE(op)->tp_repr) return Py_TYPE(op)->tp_repr(op);
    char buf[128];
    snprintf(buf, sizeof(buf), "<%s object at %p>",
             Py_TYPE(op)->tp_name ? Py_TYPE(op)->tp_name : "unknown", (void*)op);
    return PyUnicode_FromString(buf);
}

PyObject* PyObject_Repr(PyObject *op) {
    if (!op) return PyUnicode_FromString("None");
    if (Py_TYPE(op)->tp_repr) return Py_TYPE(op)->tp_repr(op);
    return PyObject_Str(op);
}

/* Boolean */
int PyObject_IsTrue(PyObject *op) {
    if (!op) return 0;
    if (op == Py_True) return 1;
    if (op == Py_False) return 0;
    if (Py_TYPE(op)->tp_bool) return Py_TYPE(op)->tp_bool(op);
    if (Py_TYPE(op) == &_PyList_Type) return ((PyListObject*)op)->size != 0;
    if (Py_TYPE(op) == &_PyTuple_Type) return ((PyTupleObject*)op)->size != 0;
    return 1;
}

/* Hash */
Py_ssize_t PyObject_Hash(PyObject *op) {
    if (!op) return 0;
    if (Py_TYPE(op)->tp_hash) return (Py_ssize_t)Py_TYPE(op)->tp_hash(op);
    return (Py_ssize_t)((uintptr_t)op);
}

/* Comparison */
int PyObject_Compare(PyObject *a, PyObject *b) {
    if (a == b) return 0;
    if (!a) return -1;
    if (!b) return 1;
    if (Py_TYPE(a)->tp_compare) return Py_TYPE(a)->tp_compare(a, b);
    const char *n1 = Py_TYPE(a)->tp_name ? Py_TYPE(a)->tp_name : "";
    const char *n2 = Py_TYPE(b)->tp_name ? Py_TYPE(b)->tp_name : "";
    return strcmp(n1, n2);
}

/* Attribute access */
PyObject* PyObject_GetAttr(PyObject *op, PyObject *name) {
    if (!op || !name) { PyErr_SetString(PyExc_TypeError, "argument must be an object"); return NULL; }
    if (Py_TYPE(op)->tp_getattr) {
        const char *n = PyUnicode_AsString(name);
        if (n) return Py_TYPE(op)->tp_getattr(op, n);
    }
    PyErr_Format(PyExc_AttributeError, "'%.200s' object has no attribute '%.200s'",
                 Py_TYPE(op)->tp_name, PyUnicode_AsString(name));
    return NULL;
}

int PyObject_SetAttr(PyObject *op, PyObject *name, PyObject *value) {
    if (!op || !name) { PyErr_SetString(PyExc_TypeError, "argument must be an object"); return -1; }
    PyErr_Format(PyExc_AttributeError, "'%.200s' object has no attribute '%.200s'",
                 Py_TYPE(op)->tp_name, PyUnicode_AsString(name));
    return -1;
}

/* Callable */
int PyCallable_Check(PyObject *op) { return op && Py_TYPE(op)->tp_call; }

PyObject* PyObject_Call(PyObject *callable, PyObject *args, PyObject *kwargs) {
    if (!callable) { PyErr_SetString(PyExc_TypeError, "object is not callable"); return NULL; }
    if (Py_TYPE(callable)->tp_call) return Py_TYPE(callable)->tp_call(callable, args, kwargs);
    PyErr_Format(PyExc_TypeError, "'%.200s' object is not callable", Py_TYPE(callable)->tp_name);
    return NULL;
}

/* Type */
int PyType_Ready(PyTypeObject *type) {
    if (!type) return -1;
    if (!type->tp_name) type->tp_name = "<unknown type>";
    return 0;
}

int PyType_IsSubtype(PyTypeObject *a, PyTypeObject *b) {
    if (a == b) return 1;
    return 0;
}
