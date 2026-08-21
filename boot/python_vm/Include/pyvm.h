/*
 * pyvm.h - UmerOS Python Virtual Machine
 *
 * VM macros, helper functions, and evaluation declarations.
 */

#ifndef UMEROS_PYVM_H
#define UMEROS_PYVM_H

#include "object.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ==================== VM CONSTANTS ==================== */

#define VM_MAX_STACK_SIZE 8192
#define VM_MAX_BLOCK_DEPTH 256
#define MAX_VALUE_STACK   8192

/* Block types */
#define BLOCK_LOOP      0
#define BLOCK_TRY       1
#define BLOCK_WITH      2

/* ==================== EVALUATION ==================== */

PyObject* PyEval_EvalFrame(PyFrameObject *frame);
PyObject* PyEval_EvalCode(PyCodeObject *code, PyObject *globals, PyObject *locals);

/* ==================== VM HELPERS ==================== */

static inline void PyErr_SetPending(void) {
    _current_thread.pending = 1;
}

static inline int PyErr_HasPending(void) {
    return _current_thread.pending != 0;
}

static inline void PyErr_ClearPending(void) {
    _current_thread.pending = 0;
    _current_thread.exc_type = NULL;
    _current_thread.exc_value = NULL;
    _current_thread.exc_traceback = NULL;
}

#ifdef __cplusplus
}
#endif

#endif /* UMEROS_PYVM_H */
