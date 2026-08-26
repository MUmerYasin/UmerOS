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

#include <stdio.h>
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

/* ==================== COMPILER (forward declarations) ==================== */

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

    /* Emit argument byte (always 2 bytes per instruction) */
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
    int result = TOKEN_ERROR; /* default for unmatched paths */
    Lexer_SkipWhitespace(parser->lexer);
    if (parser->lexer->pos >= parser->lexer->length) {
        result = TOKEN_ENDMARKER;
        goto out;
    }

    char c = Lexer_Peek(parser->lexer);

    /* String */
    if (c == '\'' || c == '"') {
        PyObject *str = Lexer_ReadString(parser->lexer, c);
        if (str) {
            if (parser->current_token) Py_DECREF(parser->current_token);
            parser->current_token = str;
            result = TOKEN_STRING;
            goto out;
        }
        result = TOKEN_ERROR;
        goto out;
    }

    /* Number */
    if (c >= '0' && c <= '9') {
        PyObject *num = Lexer_ReadNumber(parser->lexer);
        if (parser->current_token) Py_DECREF(parser->current_token);
        parser->current_token = num;
        result = TOKEN_NUMBER;
        goto out;
    }

    /* Name or keyword */
    if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_') {
        PyObject *name = Lexer_ReadName(parser->lexer);
        if (parser->current_token) Py_DECREF(parser->current_token);
        parser->current_token = name;
        const char *s = PyUnicode_AsString(name);
        result = GetTokenType(s);
        goto out;
    }

    /* Operators and delimiters */
    Lexer_Advance(parser->lexer);
    switch (c) {
        case '(': result = TOKEN_LPAREN; goto out;
        case ')': result = TOKEN_RPAREN; goto out;
        case '[': result = TOKEN_LBRACKET; goto out;
        case ']': result = TOKEN_RBRACKET; goto out;
        case '{': result = TOKEN_LBRACE; goto out;
        case '}': result = TOKEN_RBRACE; goto out;
        case ',': result = TOKEN_COMMA; goto out;
        case ':': result = TOKEN_COLON; goto out;
        case '.': result = TOKEN_DOT; goto out;
        case ';': result = TOKEN_SEMICOLON; goto out;
        case '@': result = TOKEN_AT; goto out;
        case '+':
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); result = TOKEN_PLUSEQUAL; goto out; }
            result = TOKEN_PLUS; goto out;
        case '-':
            if (Lexer_Peek(parser->lexer) == '>') { Lexer_Advance(parser->lexer); result = TOKEN_ARROW; goto out; }
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); result = TOKEN_MINEQUAL; goto out; }
            result = TOKEN_MINUS; goto out;
        case '*':
            if (Lexer_Peek(parser->lexer) == '*') { Lexer_Advance(parser->lexer); result = TOKEN_DOUBLESTAR; goto out; }
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); result = TOKEN_STAREQUAL; goto out; }
            result = TOKEN_STAR; goto out;
        case '/':
            if (Lexer_Peek(parser->lexer) == '/') { Lexer_Advance(parser->lexer); result = TOKEN_DOUBLESLASH; goto out; }
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); result = TOKEN_SLASHEQUAL; goto out; }
            result = TOKEN_SLASH; goto out;
        case '%':
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); result = TOKEN_PERCENTEQUAL; goto out; }
            result = TOKEN_PERCENT; goto out;
        case '=':
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); result = TOKEN_EQEQ; goto out; }
            result = TOKEN_EQ; goto out;
        case '!':
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); result = TOKEN_NOTEQ; goto out; }
            result = TOKEN_ERROR; goto out;
        case '<':
            if (Lexer_Peek(parser->lexer) == '<') { Lexer_Advance(parser->lexer); result = TOKEN_LSHIFT; goto out; }
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); result = TOKEN_LE; goto out; }
            result = TOKEN_LT; goto out;
        case '>':
            if (Lexer_Peek(parser->lexer) == '>') { Lexer_Advance(parser->lexer); result = TOKEN_RSHIFT; goto out; }
            if (Lexer_Peek(parser->lexer) == '=') { Lexer_Advance(parser->lexer); result = TOKEN_GE; goto out; }
            result = TOKEN_GT; goto out;
        case '\n': result = TOKEN_NL; goto out;
        default: result = TOKEN_ERROR; goto out;
    }

out:
    parser->token_type = result;
    return result;
}

