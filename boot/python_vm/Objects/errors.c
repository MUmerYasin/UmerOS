/*
 * errors.c - UmerOS Python Error System
 */

#include "../Include/umeros_python.h"

/* Exception type objects */
typedef struct {
    PyObject ob_base;
    PyObject *args;
    PyObject *cause;
    PyObject *traceback;
    char *message;
} PyExceptionObject;

/* Base exception type */
static PyTypeObject PyBaseException_Type;

/* Exception type objects */
static PyObject _PyExc_BaseException_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_Exception_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_StopIteration_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_TypeError_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_ValueError_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_IndexError_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_KeyError_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_NameError_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_AttributeError_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_RuntimeError_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_SyntaxError_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_ImportError_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_MemoryError_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_ZeroDivisionError_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_OSError_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_IOError_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_FileNotFoundError_struct = { .ob_refcnt = 1, .ob_type = NULL };
static PyObject _PyExc_OverflowError_struct = { .ob_refcnt = 1, .ob_type = NULL };

PyObject *PyExc_BaseException = &_PyExc_BaseException_struct;
PyObject *PyExc_Exception = &_PyExc_Exception_struct;
PyObject *PyExc_StopIteration = &_PyExc_StopIteration_struct;
PyObject *PyExc_TypeError = &_PyExc_TypeError_struct;
PyObject *PyExc_ValueError = &_PyExc_ValueError_struct;
PyObject *PyExc_IndexError = &_PyExc_IndexError_struct;
PyObject *PyExc_KeyError = &_PyExc_KeyError_struct;
PyObject *PyExc_NameError = &_PyExc_NameError_struct;
PyObject *PyExc_AttributeError = &_PyExc_AttributeError_struct;
PyObject *PyExc_RuntimeError = &_PyExc_RuntimeError_struct;
PyObject *PyExc_SyntaxError = &_PyExc_SyntaxError_struct;
PyObject *PyExc_ImportError = &_PyExc_ImportError_struct;
PyObject *PyExc_MemoryError = &_PyExc_MemoryError_struct;
PyObject *PyExc_ZeroDivisionError = &_PyExc_ZeroDivisionError_struct;
PyObject *PyExc_OSError = &_PyExc_OSError_struct;
PyObject *PyExc_IOError = &_PyExc_IOError_struct;
PyObject *PyExc_FileNotFoundError = &_PyExc_FileNotFoundError_struct;
PyObject *PyExc_OverflowError = &_PyExc_OverflowError_struct;

/* Exception type name map */
static struct { PyObject **type; const char *name; } exception_types[] = {
    { &PyExc_BaseException, "BaseException" },
    { &PyExc_Exception, "Exception" },
    { &PyExc_StopIteration, "StopIteration" },
    { &PyExc_TypeError, "TypeError" },
    { &PyExc_ValueError, "ValueError" },
    { &PyExc_IndexError, "IndexError" },
    { &PyExc_KeyError, "KeyError" },
    { &PyExc_NameError, "NameError" },
    { &PyExc_AttributeError, "AttributeError" },
    { &PyExc_RuntimeError, "RuntimeError" },
    { &PyExc_SyntaxError, "SyntaxError" },
    { &PyExc_ImportError, "ImportError" },
    { &PyExc_MemoryError, "MemoryError" },
    { &PyExc_ZeroDivisionError, "ZeroDivisionError" },
    { &PyExc_OSError, "OSError" },
    { &PyExc_IOError, "IOError" },
    { &PyExc_FileNotFoundError, "FileNotFoundError" },
    { &PyExc_OverflowError, "OverflowError" },
    { NULL, NULL }
};

/* Initialize exception types */
void PyErrors_Init(void) {
    for (int i = 0; exception_types[i].type != NULL; i++) {
        (*exception_types[i].type)->ob_type = &PyBaseException_Type;
    }
}

/* Set a string exception */
void PyErr_SetString(PyObject *type, const char *message) {
    _current_thread.exc_type = type;
    _current_thread.exc_value = PyUnicode_FromString(message);
    _current_thread.pending = 1;
}

/* Set an object exception */
void PyErr_SetObject(PyObject *type, PyObject *value) {
    _current_thread.exc_type = type;
    _current_thread.exc_value = value;
    _current_thread.pending = 1;
}

/* Format and set an exception */
void PyErr_Format(PyObject *type, const char *format, ...) {
    char buffer[1024];
    va_list args;
    va_start(args, format);
    vsnprintf(buffer, sizeof(buffer), format, args);
    va_end(args);
    PyErr_SetString(type, buffer);
}

/* Check if exception is set */
PyObject* PyErr_Occurred(void) {
    if (_current_thread.pending) {
        return _current_thread.exc_type;
    }
    return NULL;
}

/* Check if exception matches */
PyObject* PyErr_ExceptionMatches(PyObject *exc) {
    if (!_current_thread.pending) return NULL;
    if (_current_thread.exc_type == exc) return exc;
    return NULL;
}

/* Print exception to stderr */
void PyErr_Print(void) {
    if (!_current_thread.pending) return;

    PyObject *exc_type = _current_thread.exc_type;
    PyObject *exc_value = _current_thread.exc_value;

    if (exc_type && exc_value) {
        const char *type_name = "UnknownException";
        for (int i = 0; exception_types[i].type != NULL; i++) {
            if (*exception_types[i].type == exc_type) {
                type_name = exception_types[i].name;
                break;
            }
        }

        const char *message = PyUnicode_AsString(exc_value);
        if (message) {
            fprintf(stderr, "%s: %s\n", type_name, message);
        } else {
            fprintf(stderr, "%s\n", type_name);
        }
    }

    PyErr_Clear();
}

/* Clear the current exception */
void PyErr_Clear(void) {
    _current_thread.exc_type = NULL;
    _current_thread.exc_value = NULL;
    _current_thread.exc_traceback = NULL;
    _current_thread.pending = 0;
}

/* Normalize exception */
void PyErr_NormalizeException(PyObject **exc, PyObject **val, PyObject **tb) {
    (void)exc; (void)val; (void)tb;
    /* No-op for now */
}

/* Exception type object (simplified) */
static PyTypeObject PyBaseException_Type = {
    PyObject_HEAD_INIT(NULL)
    .tp_name = "BaseException",
    .tp_basicsize = sizeof(PyObject),
    .tp_flags = TPFLAGS_DEFAULT,
    .tp_doc = "Base exception type"
};
