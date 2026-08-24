/*
 * object.h - UmerOS Python Object System
 *
 * The foundation of the entire Python VM.
 * Every value is a PyObject. Types are objects too.
 */

#ifndef UMEROS_OBJECT_H
#define UMEROS_OBJECT_H

#include <stdint.h>
#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

/* ==================== BASIC TYPES ==================== */

typedef int64_t Py_ssize_t;
typedef size_t  PyObjectHash;

/* Type tag used during debugging */
#define PyObject_HEAD             \
    Py_ssize_t ob_refcnt;        \
    struct _typeobject *ob_type

#define PyObject_HEAD_INIT(type)  \
    1, (type)

#define Py_REFCNT(op)             ((op)->ob_refcnt)
#define Py_TYPE(op)               ((op)->ob_type)
#define Py_SIZE(op)               (0) /* stub */

#define Py_INCREF(op)             ((op)->ob_refcnt++)
#define Py_DECREF(op)             do { if (--(op)->ob_refcnt == 0) Py_Dealloc(op); } while(0)
#define Py_XINCREF(op)            if (op) Py_INCREF(op)
#define Py_XDECREF(op)            if (op) Py_DECREF(op)

/* Forward declarations */
typedef struct _object PyObject;
typedef struct _typeobject PyTypeObject;
typedef struct _varobject PyVarObject;
typedef struct _codeobject PyCodeObject;
typedef struct _frame PyFrameObject;
typedef struct _threadstate PyThreadState;

/* ==================== TYPE FLAGS ==================== */

#define Py_TPFLAGS_DEFAULT       (1UL << 0)
#define Py_TPFLAGS_BASETYPE      (1UL << 1)
#define Py_TPFLAGS_HAVE_GC       (1UL << 2)
#define Py_TPFLAGS_NUMBER        (1UL << 3)
#define Py_TPFLAGS_SEQUENCE      (1UL << 4)
#define Py_TPFLAGS_MAPPING       (1UL << 5)
#define Py_TPFLAGS_IMMUTABLETYPE (1UL << 6)
#define Py_TPFLAGS_UNICODE_SUBCLASS  (1UL << 7)
#define Py_TPFLAGS_LONG_SUBCLASS     (1UL << 8)
#define Py_TPFLAGS_LIST_SUBCLASS     (1UL << 9)
#define Py_TPFLAGS_TUPLE_SUBCLASS    (1UL << 10)
#define Py_TPFLAGS_DICT_SUBCLASS     (1UL << 11)
#define Py_TPFLAGS_BYTES_SUBCLASS    (1UL << 12)
#define Py_TPFLAGS_FLOAT_SUBCLASS    (1UL << 13)
#define Py_TPFLAGS_BOOL_SUBCLASS     (1UL << 14)

/* ==================== OBJECT STRUCTURE ==================== */

struct _object {
    PyObject_HEAD;
};

/* ==================== VAR OBJECT ==================== */

struct _varobject {
    PyObject ob_base;
    Py_ssize_t ob_size;
};

/* ==================== CODE OBJECT ==================== */

struct _codeobject {
    PyObject ob_base;
    uint8_t *code;
    Py_ssize_t code_size;
    PyObject **consts;
    Py_ssize_t n_consts;
    char **names;
    Py_ssize_t n_names;
    const char *filename;
    const char *name;
    int argcount;
    int flags;
};

/* ==================== FRAME OBJECT ==================== */

struct _frame {
    PyObject ob_base;
    PyCodeObject *f_code;
    PyObject *f_globals;
    PyObject *f_locals;
    struct _frame *f_back;
    Py_ssize_t f_lasti;
    Py_ssize_t f_block_top;
    PyObject **f_stacktop;
};

/* ==================== THREAD STATE ==================== */

struct _threadstate {
    PyFrameObject *frame;
    Py_ssize_t recursion_depth;
    int pending;
    PyObject *exc_type;
    PyObject *exc_value;
    PyObject *exc_traceback;
};

/* ==================== TYPE OBJECT ==================== */