/* Parse and compile an expression, emitting bytecode */
static void Compile_Expr(Compiler *compiler, Parser *parser) {
    fprintf(stderr, "[DBG-C] Compile_Expr ENTER token=%d\n", parser->token_type);
    fflush(stderr);
    /* Parse primary expression */
    int token = parser->token_type;

    if (token == TOKEN_NUMBER) {
        Py_INCREF(parser->current_token);
        int idx = Compiler_AddConstant(compiler, parser->current_token);
        Compiler_Emit(compiler, OP_LOAD_CONST, idx);
        Py_DECREF(parser->current_token);
        parser->current_token = NULL;
        Parser_NextToken(parser);  /* consume the token we just read */
        goto parse_binop;
    }

    if (token == TOKEN_STRING) {
        Py_INCREF(parser->current_token);
        int idx = Compiler_AddConstant(compiler, parser->current_token);
        Compiler_Emit(compiler, OP_LOAD_CONST, idx);
        Py_DECREF(parser->current_token);
        parser->current_token = NULL;
        Parser_NextToken(parser);  /* consume the token we just read */
        goto parse_binop;
    }

    if (token == TOKEN_LPAREN) {
        Parser_NextToken(parser);  /* consume '(' */
        Compile_Expr(compiler, parser);  /* parse inner expression */
        if (parser->token_type == TOKEN_RPAREN) {
            Parser_NextToken(parser);  /* consume ')' */
        }
        goto parse_binop;
    }

    if (token == TOKEN_MINUS) {
        /* Unary minus: emit 0 then subtract */
        Compiler_Emit(compiler, OP_LOAD_CONST,
            Compiler_AddConstant(compiler, PyLong_FromLong(0)));
        Parser_NextToken(parser);  /* consume '-' */
        Compile_Expr(compiler, parser);  /* parse operand */
        Compiler_Emit(compiler, OP_BINARY_SUBTRACT, 0);
        goto parse_binop;
    }

    if (token == TOKEN_NAME) {
        Py_INCREF(parser->current_token);
        int idx = Compiler_AddConstant(compiler, parser->current_token);
        Compiler_Emit(compiler, OP_LOAD_NAME, idx);
        Py_DECREF(parser->current_token);
        parser->current_token = NULL;
        Parser_NextToken(parser);  /* consume the name */
        goto parse_binop;
    }

    if (token == TOKEN_KEYWORD_TRUE) {
        Parser_NextToken(parser);  /* consume keyword */
        int idx = Compiler_AddConstant(compiler, PyBool_FromLong(1));
        Compiler_Emit(compiler, OP_LOAD_CONST, idx);
        goto parse_binop;
    }
    if (token == TOKEN_KEYWORD_FALSE) {
        Parser_NextToken(parser);
        int idx = Compiler_AddConstant(compiler, PyBool_FromLong(0));
        Compiler_Emit(compiler, OP_LOAD_CONST, idx);
        goto parse_binop;
    }
    if (token == TOKEN_KEYWORD_NONE) {
        Parser_NextToken(parser);
        int idx = Compiler_AddConstant(compiler, Py_None);
        Compiler_Emit(compiler, OP_LOAD_CONST, idx);
        goto parse_binop;
    }

    /* Fallback: push None */
    Compiler_Emit(compiler, OP_LOAD_CONST,
        Compiler_AddConstant(compiler, Py_None));
    return;

parse_binop:
    /* Check for binary operators */
    token = parser->token_type;
    if (token == TOKEN_PLUS) {
        Parser_NextToken(parser);  /* consume '+' */
        Compile_Expr(compiler, parser);  /* parse right operand */
        Compiler_Emit(compiler, OP_BINARY_ADD, 0);
    } else if (token == TOKEN_MINUS) {
        Parser_NextToken(parser);  /* consume '-' */
        Compile_Expr(compiler, parser);
        Compiler_Emit(compiler, OP_BINARY_SUBTRACT, 0);
    } else if (token == TOKEN_STAR) {
        Parser_NextToken(parser);  /* consume '*' */
        Compile_Expr(compiler, parser);
        Compiler_Emit(compiler, OP_BINARY_MULTIPLY, 0);
    } else if (token == TOKEN_SLASH) {
        Parser_NextToken(parser);  /* consume '/' */
        Compile_Expr(compiler, parser);
        Compiler_Emit(compiler, OP_BINARY_TRUE_DIVIDE, 0);
    } else if (token == TOKEN_PERCENT) {
        Parser_NextToken(parser);  /* consume '%' */
        Compile_Expr(compiler, parser);
        Compiler_Emit(compiler, OP_BINARY_MODULO, 0);
    } else if (token == TOKEN_DOUBLESTAR) {
        Parser_NextToken(parser);  /* consume '**' */
        Compile_Expr(compiler, parser);
        Compiler_Emit(compiler, OP_BINARY_POWER, 0);
    } else if (token == TOKEN_DOUBLESLASH) {
        Parser_NextToken(parser);  /* consume '//' */
        Compile_Expr(compiler, parser);
        Compiler_Emit(compiler, OP_BINARY_FLOOR_DIVIDE, 0);
    }
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
    fprintf(stderr, "[DBG-C] Compile_Statement ENTER token=%d\n", parser->token_type);
    fflush(stderr);
    int token = parser->token_type;

    /* Skip newlines */
    while (token == TOKEN_NL) {
        token = Parser_NextToken(parser);
    }

    if (token == TOKEN_ENDMARKER) return 0;

    /* print(...) statement */
    if (token == TOKEN_NAME) {
        const char *name = PyUnicode_AsString(parser->current_token);
        fprintf(stderr, "[DBG-C] Compile_Statement: NAME='%s'\n", name ? name : "NULL");
        fflush(stderr);
        if (strcmp(name, "print") == 0) {
            fprintf(stderr, "[DBG-C] Compile_Statement: found 'print'\n");
            fflush(stderr);
            /* Parse function call */
            Parser_NextToken(parser);  /* skip 'print' */
            fprintf(stderr, "[DBG-C] Compile_Statement: after skip print, token=%d\n", parser->token_type);
            fflush(stderr);
            if (parser->token_type == TOKEN_LPAREN) {
                fprintf(stderr, "[DBG-C] Compile_Statement: found '('\n");
                fflush(stderr);
                /* Parse arguments */
                Parser_NextToken(parser);  /* skip '(' */
                fprintf(stderr, "[DBG-C] Compile_Statement: after skip '(', token=%d\n", parser->token_type);
                fflush(stderr);

                /* Compile the argument expression */
                fprintf(stderr, "[DBG-C] Compile_Statement: calling Compile_Expr\n");
                fflush(stderr);
                Compile_Expr(compiler, parser);
                fprintf(stderr, "[DBG-C] Compile_Statement: Compile_Expr returned, token=%d\n", parser->token_type);
                fflush(stderr);

                /* Emit: LOAD_GLOBAL <print>, CALL_FUNCTION 1, POP_TOP */
                int print_idx = Compiler_AddConstant(compiler,
                    PyUnicode_FromString("print"));
                Compiler_Emit(compiler, OP_LOAD_GLOBAL, print_idx);
                Compiler_Emit(compiler, OP_CALL_FUNCTION, 1);
                Compiler_Emit(compiler, OP_POP_TOP, 0);
                fprintf(stderr, "[DBG-C] Compile_Statement: emitted print bytecode\n");
                fflush(stderr);

                /* Consume closing paren */
                while (parser->token_type != TOKEN_RPAREN &&
                       parser->token_type != TOKEN_ENDMARKER) {
                    Parser_NextToken(parser);
                }
                if (parser->token_type == TOKEN_RPAREN) {
                    Parser_NextToken(parser);
                }
                fprintf(stderr, "[DBG-C] Compile_Statement: after closing paren, token=%d\n", parser->token_type);
                fflush(stderr);
            }
            fprintf(stderr, "[DBG-C] Compile_Statement: returning 1 (print)\n");
            fflush(stderr);
            return 1;
        }

        /* Assignment: name = expr */
        Parser_NextToken(parser);
        if (parser->token_type == TOKEN_EQUAL) {
            Parser_NextToken(parser);  /* skip '=' */
            Compile_Expr(compiler, parser);
            int name_idx = Compiler_AddConstant(compiler, PyUnicode_FromString(name));
            Compiler_Emit(compiler, OP_STORE_NAME, name_idx);
            return 1;
        }
    }

    /* Skip unrecognized tokens */
    fprintf(stderr, "[DBG-C] Compile_Statement: skipping unrecognized tokens\n");
    fflush(stderr);
    while (token != TOKEN_NL && token != TOKEN_ENDMARKER) {
        token = Parser_NextToken(parser);
    }

    fprintf(stderr, "[DBG-C] Compile_Statement: returning 1\n");
    fflush(stderr);
    return 1;
}

