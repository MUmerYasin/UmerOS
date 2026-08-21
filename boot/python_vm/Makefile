# Makefile - UmerOS Python VM
#
# Usage:
#   make              # Build release
#   make debug        # Build debug
#   make test         # Run tests
#   make clean        # Clean build

CC ?= gcc
CFLAGS ?= -Wall -Wextra -Wpedantic -O2
CFLAGS_DEBUG = -Wall -Wextra -Wpedantic -O0 -g -DDEBUG

BUILD_DIR = build
SRC_DIR = .
INC_DIR = Include

SOURCES = \
    Objects/object.c \
    Objects/long.c \
    Objects/float.c \
    Objects/unicode.c \
    Objects/bool.c \
    Objects/none.c \
    Objects/errors.c \
    Builtins/builtins.c \
    Compiler/compiler.c \
    VM/vm.c \
    Programs/main.c

OBJECTS = $(patsubst %.c,$(BUILD_DIR)/%.o,$(SOURCES))
TARGET = umeros_python

.PHONY: all debug test clean install

all: $(BUILD_DIR)/$(TARGET)

debug: CFLAGS = $(CFLAGS_DEBUG)
debug: $(BUILD_DIR)/$(TARGET)

$(BUILD_DIR)/$(TARGET): $(OBJECTS)
	$(CC) $(CFLAGS) -o $@ $^ -lm

$(BUILD_DIR)/%.o: %.c | $(BUILD_DIR)
	$(CC) $(CFLAGS) -I$(INC_DIR) -c -o $@ $<

$(BUILD_DIR):
	mkdir -p $(BUILD_DIR)/Objects $(BUILD_DIR)/Builtins $(BUILD_DIR)/Compiler $(BUILD_DIR)/VM $(BUILD_DIR)/Programs

test: all
	@echo "=== Running basic tests ==="
	@echo 'print("Hello, UmerOS!")' | ./$(BUILD_DIR)/$(TARGET) -c -
	@echo 'print(2 + 3)' | ./$(BUILD_DIR)/$(TARGET) -c -
	@echo 'x = 42; print(x)' | ./$(BUILD_DIR)/$(TARGET) -c -
	@echo 'print("Hello" + " " + "World")' | ./$(BUILD_DIR)/$(TARGET) -c -
	@echo 'print(True)' | ./$(BUILD_DIR)/$(TARGET) -c -
	@echo 'print(None)' | ./$(BUILD_DIR)/$(TARGET) -c -
	@echo '=== All tests passed ==='

clean:
	rm -rf $(BUILD_DIR)

install: all
	install -d $(DESTDIR)/usr/bin
	install -m 755 $(BUILD_DIR)/$(TARGET) $(DESTDIR)/usr/bin/umerospython

# Version info
version:
	@echo "UmerOS Python VM v3.0.0"
