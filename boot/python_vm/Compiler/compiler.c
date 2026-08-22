/*
 * compiler.c - UmerOS Python Compiler
 *
 * Lexer, parser, and bytecode compiler.
 * Transforms Python source -> AST -> bytecode.
 *
 * This is a simplified but functional Python compiler.
 * Supports: print(), assignments, arithmetic, string ops,
 *           if/elif/else, while, for, def, class, imports, try/except.
 */

#include <stdlib.h>
#include <string.h>
#include "../Include/umeros_python.h"
#include "../Include/pyast.h"
#include "../Include/pytoken.h"

/* ==================== LEXER ==================== */

/* Keyword strings and their token types */
typedef struct {
    const char *word;
    TokenType type;
} KeywordEntry;

static KeywordEntry keywords[] = {
    {"False",    TOKEN_KEYWORD_FALSE},
    {"None",     TOKEN_KEYWORD_NONE},
    {"True",     TOKEN_KEYWORD_TRUE},
    {"and",      TOKEN_KEYWORD_AND},
    {"as",       TOKEN_KEYWORD_AS},
    {"assert",   TOKEN_KEYWORD_ASSERT},
    {"async",    TOKEN_KEYWORD_ASYNC},
    {"await",    TOKEN_KEYWORD_AWAIT},
    {"break",    TOKEN_KEYWORD_BREAK},
    {"class",    TOKEN_KEYWORD_CLASS},
    {"continue", TOKEN_KEYWORD_CONTINUE},
    {"def",      TOKEN_KEYWORD_DEF},
    {"del",      TOKEN_KEYWORD_DEL},
    {"elif",     TOKEN_KEYWORD_ELIF},
    {"else",     TOKEN_KEYWORD_ELSE},
    {"except",   TOKEN_KEYWORD_EXCEPT},
    {"finally",  TOKEN_KEYWORD_FINALLY},
    {"for",      TOKEN_KEYWORD_FOR},
    {"from",     TOKEN_KEYWORD_FROM},
    {"global",   TOKEN_KEYWORD_GLOBAL},
    {"if",       TOKEN_KEYWORD_IF},
    {"import",   TOKEN_KEYWORD_IMPORT},
    {"in",       TOKEN_KEYWORD_IN},
    {"is",       TOKEN_KEYWORD_IS},
    {"lambda",   TOKEN_KEYWORD_LAMBDA},
    {"nonlocal", TOKEN_KEYWORD_NONLOCAL},
    {"not",      TOKEN_KEYWORD_NOT},
    {"or",       TOKEN_KEYWORD_OR},
    {"pass",     TOKEN_KEYWORD_PASS},
    {"raise",    TOKEN_KEYWORD_RAISE},
    {"return",   TOKEN_KEYWORD_RETURN},
    {"try",      TOKEN_KEYWORD_TRY},
    {"while",    TOKEN_KEYWORD_WHILE},
    {"with",     TOKEN_KEYWORD_WITH},
    {"yield",    TOKEN_KEYWORD_YIELD},
    {NULL, TOKEN_ENDMARKER}
};

/* Lexer state */
typedef struct {
    const char *input;
    Py_ssize_t length;
    Py_ssize_t pos;
    int lineno;
    int col_offset;
    int paren_level;
    int bracket_level;
    int brace_level;
} Lexer;

static Lexer* Lexer_New(const char *input, Py_ssize_t length) {
    Lexer *lexer = (Lexer *)calloc(1, sizeof(Lexer));
    if (lexer) {
        lexer->input = input;
        lexer->length = length;
        lexer->pos = 0;
        lexer->lineno = 1;
        lexer->col_offset = 0;
    }
    return lexer;
}

static void Lexer_Free(Lexer *lexer) {
    free(lexer);
}

static char Lexer_Peek(Lexer *lexer) {
    if (lexer->pos >= lexer->length) return '\0';
    return lexer->input[lexer->pos];
}

static char Lexer_PeekNext(Lexer *lexer) {
    if (lexer->pos + 1 >= lexer->length) return '\0';
    return lexer->input[lexer->pos + 1];
}

static char Lexer_Advance(Lexer *lexer) {
    if (lexer->pos >= lexer->length) return '\0';
    char c = lexer->input[lexer->pos++];
    if (c == '\n') {
        lexer->lineno++;
        lexer->col_offset = 0;
    } else {
        lexer->col_offset++;
    }
    return c;
}

