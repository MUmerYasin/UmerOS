/*
 * object.h - UmerOS Python Object System
 *
 * Core types: PyObject, PyVarObject, PyTypeObject,
 * PyThreadState, PyFrameObject, PyCodeObject.
 * This is the FOUNDATION header - all others depend on it.
 */

#ifndef UMEROS_OBJECT_H
#define UMEROS_OBJECT_H

#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ==================== TYPEDEFS ==================== */

typedef intptr_t Py_ssize_t;
typedef struct _object PyObject;
typedef struct _typeobject PyTypeObject;
typedef struct _codeobject PyCodeObject;
typedef struct _frameobject PyFrameObject;
typedef struct _threadstate PyThreadState;

/* ==================== BASE OBJECT ==================== */

struct _object {
    Py_ssize_t ob_refcnt;
    PyTypeObject *ob_type;
};

#define PyObject_HEAD     PyObject ob_base
#define PyObject_HEAD_INIT(type)  { 1, (type) }

/* ==================== VARIABLE-SIZE OBJECT ==================== */

typedef struct {
    PyObject ob_base;
    Py_ssize_t ob_size;
} PyVarObject;

#define PyVarObject_HEAD(type, size)  { { 1, (type) }, (size) }

/* ==================== TYPE OBJECT ==================== */

struct _typeobject {
    PyObject ob_base;

    const char *tp_name;
    Py_ssize_t tp_basicsize;
    Py_ssize_t tp_itemsize;

    void (*tp_dealloc)(PyObject *);
    PyObject *(*tp_getattr)(PyObject *, const char *);
    int (*tp_setattr)(PyObject *, const char *, PyObject *);

    PyObject *(*tp_repr)(PyObject *);
    PyObject *(*tp_str)(PyObject *);

    /* Numeric */
    PyObject *(*tp_add)(PyObject *, PyObject *);
    PyObject *(*tp_subtract)(PyObject *, PyObject *);
    PyObject *(*tp_multiply)(PyObject *, PyObject *);
    PyObject *(*tp_divide)(PyObject *, PyObject *);
    PyObject *(*tp_modulo)(PyObject *, PyObject *);
    PyObject *(*tp_neg)(PyObject *);
    PyObject *(*tp_pos)(PyObject *);
    PyObject *(*tp_abs)(PyObject *);
    int (*tp_bool)(PyObject *);

    int (*tp_compare)(PyObject *, PyObject *);
    long (*tp_hash)(PyObject *);
    PyObject *(*tp_call)(PyObject *, PyObject *, PyObject *);

    uint64_t tp_flags;
    const char *tp_doc;
};

/* Type flags */
#define TPFLAGS_DEFAULT 0

/* ==================== REFERENCE COUNTING ==================== */

static inline void Py_INCREF(PyObject *op) {
    op->ob_refcnt++;
}

static inline void Py_DECREF(PyObject *op) {
    if (op && --op->ob_refcnt == 0) {
        if (op->ob_type && op->ob_type->tp_dealloc) {
            op->ob_type->tp_dealloc(op);
        }
    }
}

static inline void Py_XDECREF(PyObject *op) {
    if (op) {
        Py_DECREF(op);
    }
}

/* ==================== TYPE CHECKS ==================== */

#define Py_TYPE(op) ((op)->ob_type)

/* ==================== THREAD STATE ==================== */

struct _threadstate {
    PyObject *exc_type;
    PyObject *exc_value;
    PyObject *exc_traceback;
    int pending;
    int recursion_depth;
    int recursion_limit;
    PyFrameObject *frame;
};

extern PyThreadState _current_thread;

PyThreadState* PyThreadState_Get(void);

/* ==================== FRAME OBJECT ==================== */

struct _frameobject {
    PyObject ob_base;

    PyCodeObject *f_code;
    PyObject *f_globals;
    PyObject *f_locals;

    PyObject **f_stack;
    PyObject **f_stacktop;

    int f_lasti;
    int f_block_top;

    PyFrameObject *f_back;
};

PyFrameObject* PyFrame_New(PyCodeObject *code, PyObject *globals, PyObject *locals);
void PyFrame_Free(PyFrameObject *frame);
PyObject* PyFrame_GetLocal(PyFrameObject *frame, const char *name);
void PyFrame_SetLocal(PyFrameObject *frame, const char *name, PyObject *value);
PyObject* PyFrame_GetGlobal(PyFrameObject *frame, const char *name);

/* Thread frame management */
void PyThreadState_PushFrame(PyThreadState *tstate, PyFrameObject *frame);
PyFrameObject* PyThreadState_PopFrame(PyThreadState *tstate);

/* ==================== CODE OBJECT ==================== */

struct _codeobject {
    PyObject ob_base;

    uint8_t *code;
    Py_ssize_t code_size;

    PyObject **consts;
    Py_ssize_t n_consts;

    PyObject **names;
    Py_ssize_t n_names;

    const char *filename;
    const char *name;
    int argcount;
    int flags;
};

