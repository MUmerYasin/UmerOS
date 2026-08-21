/*
 * pytoken.h - UmerOS Python Token Types
 */

#ifndef UMEROS_PYTOKEN_H
#define UMEROS_PYTOKEN_H

#include "object.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    TOKEN_EOF = 0,

    /* Literals */
    TOKEN_INTEGER,
    TOKEN_FLOAT,
    TOKEN_STRING,
    TOKEN_NAME,
    TOKEN_TRUE,
    TOKEN_FALSE,
    TOKEN_NONE,

    /* Keywords */
    TOKEN_IF,
    TOKEN_ELIF,
    TOKEN_ELSE,
    TOKEN_WHILE,
    TOKEN_FOR,
    TOKEN_IN,
    TOKEN_BREAK,
    TOKEN_CONTINUE,
    TOKEN_RETURN,
    TOKEN_DEF,
    TOKEN_CLASS,
    TOKEN_IMPORT,
    TOKEN_FROM,
    TOKEN_AND,
    TOKEN_OR,
    TOKEN_NOT,
    TOKEN_IS,
    TOKEN_LAMBDA,
    TOKEN_TRY,
    TOKEN_EXCEPT,
    TOKEN_FINALLY,
    TOKEN_RAISE,
    TOKEN_WITH,
    TOKEN_AS,
    TOKEN_YIELD,
    TOKEN_GLOBAL,
    TOKEN_NONLOCAL,
    TOKEN_ASSERT,
    TOKEN_DEL,
    TOKEN_PASS,
    TOKEN_ASYNC,
    TOKEN_AWAIT,

    /* Operators */
    TOKEN_PLUS,
    TOKEN_MINUS,
    TOKEN_STAR,
    TOKEN_DOUBLE_STAR,
    TOKEN_SLASH,
    TOKEN_DOUBLE_SLASH,
    TOKEN_PERCENT,
    TOKEN_EQ,
    TOKEN_EQEQ,
    TOKEN_NOTEQ,
    TOKEN_LT,
    TOKEN_GT,
    TOKEN_LE,
    TOKEN_GE,
    TOKEN_AND_AND,
    TOKEN_OR_OR,
    TOKEN_NOT_NOT,
    TOKEN_TILDE,
    TOKEN_COLON_EQUAL,

    /* Delimiters */
    TOKEN_LPAREN,
    TOKEN_RPAREN,
    TOKEN_LBRACKET,
    TOKEN_RBRACKET,
    TOKEN_LBRACE,
    TOKEN_RBRACE,
    TOKEN_COMMA,
    TOKEN_SEMICOLON,
    TOKEN_COLON,
    TOKEN_DOT,
    TOKEN_ARROW,
    TOKEN_ELLIPSIS,

    /* Assignment */
    TOKEN_PLUS_EQUAL,
    TOKEN_MINUS_EQUAL,
    TOKEN_STAR_EQUAL,
    TOKEN_SLASH_EQUAL,
    TOKEN_PERCENT_EQUAL,
    TOKEN_AMPERSAND_EQUAL,
    TOKEN_PIPE_EQUAL,
    TOKEN_CARET_EQUAL,
    TOKEN_DOUBLE_STAR_EQUAL,
    TOKEN_DOUBLE_SLASH_EQUAL,
    TOKEN_RSHIFT_EQUAL,
    TOKEN_LSHIFT_EQUAL,

    /* Bitwise */
    TOKEN_AMPERSAND,
    TOKEN_PIPE,
    TOKEN_CARET,
    TOKEN_RSHIFT,
    TOKEN_LSHIFT,

    /* Special */
    TOKEN_NEWLINE,
    TOKEN_INDENT,
    TOKEN_DEDENT,
    TOKEN_COMMENT,
    TOKEN_WHITESPACE,
    TOKEN_ERROR
} TokenType;

/* Token structure */
typedef struct {
    TokenType type;
    char *value;
    Py_ssize_t length;
    int line;
    int column;
} Token;

#ifdef __cplusplus
}
#endif

#endif /* UMEROS_PYTOKEN_H */