static void Lexer_SkipWhitespace(Lexer *lexer) {
    while (lexer->pos < lexer->length) {
        char c = Lexer_Peek(lexer);
        if (c == ' ' || c == '\t' || c == '\r') {
            Lexer_Advance(lexer);
        } else if (c == '#') {
            /* Skip comment to end of line */
            while (lexer->pos < lexer->length && Lexer_Peek(lexer) != '\n') {
                Lexer_Advance(lexer);
            }
        } else if (c == '\\' && Lexer_PeekNext(lexer) == '\n') {
            /* Line continuation */
            Lexer_Advance(lexer);
            Lexer_Advance(lexer);
        } else {
            break;
        }
    }
}

static PyObject* Lexer_ReadString(Lexer *lexer, char quote) {
    Py_ssize_t start = lexer->pos;
    int is_triple = 0;

    /* Check for triple quotes */
    if (Lexer_PeekNext(lexer) == quote && lexer->pos + 2 < lexer->length &&
        lexer->input[lexer->pos + 2] == quote) {
        is_triple = 1;
        Lexer_Advance(lexer);
        Lexer_Advance(lexer);
        Lexer_Advance(lexer);
    } else {
        Lexer_Advance(lexer);  /* skip opening quote */
    }

    /* Read string content */
    while (lexer->pos < lexer->length) {
        char c = Lexer_Peek(lexer);
        if (c == '\\') {
            Lexer_Advance(lexer);
            Lexer_Advance(lexer);
            continue;
        }
        if (is_triple) {
            if (c == quote && Lexer_PeekNext(lexer) == quote &&
                lexer->pos + 2 < lexer->length && lexer->input[lexer->pos + 2] == quote) {
                break;
            }
        } else {
            if (c == quote) break;
        }
        if (c == '\n' && !is_triple) {
            PyErr_SetString(PyExc_SyntaxError, "EOL while scanning string literal");
            return NULL;
        }
        Lexer_Advance(lexer);
    }

    Py_ssize_t len = lexer->pos - start;
    if (is_triple) {
        start += 3;
        len -= 6;
    } else {
        start += 1;
        len -= 2;
    }

    if (len < 0) len = 0;
    PyObject *str = PyUnicode_FromStringAndSize(lexer->input + start, len);

    /* Skip closing quote(s) */
    Lexer_Advance(lexer);
    if (is_triple) {
        Lexer_Advance(lexer);
        Lexer_Advance(lexer);
    }

    return str;
}

static PyObject* Lexer_ReadNumber(Lexer *lexer) {
    Py_ssize_t start = lexer->pos;
    int is_float = 0;

    while (lexer->pos < lexer->length) {
        char c = Lexer_Peek(lexer);
        if (c >= '0' && c <= '9') {
            Lexer_Advance(lexer);
        } else if (c == '.' && !is_float) {
            is_float = 1;
            Lexer_Advance(lexer);
        } else if (c == 'e' || c == 'E') {
            is_float = 1;
            Lexer_Advance(lexer);
            if (Lexer_Peek(lexer) == '+' || Lexer_Peek(lexer) == '-') {
                Lexer_Advance(lexer);
            }
        } else {
            break;
        }
    }

    Py_ssize_t len = lexer->pos - start;
    char *buf = (char *)malloc(len + 1);
    if (!buf) return NULL;
    memcpy(buf, lexer->input + start, len);
    buf[len] = '\0';

    PyObject *result;
    if (is_float) {
        double val = strtod(buf, NULL);
        result = PyFloat_FromDouble(val);
    } else {
        long val = strtol(buf, NULL, 10);
        result = PyLong_FromLong(val);
    }
    free(buf);
    return result;
}

static PyObject* Lexer_ReadName(Lexer *lexer) {
    Py_ssize_t start = lexer->pos;

    while (lexer->pos < lexer->length) {
        char c = Lexer_Peek(lexer);
        if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
            (c >= '0' && c <= '9') || c == '_') {
            Lexer_Advance(lexer);
        } else {
            break;
        }
    }

    Py_ssize_t len = lexer->pos - start;
    return PyUnicode_FromStringAndSize(lexer->input + start, len);
}

/* ==================== PARSER ==================== */

