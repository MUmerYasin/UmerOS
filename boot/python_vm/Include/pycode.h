/*
 * pycode.h - UmerOS Python Code Object
 *
 * Opcodes and the PyCodeObject struct.
 */

#ifndef UMEROS_PYCODE_H
#define UMEROS_PYCODE_H

#include "object.h"

#ifdef __cplusplus
extern "C" {
#endif

/* ==================== OPCODES ==================== */

typedef enum {
    OP_LOAD_CONST = 1,
    OP_LOAD_NAME,
    OP_LOAD_GLOBAL,
    OP_STORE_NAME,
    OP_STORE_GLOBAL,
    OP_POP_TOP,
    OP_BINARY_ADD,
    OP_BINARY_SUBTRACT,
    OP_BINARY_MULTIPLY,
    OP_BINARY_TRUE_DIVIDE,
    OP_BINARY_FLOOR_DIVIDE,
    OP_BINARY_MODULO,
    OP_BINARY_POWER,
    OP_COMPARE_OP,
    OP_JUMP_IF_FALSE,
    OP_JUMP_IF_TRUE,
    OP_JUMP,
    OP_CALL_FUNCTION,
    OP_RETURN_VALUE,
    OP_NOP,
    OP_HAVE_ARGUMENT = 90
} Opcode;

/* ==================== COMPARE OPS ==================== */

#define CMP_LT 0
#define CMP_LE 1
#define CMP_EQ 2
#define CMP_NE 3
#define CMP_GT 4
#define CMP_GE 5

/* ==================== CODE OBJECT FUNCTIONS ==================== */

PyCodeObject* PyCode_New(uint8_t *code, Py_ssize_t code_size,
                         PyObject **consts, Py_ssize_t n_consts);
void PyCode_Free(PyCodeObject *code);

#ifdef __cplusplus
}
#endif

#endif /* UMEROS_PYCODE_H */