struct _typeobject {
    PyObject_HEAD;
    const char *tp_name;
    Py_ssize_t tp_basicsize;
    Py_ssize_t tp_itemsize;

    /* Construction / destruction */
    PyObject* (*tp_new)(PyTypeObject *type, PyObject *args, PyObject *kwargs);
    void      (*tp_dealloc)(PyObject *self);

    /* String representations */
    PyObject* (*tp_repr)(PyObject *self);
    PyObject* (*tp_str)(PyObject *self);

    /* Rich comparison */
    PyObject* (*tp_richcompare)(PyObject *self, PyObject *other, int op);

    /* Hash and bool */
    PyObjectHash (*tp_hash)(PyObject *self);
    int       (*tp_bool)(PyObject *self);

    /* Number protocol */
    PyObject* (*tp_add)(PyObject *a, PyObject *b);
    PyObject* (*tp_subtract)(PyObject *a, PyObject *b);
    PyObject* (*tp_multiply)(PyObject *a, PyObject *b);
    PyObject* (*tp_true_divide)(PyObject *a, PyObject *b);
    PyObject* (*tp_floor_divide)(PyObject *a, PyObject *b);
    PyObject* (*tp_remainder)(PyObject *a, PyObject *b);
    PyObject* (*tp_power)(PyObject *a, PyObject *b);
    PyObject* (*tp_negative)(PyObject *self);
    PyObject* (*tp_positive)(PyObject *self);
    PyObject* (*tp_absolute)(PyObject *self);
    PyObject* (*tp_and)(PyObject *a, PyObject *b);
    PyObject* (*tp_xor)(PyObject *a, PyObject *b);
    PyObject* (*tp_or)(PyObject *a, PyObject *b);
    PyObject* (*tp_lshift)(PyObject *a, PyObject *b);
    PyObject* (*tp_rshift)(PyObject *a, PyObject *b);

    /* Sequence protocol */
    Py_ssize_t (*tp_length)(PyObject *self);
    PyObject* (*tp_concat)(PyObject *self, PyObject *other);
    PyObject* (*tp_repeat)(PyObject *self, Py_ssize_t n);
    PyObject* (*tp_item)(PyObject *self, Py_ssize_t index);

    /* Attribute access */
    PyObject* (*tp_getattro)(PyObject *self, PyObject *name);
    int       (*tp_setattro)(PyObject *self, PyObject *name, PyObject *value);

    /* Call protocol */
    PyObject* (*tp_call)(PyObject *self, PyObject *args, PyObject *kwargs);

    /* Base type */
    PyTypeObject *tp_base;

    /* Flags */
    uint32_t tp_flags;
};

/* ==================== ALLOCATION ==================== */

PyObject* PyObject_New(PyTypeObject *type);
void      Py_Dealloc(PyObject *self);
void      PyObject_Print(PyObject *self);

/* ==================== TYPE CHECKING ==================== */

static inline int PyType_IsSubtype(PyTypeObject *a, PyTypeObject *b) {
    while (a) {
        if (a == b) return 1;
        a = a->tp_base;
    }
    return 0;
}

#define PyObject_TypeCheck(op, tp) \
    (Py_TYPE(op) == (tp) || PyType_IsSubtype(Py_TYPE(op), (tp)))

/* Type-specific check macros (static inline to avoid duplicate symbols) */
static inline int PyLong_Check(PyObject *op) {
    return op && op->ob_type && (op->ob_type->tp_flags & Py_TPFLAGS_LONG_SUBCLASS);
}

static inline int PyFloat_Check(PyObject *op) {
    return op && op->ob_type && (op->ob_type->tp_flags & Py_TPFLAGS_FLOAT_SUBCLASS);
}

static inline int PyUnicode_Check(PyObject *op) {
    return op && op->ob_type && (op->ob_type->tp_flags & Py_TPFLAGS_UNICODE_SUBCLASS);
}

static inline int PyBool_Check(PyObject *op) {
    return op && op->ob_type && (op->ob_type->tp_flags & Py_TPFLAGS_BOOL_SUBCLASS);
}