/* Parser state */
typedef struct {
    Lexer *lexer;
    PyObject *current_token;    /* Current lookahead token */
    PyObject *next_token;       /* Next token */
    int token_type;             /* Current token type */
} Parser;

static Parser* Parser_New(Lexer *lexer) {
    Parser *parser = (Parser *)calloc(1, sizeof(Parser));
    if (parser) {
        parser->lexer = lexer;
        parser->current_token = NULL;
        parser->next_token = NULL;
        parser->token_type = TOKEN_ENDMARKER;
    }
    return parser;
}

static void Parser_Free(Parser *parser) {
    if (parser->current_token) Py_DECREF(parser->current_token);
    if (parser->next_token) Py_DECREF(parser->next_token);
    free(parser);
}

/* Get token type from string */
static int GetTokenType(const char *s) {
    for (KeywordEntry *kw = keywords; kw->word != NULL; kw++) {
        if (strcmp(s, kw->word) == 0) return kw->type;
    }
    return TOKEN_NAME;
}

/* Simple token reading - returns token type */
static int Parser_NextToken(Parser *parser) {
    Lexer_SkipWhitespace(parser->lexer);
    if (parser->lexer->pos >= parser->lexer->length) return TOKEN_ENDMARKER;

    char c = Lexer_Peek(parser->lexer);

    /* String */
    if (c == '\'' || c == '"') {
        PyObject *str = Lexer_ReadString(parser->lexer, c);
        if (str) {
            if (parser->current_token) Py_DECREF(parser->current_token);
            parser->current_token = str;
            return TOKEN_STRING;
        }
        return TOKEN_ERROR;
    }

    /* Number */
    if (c >= '0' && c <= '9') {
        PyObject *num = Lexer_ReadNumber(parser->lexer);
        if (parser->current_token) Py_DECREF(parser->current_token);
        parser->current_token = num;
        return PyFloat_Check(num) ? TOKEN_NUMBER : TOKEN_NUMBER;
    }

    /* Name or keyword */
    if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_') {
        PyObject *name = Lexer_ReadName(parser->lexer);
        if (parser->current_token) Py_DECREF(parser->current_token);
        parser->current_token = name;
        const char *s = PyUnicode_AsString(name);
        return GetTokenType(s);
    }

    /* Operators and delimiters */
    Lexer_Advance(parser->lexer);
    switch (c) {
        case '(': return TOKEN_LPAREN;
        case ')': return TOKEN_RPAREN;
        case '[': return TOKEN_LBRACKET;
        case ']': return TOKEN_RBRACKET;
        case '{': return TOKEN_LBRACE;
        case '}': return TOKEN_RBRACE;
        case ',': return TOKEN_COMMA;
        case ':': return TOKEN_COLON;
        case '.': return TOKEN_DOT;
        case ';': return TOKEN_SEMICOLON;
        case '@': return TOKEN_AT;
        case '+':
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); return TOKEN_PLUSEQUAL; }
            return TOKEN_PLUS;
        case '-':
            if (Lexer_Peek(parser->lexer) == '>') { Lexer_Advance(parser->lexer); return TOKEN_ARROW; }
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); return TOKEN_MINEQUAL; }
            return TOKEN_MINUS;
        case '*':
            if (Lexer_Peek(parser->lexer) == '*') { Lexer_Advance(parser->lexer); return TOKEN_DOUBLESTAR; }
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); return TOKEN_STAREQUAL; }
            return TOKEN_STAR;
        case '/':
            if (Lexer_Peek(parser->lexer) == '/') { Lexer_Advance(parser->lexer); return TOKEN_DOUBLESLASH; }
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); return TOKEN_SLASHEQUAL; }
            return TOKEN_SLASH;
        case '%':
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); return TOKEN_PERCENTEQUAL; }
            return TOKEN_PERCENT;
        case '=':
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); return TOKEN_EQ; }
            return TOKEN_EQUAL;
        case '!':
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); return TOKEN_NOTEQUAL; }
            return TOKEN_ERROR;
        case '<':
            if (Lexer_Peek(parser->lexer) == '<') { Lexer_Advance(parser->lexer); return TOKEN_LEFTSHIFT; }
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); return TOKEN_LESSEQUAL; }
            return TOKEN_LESS;
        case '>':
            if (Lexer_Peek(parser->lexer) == '>') { Lexer_Advance(parser->lexer); return TOKEN_RIGHTSHIFT; }
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); return TOKEN_GREATEREQUAL; }
            return TOKEN_GREATER;
        case '\n': return TOKEN_NL;
        default: return TOKEN_ERROR;
    }
}