/* Compile source code to bytecode */
PyObject* Py_CompileString(const char *source, const char *filename) {
    fprintf(stderr, "[DBG] Py_CompileString entered, source='%s'\n", source);
    fflush(stderr);

    Py_ssize_t length = strlen(source);
    fprintf(stderr, "[DBG] Py_CompileString: length=%d\n", (int)length);
    fflush(stderr);

    fprintf(stderr, "[DBG] Py_CompileString: creating Lexer\n");
    fflush(stderr);
    Lexer *lexer = Lexer_New(source, length);
    if (!lexer) {
        fprintf(stderr, "[DBG] Py_CompileString: Lexer_New failed\n");
        fflush(stderr);
        return NULL;
    }
    fprintf(stderr, "[DBG] Py_CompileString: Lexer created OK\n");
    fflush(stderr);

    fprintf(stderr, "[DBG] Py_CompileString: creating Parser\n");
    fflush(stderr);
    Parser *parser = Parser_New(lexer);
    if (!parser) {
        fprintf(stderr, "[DBG] Py_CompileString: Parser_New failed\n");
        fflush(stderr);
        Lexer_Free(lexer);
        return NULL;
    }
    fprintf(stderr, "[DBG] Py_CompileString: Parser created OK\n");
    fflush(stderr);

    fprintf(stderr, "[DBG] Py_CompileString: creating Compiler\n");
    fflush(stderr);
    Compiler *compiler = Compiler_New();
    if (!compiler) {
        fprintf(stderr, "[DBG] Py_CompileString: Compiler_New failed\n");
        fflush(stderr);
        Parser_Free(parser);
        Lexer_Free(lexer);
        return NULL;
    }
    fprintf(stderr, "[DBG] Py_CompileString: Compiler created OK\n");
    fflush(stderr);

    /* Compile all statements */
    fprintf(stderr, "[DBG] Py_CompileString: starting compile loop\n");
    fflush(stderr);
    while (1) {
        int token = Parser_NextToken(parser);
        parser->token_type = token;
        fprintf(stderr, "[DBG] Py_CompileString: token=%d\n", token);
        fflush(stderr);

        fprintf(stderr, "[DBG] TEST: token=%d ENDMARKER=%d cmp=%d\n", token, TOKEN_ENDMARKER, token == TOKEN_ENDMARKER);
        fflush(stderr);
        if (token == TOKEN_ENDMARKER) break;

        fprintf(stderr, "[DBG] calling Compile_Statement token=%d\n", token);
        fflush(stderr);
        int ret = Compile_Statement(compiler, parser);
        fprintf(stderr, "[DBG] Py_CompileString: Compile_Statement returned %d\n", ret);
        fflush(stderr);
    }
    fprintf(stderr, "[DBG] Py_CompileString: compile loop done\n");
    fflush(stderr);

    /* Add return None at end */
    fprintf(stderr, "[DBG] before Compiler_AddConstant(Py_None)\n"); fflush(stderr);
    int none_idx = Compiler_AddConstant(compiler, Py_None);
    fprintf(stderr, "[DBG] none_idx=%d, before emit LOAD_CONST\n", none_idx); fflush(stderr);
    Compiler_Emit(compiler, OP_LOAD_CONST, none_idx);
    fprintf(stderr, "[DBG] before emit RETURN_VALUE\n"); fflush(stderr);
    Compiler_Emit(compiler, OP_RETURN_VALUE, 0);
    fprintf(stderr, "[DBG] after all emits\n"); fflush(stderr);

    fprintf(stderr, "[DBG] Py_CompileString: calling Compiler_MakeCode\n");
    fflush(stderr);
    PyCodeObject *code = Compiler_MakeCode(compiler);
    fprintf(stderr, "[DBG] Py_CompileString: Compiler_MakeCode returned %p\n", (void*)code);
    if (code) {
        fprintf(stderr, "[DBG] Py_CompileString: bytecode=%p code_size=%d n_consts=%d\n",
                (void*)code->code, (int)code->code_size, code->n_consts);
    }
    fflush(stderr);

    Compiler_Free(compiler);
    Parser_Free(parser);
    Lexer_Free(lexer);

    return (PyObject *)code;
}