static inline int PyList_Check(PyObject *op) {
    return op && op->ob_type && (op->ob_type->tp_flags & Py_TPFLAGS_LIST_SUBCLASS);
}

static inline int PyTuple_Check(PyObject *op) {
    return op && op->ob_type && (op->ob_type->tp_flags & Py_TPFLAGS_TUPLE_SUBCLASS);
}

static inline int PyDict_Check(PyObject *op) {
    return op && op->ob_type && (op->ob_type->tp_flags & Py_TPFLAGS_DICT_SUBCLASS);
}

static inline int Py_None_Check(PyObject *op) {
    extern PyTypeObject PyNone_Type;
    return op && op->ob_type == &PyNone_Type;
}

static inline int PyCallable_Check(PyObject *op) {
    return op && op->ob_type && op->ob_type->tp_call;
}

static inline int Py_IsTrue(PyObject *op) {
    extern PyObject *Py_True;
    return op == Py_True;
}

static inline int Py_IsFalse(PyObject *op) {
    extern PyObject *Py_False;
    return op == Py_False;
}

static inline int Py_IS_SUBCLASS(PyObject *derived, PyObject *base) {
    if (!derived || !base) return 0;
    return PyType_IsSubtype((PyTypeObject *)derived, (PyTypeObject *)base);
}

/* ==================== C FUNCTION TYPE ==================== */

typedef PyObject* (*PyCFunction)(PyObject *self, PyObject *args);
typedef PyObject* (*PyCFunctionWithKeywords)(PyObject *self, PyObject *args, PyObject *kwargs);

typedef struct {
    PyCFunction ml_meth;
    int         ml_flags;
    const char *ml_name;
} PyMethodDef;

#define PyCFunction_New(method, self) PyCFunction_NewEx(method, self, NULL)
PyObject* PyCFunction_NewEx(PyMethodDef *method, PyObject *self, PyObject *module);

/* ==================== COMPARISON ==================== */

#define Py_LT 0
#define Py_LE 1
#define Py_EQ 2
#define Py_NE 3
#define Py_GT 4
#define Py_GE 5
#define Py_Is(a, b) ((a) == (b))

PyObject* PyObject_RichCompare(PyObject *v, PyObject *w, int op);
int       PyObject_IsTrue(PyObject *v);
int       PyObject_Not(PyObject *v);
int       PyObject_Compare(PyObject *a, PyObject *b);

/* ==================== CONVERSION ==================== */

PyObject* PyNumber_Long(PyObject *o);
PyObject* PyNumber_Float(PyObject *o);
PyObject* PyNumber_Index(PyObject *o);

/* ==================== NUMBER PROTOCOL ==================== */

PyObject* PyNumber_Add(PyObject *v, PyObject *w);
PyObject* PyNumber_Subtract(PyObject *v, PyObject *w);
PyObject* PyNumber_Multiply(PyObject *v, PyObject *w);
PyObject* PyNumber_TrueDivide(PyObject *v, PyObject *w);
PyObject* PyNumber_FloorDivide(PyObject *v, PyObject *w);
PyObject* PyNumber_Remainder(PyObject *v, PyObject *w);
PyObject* PyNumber_Power(PyObject *v, PyObject *w);
PyObject* PyNumber_Negative(PyObject *v);
PyObject* PyNumber_Positive(PyObject *v);
PyObject* PyNumber_Absolute(PyObject *v);

/* ==================== SEQUENCE PROTOCOL ==================== */

Py_ssize_t PyObject_Length(PyObject *o);
PyObject*  PySequence_Concat(PyObject *s, PyObject *o);
PyObject*  PySequence_Repeat(PyObject *o, Py_ssize_t count);
PyObject*  PySequence_GetItem(PyObject *s, Py_ssize_t i);

/* ==================== TYPE-SPECIFIC GETTERS ==================== */

long    PyLong_AsLong(PyObject *obj);
double  PyFloat_AsDouble(PyObject *obj);
int     PyBool_AsLong(PyObject *obj);

/* ==================== STRING REPR ==================== */