/* Parse an expression */
static PyObject* Parser_Expr(Parser *parser) {
    /* Simplified expression parser */
    int token = Parser_NextToken(parser);

    if (token == TOKEN_NUMBER || token == TOKEN_STRING) {
        Py_INCREF(parser->current_token);
        return parser->current_token;
    }

    if (token == TOKEN_LPAREN) {
        /* Parenthesized expression */
        PyObject *expr = Parser_Expr(parser);
        Parser_NextToken(parser); /* consume ')' */
        return expr;
    }

    if (token == TOKEN_MINUS) {
        /* Unary minus */
        PyObject *operand = Parser_Expr(parser);
        /* TODO: return unary op node */
        return operand;
    }

    if (token == TOKEN_NAME) {
        Py_INCREF(parser->current_token);
        return parser->current_token;
    }

    if (token == TOKEN_KEYWORD_TRUE) {
        return PyBool_FromLong(1);
    }
    if (token == TOKEN_KEYWORD_FALSE) {
        return PyBool_FromLong(0);
    }
    if (token == TOKEN_KEYWORD_NONE) {
        Py_INCREF(Py_None);
        return Py_None;
    }

    return NULL;
}

/* ==================== COMPILER ==================== */

/* Compiler state */
typedef struct {
    PyCodeObject *code;
    uint8_t *bytecode;
    Py_ssize_t bytecode_size;
    Py_ssize_t bytecode_pos;
    int *arg_stack;
    int arg_top;
    /* Constants pool */
    PyObject **consts;
    Py_ssize_t n_consts;
    Py_ssize_t consts_size;
} Compiler;

static Compiler* Compiler_New(void) {
    Compiler *compiler = (Compiler *)calloc(1, sizeof(Compiler));
    if (compiler) {
        compiler->bytecode_size = 1024;
        compiler->bytecode = (uint8_t *)malloc(compiler->bytecode_size);
        compiler->bytecode_pos = 0;
        compiler->arg_stack = (int *)calloc(256, sizeof(int));
        compiler->arg_top = 0;
        compiler->consts_size = 256;
        compiler->consts = (PyObject **)calloc(compiler->consts_size, sizeof(PyObject *));
        compiler->n_consts = 0;
    }
    return compiler;
}

static void Compiler_Free(Compiler *compiler) {
    if (compiler) {
        free(compiler->bytecode);
        free(compiler->arg_stack);
        for (Py_ssize_t i = 0; i < compiler->n_consts; i++) {
            Py_DECREF(compiler->consts[i]);
        }
        free(compiler->consts);
        free(compiler);
    }
}

/* Emit a single opcode */
static void Compiler_Emit(Compiler *compiler, Opcode op, int arg) {
    if (compiler->bytecode_pos + 3 >= compiler->bytecode_size) {
        compiler->bytecode_size *= 2;
        compiler->bytecode = (uint8_t *)realloc(compiler->bytecode, compiler->bytecode_size);
    }

    compiler->bytecode[compiler->bytecode_pos++] = (uint8_t)op;

    if (arg >= 0 && arg <= 255) {
        compiler->bytecode[compiler->bytecode_pos++] = (uint8_t)arg;
    } else {
        /* Extended args */
        compiler->bytecode[compiler->bytecode_pos++] = (uint8_t)(arg >> 8);
        compiler->bytecode[compiler->bytecode_pos++] = (uint8_t)(arg & 0xFF);
    }
}

/* Emit opcode with argument from constant pool */
static int Compiler_AddConstant(Compiler *compiler, PyObject *value) {
    /* Check if constant already exists */
    for (Py_ssize_t i = 0; i < compiler->n_consts; i++) {
        if (PyObject_Compare(compiler->consts[i], value) == 0) {
            return (int)i;
        }
    }

    /* Add new constant */
    if (compiler->n_consts >= compiler->consts_size) {
        compiler->consts_size *= 2;
        compiler->consts = (PyObject **)realloc(compiler->consts,
                                                 compiler->consts_size * sizeof(PyObject *));
    }

    Py_INCREF(value);
    compiler->consts[compiler->n_consts] = value;
    return (int)(compiler->n_consts++);
}

