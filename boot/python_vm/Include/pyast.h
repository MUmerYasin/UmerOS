/*
 * pyast.h - UmerOS Python AST Node Types
 */

#ifndef UMEROS_PYAST_H
#define UMEROS_PYAST_H

#include "object.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    /* Statements */
    AST_EXPR_STMT,
    AST_ASSIGN,
    AST_RETURN,
    AST_IF,
    AST_WHILE,
    AST_FOR,
    AST_BREAK_STMT,
    AST_CONTINUE_STMT,
    AST_PASS,
    AST_IMPORT,
    AST_FROM_IMPORT,
    AST_DEF,
    AST_CLASS,
    AST_RAISE,
    AST_TRY,
    AST_WITH,

    /* Expressions */
    AST_NUMBER,
    AST_STRING,
    AST_BOOL,
    AST_NONE,
    AST_NAME,
    AST_BINARY_OP,
    AST_UNARY_OP,
    AST_CALL,
    AST_ATTRIBUTE,
    AST_SUBSCRIPT,
    AST_SLICE,
    AST_LIST,
    AST_TUPLE,
    AST_DICT,
    AST_SET,
    AST_LAMBDA,
    AST_LIST_COMP,
    AST_SET_COMP,
    AST_DICT_COMP,
    AST_GENERATOR,
    AST_YIELD,
    AST_AWAIT,

    /* Comparison */
    AST_COMPARE,

    /* Walrus */
    AST_WALRUS,

    /* Keyword argument */
    AST_KEYWORD,

    /* Starred */
    AST_STARRED,

    /* Global */
    AST_GLOBAL,

    /* Nonlocal */
    AST_NONLOCAL,

    /* Assert */
    AST_ASSERT,

    /* Del */
    AST_DEL
} ASTNodeType;

typedef enum {
    BINOP_ADD,
    BINOP_SUBTRACT,
    BINOP_MULTIPLY,
    BINOP_DIVIDE,
    BINOP_FLOOR_DIVIDE,
    BINOP_MODULO,
    BINOP_POWER,
    BINOP_LSHIFT,
    BINOP_RSHIFT,
    BINOP_AND,
    BINOP_XOR,
    BINOP_OR,
    BINOP_AND_AND,
    BINOP_OR_OR
} BinaryOpType;

typedef enum {
    UNARYOP_NEG,
    UNARYOP_POS,
    UNARYOP_NOT,
    UNARYOP_INV
} UnaryOpType;

typedef enum {
    CMP_LT,
    CMP_LE,
    CMP_EQ,
    CMP_NE,
    CMP_GT,
    CMP_GE,
    CMP_IS,
    CMP_IS_NOT,
    CMP_IN,
    CMP_NOT_IN
} CmpOpType;

/* AST Node structure */
typedef struct {
    ASTNodeType type;
    int line;
    int col_offset;

    union {
        /* Number */
        long int_value;
        double float_value;

        /* String/Name */
        char *string_value;

        /* Bool */
        int bool_value;

        /* Binary operation */
        struct {
            BinaryOpType op;
            struct _ast_node *left;
            struct _ast_node *right;
        } binary_op;

        /* Unary operation */
        struct {
            UnaryOpType op;
            struct _ast_node *operand;
        } unary_op;

        /* Call */
        struct {
            struct _ast_node *func;
            PyObject *args;
            PyObject *kwargs;
        } call;

        /* Compare */
        struct {
            CmpOpType op;
            struct _ast_node *left;
            struct _ast_node *right;
        } compare;

        /* If */
        struct {
            struct _ast_node *test;
            struct _ast_node *body;
            struct _ast_node *orelse;
        } if_stmt;

        /* While */
        struct {
            struct _ast_node *test;
            struct _ast_node *body;
        } while_stmt;

        /* For */
        struct {
            struct _ast_node *target;
            struct _ast_node *iter;
            struct _ast_node *body;
        } for_stmt;

        /* Function def */
        struct {
            char *name;
            PyObject *args;
            struct _ast_node *body;
        } func_def;

        /* Return */
        struct {
            struct _ast_node *value;
        } return_stmt;

        /* Assign */
        struct {
            struct _ast_node *target;
            struct _ast_node *value;
        } assign;

        /* Name */
        struct {
            char *name;
        } name;

        /* List */
        struct {
            PyObject *elements;
        } list;

        /* Tuple */
        struct {
            PyObject *elements;
        } tuple;
    } as;
} ASTNode;

/* AST functions */
ASTNode* ASTNode_New(ASTNodeType type, int line, int col_offset);
void ASTNode_Free(ASTNode *node);
ASTNode* ASTNode_BinaryOp(BinaryOpType op, ASTNode *left, ASTNode *right, int line, int col_offset);
ASTNode* ASTNode_UnaryOp(UnaryOpType op, ASTNode *operand, int line, int col_offset);
ASTNode* ASTNode_Call(ASTNode *func, PyObject *args, PyObject *kwargs, int line, int col_offset);
ASTNode* ASTNode_Assign(ASTNode *target, ASTNode *value, int line, int col_offset);
ASTNode* ASTNode_Return(ASTNode *value, int line, int col_offset);
ASTNode* ASTNode_If(ASTNode *test, ASTNode *body, ASTNode *orelse, int line, int col_offset);
ASTNode* ASTNode_While(ASTNode *test, ASTNode *body, int line, int col_offset);
ASTNode* ASTNode_For(ASTNode *target, ASTNode *iter, ASTNode *body, int line, int col_offset);
ASTNode* ASTNode_Name(const char *name, int line, int col_offset);
ASTNode* ASTNode_Number(long value, int line, int col_offset);
ASTNode* ASTNode_Float(double value, int line, int col_offset);
ASTNode* ASTNode_String(const char *value, int line, int col_offset);
ASTNode* ASTNode_Bool(int value, int line, int col_offset);
ASTNode* ASTNode_None(int line, int col_offset);

#ifdef __cplusplus
}
#endif

#endif /* UMEROS_PYAST_H */
