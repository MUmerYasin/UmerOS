/*
 * pyerrors.h - UmerOS Python Error Handling
 *
 * Exceptions, error indicators, and exception manipulation.
 */

#ifndef UMEROS_PYERRORS_H
#define UMEROS_PYERRORS_H

#include "object.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ==================== GLOBAL EXCEPTIONS ==================== */

extern PyObject *PyExc_BaseException;
extern PyObject *PyExc_Exception;
extern PyObject *PyExc_StopIteration;
extern PyObject *PyExc_Error;
extern PyObject *PyExc_ValueError;
extern PyObject *PyExc_TypeError;
extern PyObject *PyExc_RuntimeError;
extern PyObject *PyExc_NameError;
extern PyObject *PyExc_KeyError;
extern PyObject *PyExc_IndexError;
extern PyObject *PyExc_AttributeError;
extern PyObject *PyExc_ZeroDivisionError;
extern PyObject *PyExc_MemoryError;
extern PyObject *PyExc_OverflowError;
extern PyObject *PyExc_SyntaxError;
extern PyObject *PyExc_ImportError;
extern PyObject *PyExc_RecursionError;
extern PyObject *PyExc_NotImplementedError;
extern PyObject *PyExc_SystemError;

/* ==================== ERROR INDICATOR ==================== */

extern PyObject *PyErr_Occurred(void);
extern void      PyErr_Clear(void);
extern void      PyErr_Print(void);
extern int       PyErr_ExceptionMatches(PyObject *exc);

extern void PyErr_SetString(PyObject *type, const char *message);
extern void PyErr_SetObject(PyObject *type, PyObject *value);
extern void PyErr_Format(PyObject *type, const char *fmt, ...);

/* Convenience error setters */
extern void PyErr_SetString_TypeError(const char *message);
extern void PyErr_SetString_ValueError(const char *message);
extern void PyErr_SetString_RuntimeError(const char *message);
extern void PyErr_SetString_NameError(const char *message);
extern void PyErr_SetString_KeyError(const char *message);
extern void PyErr_SetString_IndexError(const char *message);
extern void PyErr_SetString_AttributeError(const char *message);
extern void PyErr_SetString_ZeroDivisionError(const char *message);
extern void PyErr_SetString_MemoryError(const char *message);
extern void PyErr_SetString_OverflowError(const char *message);
extern void PyErr_SetString_SyntaxError(const char *message);
extern void PyErr_SetString_ImportError(const char *message);
extern void PyErr_SetString_RecursionError(const char *message);
extern void PyErr_SetString_NotImplementedError(const char *message);

/* ==================== STOP ITERATION ==================== */

extern PyObject *Py_None;
extern PyObject *Py_True;
extern PyObject *Py_False;
extern PyObject *Py_NotImplemented;
extern PyObject *Py_Ellipsis;

/* ==================== EXCEPTION CREATION ==================== */

PyObject* PyErr_NewException(const char *name, PyObject *base, PyObject *dict);

/* ==================== BACKWARD COMPAT (deprecated names) ==================== */

#define PyErr_SetString_RuntimeError PyErr_SetString_RuntimeError
#define PyErr_SetString_AttributeError PyErr_SetString_AttributeError

#ifdef __cplusplus
}
#endif

#endif /* UMEROS_PYERRORS_H */