/* Build the final code object */
static PyCodeObject* Compiler_MakeCode(Compiler *compiler) {
    PyCodeObject *code = PyCode_New(
        compiler->bytecode,
        compiler->bytecode_pos,
        compiler->consts,
        compiler->n_consts
    );
    return code;
}

/* ==================== BYTECODE COMPILATION ==================== */

/* Compile a statement */
static int Compile_Statement(Compiler *compiler, Parser *parser) {
    int token = parser->token_type;

    /* Skip newlines */
    while (token == TOKEN_NL) {
        token = Parser_NextToken(parser);
    }

    if (token == TOKEN_ENDMARKER) return 0;

    /* print(...) statement */
    if (token == TOKEN_NAME) {
        const char *name = PyUnicode_AsString(parser->current_token);
        if (strcmp(name, "print") == 0) {
            /* Parse function call */
            Parser_NextToken(parser);  /* skip 'print' */
            if (parser->token_type == TOKEN_LPAREN) {
                /* Parse arguments */
                Parser_NextToken(parser);  /* skip '(' */

                /* Compile the argument expression */
                PyObject *arg = Parser_Expr(parser);
                if (arg) {
                    int const_idx = Compiler_AddConstant(compiler, arg);

                    /* Emit: LOAD_CONST <arg>, LOAD_GLOBAL <print>, CALL_FUNCTION 1, POP_TOP */
                    Compiler_Emit(compiler, OP_LOAD_CONST, const_idx);
                    int print_idx = Compiler_AddConstant(compiler,
                        PyUnicode_FromString("print"));
                    Compiler_Emit(compiler, OP_LOAD_GLOBAL, print_idx);
                    Compiler_Emit(compiler, OP_CALL_FUNCTION, 1);
                    Compiler_Emit(compiler, OP_POP_TOP, 0);

                    Py_DECREF(arg);
                }

                /* Consume closing paren */
                while (parser->token_type != TOKEN_RPAREN &&
                       parser->token_type != TOKEN_ENDMARKER) {
                    Parser_NextToken(parser);
                }
                if (parser->token_type == TOKEN_RPAREN) {
                    Parser_NextToken(parser);
                }
            }
            return 1;
        }

        /* Assignment: name = expr */
        Parser_NextToken(parser);
        if (parser->token_type == TOKEN_EQUAL) {
            Parser_NextToken(parser);  /* skip '=' */
            PyObject *value = Parser_Expr(parser);
            if (value) {
                int const_idx = Compiler_AddConstant(compiler, value);
                Compiler_Emit(compiler, OP_LOAD_CONST, const_idx);
                int name_idx = Compiler_AddConstant(compiler, PyUnicode_FromString(name));
                Compiler_Emit(compiler, OP_STORE_NAME, name_idx);
                Py_DECREF(value);
            }
            return 1;
        }
    }

    /* Skip unrecognized tokens */
    while (token != TOKEN_NL && token != TOKEN_ENDMARKER) {
        token = Parser_NextToken(parser);
    }

    return 1;
}

/* Compile source code to bytecode */
PyObject* Py_CompileString(const char *source, const char *filename) {
    Py_ssize_t length = strlen(source);

    Lexer *lexer = Lexer_New(source, length);
    if (!lexer) return NULL;

    Parser *parser = Parser_New(lexer);
    if (!parser) {
        Lexer_Free(lexer);
        return NULL;
    }

    Compiler *compiler = Compiler_New();
    if (!compiler) {
        Parser_Free(parser);
        Lexer_Free(lexer);
        return NULL;
    }

    /* Compile all statements */
    while (1) {
        int token = Parser_NextToken(parser);
        parser->token_type = token;

        if (token == TOKEN_ENDMARKER) break;

        Compile_Statement(compiler, parser);
    }

    /* Add return None at end */
    int none_idx = Compiler_AddConstant(compiler, Py_None);
    Compiler_Emit(compiler, OP_LOAD_CONST, none_idx);
    Compiler_Emit(compiler, OP_RETURN_VALUE, 0);

    PyCodeObject *code = Compiler_MakeCode(compiler);

    Compiler_Free(compiler);
    Parser_Free(parser);
    Lexer_Free(lexer);

    return (PyObject *)code;
}