const char* PyUnicode_AsString(PyObject *obj);
PyObject*   PyUnicode_FromString(const char *u);
PyObject*   PyUnicode_FromFormat(const char *fmt, ...);

/* ==================== LIST PROTOCOL ==================== */

PyObject*  PyList_New(Py_ssize_t size);
Py_ssize_t PyList_Size(PyObject *list);
PyObject*  PyList_GetItem(PyObject *list, Py_ssize_t i);
int        PyList_Append(PyObject *list, PyObject *item);

/* ==================== TUPLE PROTOCOL ==================== */

PyObject*  PyTuple_New(Py_ssize_t size);
Py_ssize_t PyTuple_Size(PyObject *tuple);
PyObject*  PyTuple_GetItem(PyObject *tuple, Py_ssize_t i);

/* ==================== DICT PROTOCOL ==================== */

int        PyDict_SetItem(PyObject *dict, PyObject *key, PyObject *value);
int        PyDict_SetItemString(PyObject *dict, const char *key, PyObject *value);
PyObject*  PyDict_GetItemString(PyObject *dict, const char *key);
PyObject*  PyDict_Keys(PyObject *dict);
Py_ssize_t PyDict_Size(PyObject *dict);
int        PyDict_Next(PyObject *dict, Py_ssize_t *pos, PyObject **key, PyObject **value);

/* ==================== NEEDED FORWARD DECS ==================== */

PyTypeObject* PyType_FromSpec(const char *name, PyTypeObject *base);

/* Known type objects */
extern PyTypeObject PyLong_Type;
extern PyTypeObject PyFloat_Type;
extern PyTypeObject PyUnicode_Type;
extern PyTypeObject PyBool_Type;
extern PyTypeObject PyList_Type;
extern PyTypeObject PyTuple_Type;
extern PyTypeObject PyDict_Type;
extern PyTypeObject PyNone_Type;
extern PyTypeObject PyFunction_Type;
extern PyTypeObject PyModule_Type;

/* ==================== CONSTRUCTOR DECLARATIONS ==================== */

PyObject* PyLong_FromLong(long ival);
PyObject* PyFloat_FromDouble(double ival);
PyObject* PyUnicode_FromStringAndSize(const char *u, Py_ssize_t size);
PyObject* PyBool_FromLong(long ival);
Py_ssize_t PyUnicode_GetLength(PyObject *op);

/* ==================== DICT FUNCTIONS ==================== */

PyObject*  PyDict_New(void);
PyObject*  PyDict_GetItem(PyObject *dict, PyObject *key);
int        PyDict_Contains(PyObject *dict, PyObject *key);
PyObject*  PyDict_GetItemString(PyObject *dict, const char *key);

/* ==================== LIST/TUPLE SETITEM ==================== */

int PyList_SetItem(PyObject *list, Py_ssize_t i, PyObject *item);
int PyTuple_SetItem(PyObject *tuple, Py_ssize_t i, PyObject *item);

/* ==================== ITER PROTOCOL ==================== */

#define PyIter_Check(op) ((op)->ob_type && (op)->ob_type->tp_iternext != NULL)
PyObject* PyIter_Next(PyObject *iter);

/* ==================== SEQUENCE SIZE/CONTAINS ==================== */

Py_ssize_t PySequence_Size(PyObject *s);
int        PySequence_Contains(PyObject *s, PyObject *o);

/* ==================== IMPORT ==================== */

PyObject* PyImport_ImportModule(const char *name);

/* ==================== REPR/STR/TYPE/HASH ==================== */

PyObject* PyObject_Str(PyObject *obj);
PyObject* PyObject_Repr(PyObject *obj);
PyObject* PyObject_Type(PyObject *obj);
PyObjectHash PyObject_Hash(PyObject *obj);

/* ==================== DELATTR ==================== */

int PyObject_DelAttr(PyObject *obj, PyObject *name);

/* ==================== DELITEM ==================== */

int PyObject_DelItem(PyObject *obj, PyObject *key);

#ifdef __cplusplus
}
#endif

#endif /* UMEROS_OBJECT_H */
