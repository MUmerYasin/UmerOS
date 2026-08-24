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
    PyObject *op = (PyObject *)calloc(1, (size_t)type->tp_basicsize);
    if (!op) { PyErr_SetString(PyExc_MemoryError, "out of memory"); return NULL; }
    op->ob_refcnt = 1;
    op->ob_type = type;
    return op;
}

PyObject* PyObject_NewVar(PyTypeObject *type, Py_ssize_t size) {
    Py_ssize_t bs = type->tp_basicsize + size * (type->tp_itemsize > 0 ? type->tp_itemsize : 1);
    PyVarObject *op = (PyVarObject *)calloc(1, (size_t)bs);
    if (!op) { PyErr_SetString(PyExc_MemoryError, "out of memory"); return NULL; }
    op->ob_base.ob_refcnt = 1;
    op->ob_base.ob_type = type;
    op->ob_size = size;
    return (PyObject *)op;
}

void Py_Dealloc(PyObject *op) {
    if (!op) return;
    if (op->ob_type && op->ob_type->tp_dealloc)
        op->ob_type->tp_dealloc(op);
    else
        free(op);
}

void PyObject_Free(PyObject *op) { Py_Dealloc(op); }

void PyObject_Print(PyObject *self) {
    if (!self) { printf("<NULL>"); return; }
    PyObject *s = PyObject_Str(self);
    if (s) { printf("%s", PyUnicode_AsString(s)); Py_DECREF(s); }
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

/* ==================== Dict ==================== */

typedef struct { PyObject *key; PyObject *value; } DictEntry;
typedef struct { PyObject ob_base; DictEntry *entries; Py_ssize_t size; Py_ssize_t capacity; } PyDictObject;

static PyTypeObject _PyDict_Type = {
    1, NULL, "dict", sizeof(PyDictObject), 0,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL,
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_MAPPING | Py_TPFLAGS_DICT_SUBCLASS
};

static void _dict_resize(PyDictObject *d) {
    Py_ssize_t nc = d->capacity == 0 ? 8 : d->capacity * 2;
    DictEntry *e = (DictEntry *)realloc(d->entries, (size_t)nc * sizeof(DictEntry));
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

/* ==================== List ==================== */

typedef struct { PyObject ob_base; PyObject **items; Py_ssize_t size; Py_ssize_t allocated; } PyListObject;

static PyTypeObject _PyList_Type = {
    1, NULL, "list", sizeof(PyListObject), 0,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL,
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_SEQUENCE | Py_TPFLAGS_LIST_SUBCLASS
};

PyObject* PyList_New(Py_ssize_t size) {
    PyListObject *l = (PyListObject *)calloc(1, sizeof(PyListObject));
    if (!l) { PyErr_SetString(PyExc_MemoryError, "out of memory"); return NULL; }
    l->ob_base.ob_refcnt = 1; l->ob_base.ob_type = &_PyList_Type;
    Py_ssize_t cap = size > 0 ? size : 8;
    l->items = (PyObject **)calloc((size_t)cap, sizeof(PyObject *));
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

int PyList_Append(PyObject *list, PyObject *item) {
    if (!list) return -1;
    PyListObject *l = (PyListObject *)list;
    if (l->size >= l->allocated) {
        Py_ssize_t nc = l->allocated == 0 ? 8 : l->allocated * 2;
        PyObject **items = (PyObject **)realloc(l->items, (size_t)nc * sizeof(PyObject *));
        if (!items) return -1;
        l->items = items; l->allocated = nc;
    }
    Py_INCREF(item);
    l->items[l->size] = item; l->size++;
    return 0;
}

/* ==================== Tuple ==================== */

typedef struct { PyObject ob_base; PyObject **items; Py_ssize_t size; } PyTupleObject;

static PyTypeObject _PyTuple_Type = {
    1, NULL, "tuple", sizeof(PyTupleObject), 0,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL,
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_SEQUENCE | Py_TPFLAGS_TUPLE_SUBCLASS
};

PyObject* PyTuple_New(Py_ssize_t size) {
    PyTupleObject *t = (PyTupleObject *)calloc(1, sizeof(PyTupleObject));
    if (!t) { PyErr_SetString(PyExc_MemoryError, "out of memory"); return NULL; }
    t->ob_base.ob_refcnt = 1; t->ob_base.ob_type = &_PyTuple_Type;
    t->items = (PyObject **)calloc(size > 0 ? (size_t)size : 1, sizeof(PyObject *));
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

/* ==================== Sequence ==================== */

Py_ssize_t PySequence_Size(PyObject *seq) {
    if (!seq) return 0;
    PyTypeObject *tp = Py_TYPE(seq);
    if (tp->tp_length) return tp->tp_length(seq);
    if (Py_TYPE(seq) == &_PyList_Type) return PyList_Size(seq);
    if (Py_TYPE(seq) == &_PyTuple_Type) return PyTuple_Size(seq);
    return 0;
}

PyObject* PySequence_GetItem(PyObject *seq, Py_ssize_t i) {
    if (!seq) return NULL;
    PyTypeObject *tp = Py_TYPE(seq);
    if (tp->tp_item) return tp->tp_item(seq, i);
    PyErr_SetString(PyExc_TypeError, "object is not a sequence");
    return NULL;
}

PyObject* PySequence_Concat(PyObject *s, PyObject *o) {
    if (!s || !o) return NULL;
    PyTypeObject *tp = Py_TYPE(s);
    if (tp->tp_concat) return tp->tp_concat(s, o);
    PyErr_SetString(PyExc_TypeError, "object does not support concatenation");
    return NULL;
}

PyObject* PySequence_Repeat(PyObject *o, Py_ssize_t count) {
    if (!o) return NULL;
    PyTypeObject *tp = Py_TYPE(o);
    if (tp->tp_repeat) return tp->tp_repeat(o, count);
    PyErr_SetString(PyExc_TypeError, "object does not support repetition");
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

/* ==================== Iterator ==================== */

PyObject* PyIter_Next(PyObject *iter) {
    (void)iter;
    return NULL;
}

/* ==================== Import ==================== */

PyObject* PyImport_ImportModule(const char *name) {
    if (!name) return NULL;
    PyObject *m = PyDict_New();
    if (m) PyDict_SetItemString(m, "__name__", PyUnicode_FromString(name));
    return m;
}

/* ==================== String conversion ==================== */

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

/* ==================== Boolean ==================== */

int PyObject_IsTrue(PyObject *op) {
    if (!op) return 0;
    if (op == Py_True) return 1;
    if (op == Py_False) return 0;
    if (Py_TYPE(op)->tp_bool) return Py_TYPE(op)->tp_bool(op);
    if (Py_TYPE(op)->tp_length) return Py_TYPE(op)->tp_length(op) != 0;
    return 1;
}

int PyObject_Not(PyObject *op) {
    return !PyObject_IsTrue(op);
}

/* ==================== Hash ==================== */

Py_ssize_t PyObject_Hash(PyObject *op) {
    if (!op) return 0;
    if (Py_TYPE(op)->tp_hash) return (Py_ssize_t)Py_TYPE(op)->tp_hash(op);
    return (Py_ssize_t)((uintptr_t)op);
}

/* ==================== Rich comparison ==================== */

PyObject* PyObject_RichCompare(PyObject *v, PyObject *w, int op) {
    if (!v || !w) {
        Py_INCREF(Py_NotImplemented);
        return Py_NotImplemented;
    }
    if (Py_TYPE(v)->tp_richcompare) {
        PyObject *result = Py_TYPE(v)->tp_richcompare(v, w, op);
        if (result != Py_NotImplemented) return result;
        Py_DECREF(result);
    }
    if (Py_TYPE(w)->tp_richcompare) {
        PyObject *result = Py_TYPE(w)->tp_richcompare(w, v, op ^ ((op == Py_LT) | (op == Py_GT)));
        if (result != Py_NotImplemented) return result;
        Py_DECREF(result);
    }
    int result = (uintptr_t)v < (uintptr_t)w ? -1 : (uintptr_t)v > (uintptr_t)w ? 1 : 0;
    switch (op) {
        case Py_LT: return PyBool_FromLong(result < 0);
        case Py_LE: return PyBool_FromLong(result <= 0);
        case Py_EQ: return PyBool_FromLong(result == 0);
        case Py_NE: return PyBool_FromLong(result != 0);
        case Py_GT: return PyBool_FromLong(result > 0);
        case Py_GE: return PyBool_FromLong(result >= 0);
    }
    Py_INCREF(Py_NotImplemented);
    return Py_NotImplemented;
}

int PyObject_Compare(PyObject *a, PyObject *b) {
    if (a == b) return 0;
    if (!a) return -1;
    if (!b) return 1;
    if (Py_TYPE(a)->tp_richcompare) {
        PyObject *r = Py_TYPE(a)->tp_richcompare(a, b, Py_EQ);
        if (r) { int ok = PyObject_IsTrue(r); Py_DECREF(r); return ok ? 0 : -1; }
    }
    const char *n1 = Py_TYPE(a)->tp_name ? Py_TYPE(a)->tp_name : "";
    const char *n2 = Py_TYPE(b)->tp_name ? Py_TYPE(b)->tp_name : "";
    return strcmp(n1, n2);
}

/* ==================== Attribute access ==================== */

PyObject* PyObject_GetAttr(PyObject *op, PyObject *name) {
    if (!op || !name) { PyErr_SetString(PyExc_TypeError, "argument must be an object"); return NULL; }
    if (Py_TYPE(op)->tp_getattro) return Py_TYPE(op)->tp_getattro(op, name);
    PyErr_Format(PyExc_AttributeError, "'%.200s' object has no attribute '%.200s'",
                 Py_TYPE(op)->tp_name, PyUnicode_AsString(name));
    return NULL;
}

int PyObject_SetAttr(PyObject *op, PyObject *name, PyObject *value) {
    if (!op || !name) { PyErr_SetString(PyExc_TypeError, "argument must be an object"); return -1; }
    if (Py_TYPE(op)->tp_setattro) return Py_TYPE(op)->tp_setattro(op, name, value);
    PyErr_Format(PyExc_AttributeError, "'%.200s' object has no attribute '%.200s'",
                 Py_TYPE(op)->tp_name, PyUnicode_AsString(name));
    return -1;
}

/* ==================== Callable ==================== */

PyObject* PyObject_Call(PyObject *callable, PyObject *args, PyObject *kwargs) {
    if (!callable) { PyErr_SetString(PyExc_TypeError, "object is not callable"); return NULL; }
    if (Py_TYPE(callable)->tp_call) return Py_TYPE(callable)->tp_call(callable, args, kwargs);
    PyErr_Format(PyExc_TypeError, "'%.200s' object is not callable", Py_TYPE(callable)->tp_name);
    return NULL;
}

/* ==================== Length ==================== */

Py_ssize_t PyObject_Length(PyObject *o) {
    if (!o) return 0;
    if (Py_TYPE(o)->tp_length) return Py_TYPE(o)->tp_length(o);
    if (Py_TYPE(o) == &_PyList_Type) return ((PyListObject*)o)->size;
    if (Py_TYPE(o) == &_PyTuple_Type) return ((PyTupleObject*)o)->size;
    PyErr_SetString(PyExc_TypeError, "object has no len()");
    return -1;
}

/* ==================== Number protocol ==================== */

static PyObject* binary_op(PyObject *v, PyObject *w, const char *op_name,
                           PyObject* (*func)(PyObject*, PyObject*)) {
    if (func) {
        PyObject *result = func(v, w);
        if (result != Py_NotImplemented) return result;
        Py_DECREF(result);
    }
    PyErr_Format(PyExc_TypeError, "unsupported operand type(s) for %.100s: '%.100s' and '%.100s'",
                 op_name, Py_TYPE(v)->tp_name, Py_TYPE(w)->tp_name);
    return NULL;
}

PyObject* PyNumber_Add(PyObject *v, PyObject *w) {
    return binary_op(v, w, "+", Py_TYPE(v)->tp_add ? Py_TYPE(v)->tp_add : (Py_TYPE(w)->tp_add ? Py_TYPE(w)->tp_add : NULL));
}

PyObject* PyNumber_Subtract(PyObject *v, PyObject *w) {
    return binary_op(v, w, "-", Py_TYPE(v)->tp_subtract ? Py_TYPE(v)->tp_subtract : NULL);
}

PyObject* PyNumber_Multiply(PyObject *v, PyObject *w) {
    return binary_op(v, w, "*", Py_TYPE(v)->tp_multiply ? Py_TYPE(v)->tp_multiply : NULL);
}

PyObject* PyNumber_TrueDivide(PyObject *v, PyObject *w) {
    return binary_op(v, w, "/", Py_TYPE(v)->tp_true_divide ? Py_TYPE(v)->tp_true_divide : NULL);
}

PyObject* PyNumber_FloorDivide(PyObject *v, PyObject *w) {
    return binary_op(v, w, "//", Py_TYPE(v)->tp_floor_divide ? Py_TYPE(v)->tp_floor_divide : NULL);
}

PyObject* PyNumber_Remainder(PyObject *v, PyObject *w) {
    return binary_op(v, w, "%", Py_TYPE(v)->tp_remainder ? Py_TYPE(v)->tp_remainder : NULL);
}

PyObject* PyNumber_Power(PyObject *v, PyObject *w) {
    return binary_op(v, w, "**", Py_TYPE(v)->tp_power ? Py_TYPE(v)->tp_power : NULL);
}

PyObject* PyNumber_Negative(PyObject *v) {
    if (Py_TYPE(v)->tp_negative) return Py_TYPE(v)->tp_negative(v);
    PyErr_Format(PyExc_TypeError, "bad operand type for unary -: '%.100s'", Py_TYPE(v)->tp_name);
    return NULL;
}

PyObject* PyNumber_Positive(PyObject *v) {
    if (Py_TYPE(v)->tp_positive) return Py_TYPE(v)->tp_positive(v);
    PyErr_Format(PyExc_TypeError, "bad operand type for unary +: '%.100s'", Py_TYPE(v)->tp_name);
    return NULL;
}

PyObject* PyNumber_Absolute(PyObject *v) {
    if (Py_TYPE(v)->tp_absolute) return Py_TYPE(v)->tp_absolute(v);
    PyErr_Format(PyExc_TypeError, "bad operand type for abs(): '%.100s'", Py_TYPE(v)->tp_name);
    return NULL;
}

PyObject* PyNumber_Long(PyObject *o) {
    if (!o) return NULL;
    if (Py_TYPE(o)->tp_flags & Py_TPFLAGS_LONG_SUBCLASS) { Py_INCREF(o); return o; }
    PyErr_SetString(PyExc_TypeError, "int() argument must be a string, a bytes-like object or a number");
    return NULL;
}

PyObject* PyNumber_Float(PyObject *o) {
    if (!o) return NULL;
    if (Py_TYPE(o)->tp_flags & Py_TPFLAGS_FLOAT_SUBCLASS) { Py_INCREF(o); return o; }
    PyErr_SetString(PyExc_TypeError, "float() argument must be a string or a number");
    return NULL;
}

PyObject* PyNumber_Index(PyObject *o) {
    if (!o) return NULL;
    if (Py_TYPE(o)->tp_flags & Py_TPFLAGS_LONG_SUBCLASS) { Py_INCREF(o); return o; }
    PyErr_SetString(PyExc_TypeError, "'%s' object cannot be interpreted as an integer", Py_TYPE(o)->tp_name);
    return NULL;
}

/* ==================== Type ==================== */

int PyType_Ready(PyTypeObject *type) {
    if (!type) return -1;
    if (!type->tp_name) type->tp_name = "<unknown type>";
    return 0;
}

/* PyType_IsSubtype is defined as inline in object.h */

PyTypeObject* PyType_FromSpec(const char *name, PyTypeObject *base) {
    PyTypeObject *type = (PyTypeObject *)calloc(1, sizeof(PyTypeObject));
    if (!type) return NULL;
    type->ob_base.ob_refcnt = 1;
    type->ob_base.ob_type = NULL;
    type->tp_name = name;
    type->tp_basicsize = base ? base->tp_basicsize : sizeof(PyObject);
    type->tp_base = base;
    return type;
}

/* ==================== CFunction ==================== */

typedef struct { PyObject ob_base; PyMethodDef *m_ml; PyObject *m_self; PyObject *m_module; } PyCFunctionObject;

static PyTypeObject _PyCFunction_Type = {
    1, NULL, "builtin_function_or_method", sizeof(PyCFunctionObject), 0,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL,
    NULL, NULL, NULL, Py_TPFLAGS_DEFAULT
};

PyObject* PyCFunction_NewEx(PyMethodDef *method, PyObject *self, PyObject *module) {
    PyCFunctionObject *op = (PyCFunctionObject *)PyObject_New(&_PyCFunction_Type);
    if (!op) return NULL;
    op->m_ml = method;
    op->m_self = self;
    op->m_module = module;
    return (PyObject *)op;
}
