/*
 * sys_module.c - UmerOS Python sys Module
 *
 * Minimal sys module providing:
 *   sys.path      - list of module search paths (mutable)
 *   sys.platform  - platform identifier string
 *   sys.version   - version string
 *   sys.executable - path to interpreter
 */

#include "../Include/umeros_python.h"
#include <stdio.h>
#include <string.h>

/* Global sys.path list */
static PyObject *sys_path = NULL;

/* sys.path getter: returns sys.path list (new ref) */
static PyObject* sys_path_get(PyObject *self, PyObject *args) {
    (void)self; (void)args;
    Py_INCREF(sys_path);
    return sys_path;
}

/* sys.path.append(dir) - append a directory to sys.path */
static PyObject* sys_path_append(PyObject *self, PyObject *args) {
    (void)self;

    if (!args || PyList_Size(args) < 1) {
        PyErr_SetString(PyExc_TypeError, "sys.path.append() requires one argument");
        return NULL;
    }

    PyObject *dir = PyList_GetItem(args, 0);
    if (!dir || !PyUnicode_Check(dir)) {
        PyErr_SetString(PyExc_TypeError, "sys.path.append() argument must be a string");
        return NULL;
    }

    PyList_Append(sys_path, dir);

    Py_INCREF(Py_None);
    return Py_None;
}

/* sys.path.insert(index, dir) - insert a directory at index */
static PyObject* sys_path_insert(PyObject *self, PyObject *args) {
    (void)self;

    if (!args || PyList_Size(args) < 2) {
        PyErr_SetString(PyExc_TypeError, "sys.path.insert() requires two arguments");
        return NULL;
    }

    PyObject *index_obj = PyList_GetItem(args, 0);
    PyObject *dir = PyList_GetItem(args, 1);

    if (!index_obj || !PyLong_Check(index_obj)) {
        PyErr_SetString(PyExc_TypeError, "sys.path.insert() first argument must be an integer");
        return NULL;
    }
    if (!dir || !PyUnicode_Check(dir)) {
        PyErr_SetString(PyExc_TypeError, "sys.path.insert() second argument must be a string");
        return NULL;
    }

    Py_ssize_t index = PyLong_AsLong(index_obj);
    Py_ssize_t len = PyList_Size(sys_path);

    /* Clamp index */
    if (index < 0) index = 0;
    if (index > len) index = len;

    /* Build new list: [0..index-1] + [dir] + [index..end] */
    PyObject *new_list = PyList_New(len + 1);
    for (Py_ssize_t i = 0; i < len + 1; i++) {
        if (i < index) {
            PyList_SetItem(new_list, i, PyList_GetItem(sys_path, i));
        } else if (i == index) {
            Py_INCREF(dir);
            PyList_SetItem(new_list, i, dir);
        } else {
            PyList_SetItem(new_list, i, PyList_GetItem(sys_path, i - 1));
        }
    }

    /* Replace sys_path */
    Py_DECREF(sys_path);
    sys_path = new_list;

    Py_INCREF(Py_None);
    return Py_None;
}

/* Method table for sys module */
static PyMethodDef sys_methods[] = {
    { "path",      0, 0, 0 },  /* placeholder — actual method set dynamically */
    { NULL, NULL, 0, NULL }
};

/* Initialize sys module */
void SysModule_Init(void) {
    /* Create sys.path list */
    sys_path = PyList_New(0);

    /* Add current working directory as first entry */
    PyObject *cwd = PyUnicode_FromString(".");
    if (cwd) {
        PyList_Append(sys_path, cwd);
        Py_DECREF(cwd);
    }
}

/* Get sys.path list (new reference) */
PyObject* SysModule_GetPath(void) {
    if (!sys_path) {
        SysModule_Init();
    }
    Py_INCREF(sys_path);
    return sys_path;
}

/* Add a directory to sys.path (new reference to dir not consumed) */
void SysModule_AddToPath(const char *dir) {
    if (!sys_path) {
        SysModule_Init();
    }

    PyObject *py_dir = PyUnicode_FromString(dir);
    if (py_dir) {
        PyList_Append(sys_path, py_dir);
        Py_DECREF(py_dir);
    }
}

/* Get sys module dict (the actual module object) */
PyObject* SysModule_GetDict(void) {
    if (!sys_path) {
        SysModule_Init();
    }

    PyObject *sys_dict = PyDict_New();

    /* sys.path */
    Py_INCREF(sys_path);
    PyDict_SetItemString(sys_dict, "path", sys_path);

    /* sys.platform */
    PyObject *platform = PyUnicode_FromString(
#ifdef _WIN32
        "win32"
#elif defined(__APPLE__)
        "darwin"
#else
        "linux"
#endif
    );
    if (platform) {
        PyDict_SetItemString(sys_dict, "platform", platform);
        Py_DECREF(platform);
    }

    /* sys.version */
    char version_buf[128];
    snprintf(version_buf, sizeof(version_buf),
             "%d.%d.%d (UmerOS built-in)",
             UMEROS_PYTHON_MAJOR, UMEROS_PYTHON_MINOR, UMEROS_PYTHON_PATCH);
    PyObject *version = PyUnicode_FromString(version_buf);
    if (version) {
        PyDict_SetItemString(sys_dict, "version", version);
        Py_DECREF(version);
    }

    /* sys.executable — placeholder, not set */
    /* sys.argv — not implemented yet */

    return sys_dict;
}
