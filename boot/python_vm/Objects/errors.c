/*
 * errors.c - UmerOS Python Error Handling
 *
 * Implementation of exception types and error indicators.
 * Singleton values (Py_None, Py_True, Py_False) are in their type files.
 */

#include "pyerrors.h"
#include <stdio.h>
#include <string.h>
#include <stdarg.h>
#include <stdlib.h>

/* ==================== GLOBAL EXCEPTIONS ==================== */

static PyObject _exc_base_exception       = { 1, NULL };
static PyObject _exc_exception            = { 1, NULL };
static PyObject _exc_stop_iteration       = { 1, NULL };
static PyObject _exc_error                = { 1, NULL };
static PyObject _exc_value_error          = { 1, NULL };
static PyObject _exc_type_error           = { 1, NULL };
static PyObject _exc_runtime_error        = { 1, NULL };
static PyObject _exc_name_error           = { 1, NULL };
static PyObject _exc_key_error            = { 1, NULL };
static PyObject _exc_index_error          = { 1, NULL };
static PyObject _exc_attribute_error      = { 1, NULL };
static PyObject _exc_zero_division_error  = { 1, NULL };
static PyObject _exc_memory_error         = { 1, NULL };
static PyObject _exc_overflow_error       = { 1, NULL };
static PyObject _exc_syntax_error         = { 1, NULL };
static PyObject _exc_import_error         = { 1, NULL };
static PyObject _exc_recursion_error      = { 1, NULL };
static PyObject _exc_not_implemented_error = { 1, NULL };

PyObject *PyExc_BaseException     = &_exc_base_exception;
PyObject *PyExc_Exception         = &_exc_exception;
PyObject *PyExc_StopIteration     = &_exc_stop_iteration;
PyObject *PyExc_Error             = &_exc_error;
PyObject *PyExc_ValueError        = &_exc_value_error;
PyObject *PyExc_TypeError         = &_exc_type_error;
PyObject *PyExc_RuntimeError      = &_exc_runtime_error;
PyObject *PyExc_NameError         = &_exc_name_error;
PyObject *PyExc_KeyError          = &_exc_key_error;
PyObject *PyExc_IndexError        = &_exc_index_error;
PyObject *PyExc_AttributeError    = &_exc_attribute_error;
PyObject *PyExc_ZeroDivisionError = &_exc_zero_division_error;
PyObject *PyExc_MemoryError       = &_exc_memory_error;
PyObject *PyExc_OverflowError     = &_exc_overflow_error;
PyObject *PyExc_SyntaxError       = &_exc_syntax_error;
PyObject *PyExc_ImportError       = &_exc_import_error;
PyObject *PyExc_RecursionError    = &_exc_recursion_error;
PyObject *PyExc_NotImplementedError = &_exc_not_implemented_error;

/* ==================== ERROR INDICATOR ==================== */

static PyObject *cur_exc_type    = NULL;
static PyObject *cur_exc_value   = NULL;
static char      cur_exc_msg[1024] = "";

PyObject* PyErr_Occurred(void) {
    return cur_exc_type;
}

void PyErr_Clear(void) {
    cur_exc_type  = NULL;
    cur_exc_value = NULL;
    cur_exc_msg[0] = '\0';
}

void PyErr_SetString(PyObject *type, const char *message) {
    cur_exc_type = type;
    strncpy(cur_exc_msg, message, sizeof(cur_exc_msg) - 1);
    cur_exc_msg[sizeof(cur_exc_msg) - 1] = '\0';
}

void PyErr_SetObject(PyObject *type, PyObject *value) {
    cur_exc_type  = type;
    cur_exc_value = value;
}

void PyErr_Format(PyObject *type, const char *fmt, ...) {
    va_list args;
    va_start(args, fmt);
    vsnprintf(cur_exc_msg, sizeof(cur_exc_msg), fmt, args);
    va_end(args);
    cur_exc_type = type;
}

/* ==================== CONVENIENCE ERROR SETTERS ==================== */

void PyErr_SetString_TypeError(const char *msg)    { PyErr_SetString(PyExc_TypeError, msg); }
void PyErr_SetString_ValueError(const char *msg)   { PyErr_SetString(PyExc_ValueError, msg); }
void PyErr_SetString_RuntimeError(const char *msg) { PyErr_SetString(PyExc_RuntimeError, msg); }
void PyErr_SetString_NameError(const char *msg)    { PyErr_SetString(PyExc_NameError, msg); }
void PyErr_SetString_KeyError(const char *msg)     { PyErr_SetString(PyExc_KeyError, msg); }
void PyErr_SetString_IndexError(const char *msg)   { PyErr_SetString(PyExc_IndexError, msg); }
void PyErr_SetString_AttributeError(const char *msg) { PyErr_SetString(PyExc_AttributeError, msg); }
void PyErr_SetString_ZeroDivisionError(const char *msg) { PyErr_SetString(PyExc_ZeroDivisionError, msg); }
void PyErr_SetString_MemoryError(const char *msg)  { PyErr_SetString(PyExc_MemoryError, msg); }
void PyErr_SetString_OverflowError(const char *msg) { PyErr_SetString(PyExc_OverflowError, msg); }
void PyErr_SetString_SyntaxError(const char *msg)  { PyErr_SetString(PyExc_SyntaxError, msg); }
void PyErr_SetString_ImportError(const char *msg)  { PyErr_SetString(PyExc_ImportError, msg); }
void PyErr_SetString_RecursionError(const char *msg) { PyErr_SetString(PyExc_RecursionError, msg); }
void PyErr_SetString_NotImplementedError(const char *msg) { PyErr_SetString(PyExc_NotImplementedError, msg); }

/* ==================== EXCEPTION CREATION ==================== */

PyObject* PyErr_NewException(const char *name, PyObject *base, PyObject *dict) {
    (void)name; (void)base; (void)dict;
    PyObject *exc = (PyObject *)calloc(1, sizeof(PyObject));
    if (exc) {
        exc->ob_refcnt = 1;
    }
    return exc;
}