PyCodeObject* PyCode_New(uint8_t *code, Py_ssize_t code_size,
                         PyObject **consts, Py_ssize_t n_consts);
void PyCode_Free(PyCodeObject *code);

/* ==================== DICT ==================== */

PyObject* PyDict_New(void);
int PyDict_SetItem(PyObject *dict, PyObject *key, PyObject *value);
PyObject* PyDict_GetItem(PyObject *dict, PyObject *key);
int PyDict_SetItemString(PyObject *dict, const char *key, PyObject *value);
PyObject* PyDict_GetItemString(PyObject *dict, const char *key);

/* ==================== LIST ==================== */

PyObject* PyList_New(Py_ssize_t size);
Py_ssize_t PyList_Size(PyObject *list);
PyObject* PyList_GetItem(PyObject *list, Py_ssize_t index);
int PyList_SetItem(PyObject *list, Py_ssize_t index, PyObject *value);

/* ==================== TUPLE ==================== */

PyObject* PyTuple_New(Py_ssize_t size);
Py_ssize_t PyTuple_Size(PyObject *tuple);
PyObject* PyTuple_GetItem(PyObject *tuple, Py_ssize_t index);
int PyTuple_SetItem(PyObject *tuple, Py_ssize_t index, PyObject *value);

/* ==================== LONG ==================== */

PyObject* PyLong_FromLong(long value);
long PyLong_AsLong(PyObject *obj);

/* ==================== FLOAT ==================== */

PyObject* PyFloat_FromDouble(double value);
double PyFloat_AsDouble(PyObject *obj);

/* ==================== UNICODE (STRING) ==================== */

PyObject* PyUnicode_FromString(const char *str);
PyObject* PyUnicode_FromStringAndSize(const char *str, Py_ssize_t size);
const char* PyUnicode_AsString(PyObject *obj);
const char* PyUnicode_AsStringAndSize(PyObject *obj, Py_ssize_t *size);
Py_ssize_t PyUnicode_GetSize(PyObject *obj);
PyObject* PyUnicode_FromFormat(const char *format, ...);

static inline int PyUnicode_Check(PyObject *op) {
    return op && op->ob_type && op->ob_type->tp_str != NULL;
}

/* ==================== BOOL ==================== */

extern PyObject *Py_True;
extern PyObject *Py_False;
extern PyObject *Py_None;

PyObject* PyBool_FromLong(long value);

static inline int PyBool_Check(PyObject *op) {
    return (op == Py_True || op == Py_False);
}

/* ==================== NONE ==================== */

static inline int Py_None_Check(PyObject *op) {
    return op == Py_None;
}

/* ==================== NUMBER OPERATIONS ==================== */

PyObject* PyNumber_Add(PyObject *left, PyObject *right);
PyObject* PyNumber_Subtract(PyObject *left, PyObject *right);
PyObject* PyNumber_Multiply(PyObject *left, PyObject *right);
PyObject* PyNumber_TrueDivide(PyObject *left, PyObject *right);
PyObject* PyNumber_FloorDivide(PyObject *left, PyObject *right);
PyObject* PyNumber_Remainder(PyObject *left, PyObject *right);
PyObject* PyNumber_Power(PyObject *base, PyObject *exp, PyObject *mod);
PyObject* PyNumber_Negative(PyObject *op);
PyObject* PyNumber_Positive(PyObject *op);
PyObject* PyNumber_Absolute(PyObject *op);

/* ==================== OBJECT GENERIC ==================== */

PyObject* PyObject_Str(PyObject *op);
PyObject* PyObject_Repr(PyObject *op);
int PyObject_IsTrue(PyObject *op);
Py_ssize_t PyObject_Hash(PyObject *op);
int PyObject_Compare(PyObject *a, PyObject *b);
PyObject* PyObject_Call(PyObject *callable, PyObject *args, PyObject *kwargs);
PyObject* PyObject_GetAttr(PyObject *op, PyObject *name);
int PyObject_SetAttr(PyObject *op, PyObject *name, PyObject *value);
int PyCallable_Check(PyObject *op);

/* ==================== TYPE ==================== */

int PyType_Ready(PyTypeObject *type);
int PyType_IsSubtype(PyTypeObject *a, PyTypeObject *b);

/* ==================== OBJECT ALLOCATION ==================== */

PyObject* PyObject_New(PyTypeObject *type);
PyObject* PyObject_NewVar(PyTypeObject *type, Py_ssize_t size);
void PyObject_Free(PyObject *op);

/* ==================== SEQUENCE ==================== */

Py_ssize_t PySequence_Size(PyObject *seq);
PyObject* PySequence_GetItem(PyObject *seq, Py_ssize_t i);
int PySequence_Contains(PyObject *seq, PyObject *item);

/* ==================== ITERATOR ==================== */

int PyIter_Check(PyObject *op);
PyObject* PyIter_Next(PyObject *iter);

/* ==================== IMPORT ==================== */

PyObject* PyImport_ImportModule(const char *name);

#ifdef __cplusplus
}
#endif

#endif /* UMEROS_OBJECT_H */
