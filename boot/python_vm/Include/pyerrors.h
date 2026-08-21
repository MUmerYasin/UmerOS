/*
 * pyerrors.h - UmerOS Python Error Handling
 */

#ifndef UMEROS_PYERRORS_H
#define UMEROS_PYERRORS_H

#include "object.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ==================== EXCEPTION TYPES ==================== */

extern PyObject *PyExc_BaseException;
extern PyObject *PyExc_Exception;
extern PyObject *PyExc_StopIteration;
extern PyObject *PyExc_TypeError;
extern PyObject *PyExc_ValueError;
extern PyObject *PyExc_IndexError;
extern PyObject *PyExc_KeyError;
extern PyObject *PyExc_NameError;
extern PyObject *PyExc_AttributeError;
extern PyObject *PyExc_RuntimeError;
extern PyObject *PyExc_SyntaxError;
extern PyObject *PyExc_ImportError;
extern PyObject *PyExc_MemoryError;
extern PyObject *PyExc_ZeroDivisionError;
extern PyObject *PyExc_OSError;
extern PyObject *PyExc_IOError;
extern PyObject *PyExc_FileNotFoundError;
extern PyObject *PyExc_OverflowError;
extern PyObject *PyExc_SystemError;

/* ==================== ERROR FUNCTIONS ==================== */

void PyErrors_Init(void);
void PyErr_SetString(PyObject *type, const char *message);
void PyErr_SetObject(PyObject *type, PyObject *value);
void PyErr_Format(PyObject *type, const char *format, ...);
PyObject* PyErr_Occurred(void);
PyObject* PyErr_ExceptionMatches(PyObject *exc);
void PyErr_Print(void);
void PyErr_Clear(void);
void PyErr_NormalizeException(PyObject **exc, PyObject **val, PyObject **tb);

#ifdef __cplusplus
}
#endif

#endif /* UMEROS_PYERRORS_H */
