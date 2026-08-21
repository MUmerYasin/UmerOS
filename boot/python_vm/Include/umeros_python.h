/*
 * umeros_python.h - UmerOS Python 3.x Core Interpreter
 *
 * Master header: includes all sub-headers in correct dependency order.
 */

#ifndef UMEROS_PYTHON_H
#define UMEROS_PYTHON_H

#include "object.h"
#include "pycode.h"
#include "pyast.h"
#include "pytoken.h"
#include "pyerrors.h"
#include "pyvm.h"

#ifdef __cplusplus
extern "C" {
#endif

/* Version info */
#define UMEROS_PYTHON_MAJOR 3
#define UMEROS_PYTHON_MINOR 14
#define UMEROS_PYTHON_PATCH 0

/* Initialization */
void Py_Initialize(void);
void Py_Finalize(void);
int Py_IsInitialized(void);

/* Main execution */
int PyRun_SimpleString(const char *command);

/* Reference counting helpers */
static inline void Py_XDECREF(PyObject *op) {
    if (op != NULL) {
        Py_DECREF(op);
    }
}

static inline void Py_XINCREF(PyObject *op) {
    if (op != NULL) {
        Py_INCREF(op);
    }
}

#ifdef __cplusplus
}
#endif

#endif /* UMEROS_PYTHON_H */
