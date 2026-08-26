import 'package:flutter/material.dart';
import 'dart:math';

import '../widgets/auto_adjust_box.dart';

class CalculatorApp extends StatefulWidget {
  const CalculatorApp({super.key});

  @override
  State<CalculatorApp> createState() => _CalculatorAppState();
}

class _CalculatorAppState extends State<CalculatorApp> {
  String _expression = '';
  String _result = '0';
  final List<String> _history = [];
  bool _showHistory = false;
  bool _isScientific = false;
  double _memory = 0;
  bool _hasMemory = false;

  @override
  void initState() {
    super.initState();
  }

  void _onButtonPressed(String value) {
    setState(() {
      switch (value) {
        case 'C':
          _expression = '';
          _result = '0';
          break;
        case '⌫':
          if (_expression.isNotEmpty) {
            _expression = _expression.substring(0, _expression.length - 1);
          }
          if (_expression.isEmpty) _result = '0';
          break;
        case '=':
          _calculate();
          break;
        case '+/-':
          if (_expression.isNotEmpty) {
            if (_expression.startsWith('-')) {
              _expression = _expression.substring(1);
            } else {
              _expression = '-$_expression';
            }
          }
          break;
        case '%':
          if (_expression.isNotEmpty) {
            _expression = '($_expression/100)';
            _calculate();
          }
          break;
        case 'sin':
        case 'cos':
        case 'tan':
        case 'log':
        case 'ln':
        case 'sqrt':
          _expression += '$value(';
          break;
        case 'π':
          _expression += '3.14159265359';
          break;
        case 'e':
          _expression += '2.71828182846';
          break;
        case 'x²':
          _expression = '($_expression)²';
          break;
        case 'MC':
          _memory = 0;
          _hasMemory = false;
          break;
        case 'MR':
          if (_hasMemory) _expression += _memory.toString();
          break;
        case 'M+':
          if (_result != '0' && _result != 'Error') {
            _memory += double.tryParse(_result) ?? 0;
            _hasMemory = true;
          }
          break;
        case 'M-':
          if (_result != '0' && _result != 'Error') {
            _memory -= double.tryParse(_result) ?? 0;
            _hasMemory = true;
          }
          break;
        default:
          _expression += value;
      }
    });
  }

  void _calculate() {
    if (_expression.isEmpty) return;
    try {
      String expr = _expression;
      expr = expr.replaceAll('×', '*').replaceAll('÷', '/');
      expr = expr.replaceAll('²', '**2');
      // Scientific functions are handled by _parseAtom's switch statement
      final result = _evaluateExpression(expr);
      final resultStr = result == result.roundToDouble()
          ? result.toInt().toString()
          : result.toStringAsFixed(8).replaceAll(RegExp(r'0+$'), '').replaceAll(RegExp(r'\.$'), '');
      _history.insert(0, '$_expression = $resultStr');
      if (_history.length > 10) _history.removeLast();
      _result = resultStr;
      _expression = resultStr;
    } catch (e) {
      _result = 'Error';
    }
  }

  double _sinFunction(double x) => sin(x * pi / 180);
  double _cosFunction(double x) => cos(x * pi / 180);
  double _tanFunction(double x) => tan(x * pi / 180);
  double _logFunction(double x) => log(x) / ln10;
  double _lnFunction(double x) => log(x);
  double _sqrtFunction(double x) => sqrt(x);

  double _evaluateExpression(String expr) {
    expr = expr.replaceAll(' ', '');
    return _parseAddSub(expr, 0).$1;
  }

  (double, int) _parseAddSub(String expr, int startPos) {
    final (left, pos1) = _parseMulDiv(expr, startPos);
    double leftVal = left;
    int pos = pos1;
    while (pos < expr.length && (expr[pos] == '+' || expr[pos] == '-')) {
      final op = expr[pos];
      final (right, newPos) = _parseMulDiv(expr, pos + 1);
      leftVal = op == '+' ? leftVal + right : leftVal - right;
      pos = newPos;
    }
    return (leftVal, pos);
  }

  (double, int) _parseMulDiv(String expr, int startPos) {
    final (left, pos1) = _parseAtom(expr, startPos);
    double leftVal = left;
    int pos = pos1;
    while (pos < expr.length && (expr[pos] == '*' || expr[pos] == '/')) {
      final op = expr[pos];
      final (right, newPos) = _parseAtom(expr, pos + 1);
      leftVal = op == '*' ? leftVal * right : leftVal / right;
      pos = newPos;
    }
    return (leftVal, pos);
  }

  (double, int) _parseAtom(String expr, int pos) {
    while (pos < expr.length && expr[pos] == ' ') {
      pos++;
    }
    if (pos < expr.length && expr[pos] == '(') {
      final (val, newPos) = _parseAddSub(expr, pos + 1);
      return (val, newPos + 1);
    }
    if (pos < expr.length && expr[pos] == '-') {
      final (val, newPos) = _parseAtom(expr, pos + 1);
      return (-val, newPos);
    }
    int start = pos;
    while (pos < expr.length &&
        (expr[pos] == '.' || (expr[pos].codeUnitAt(0) >= 48 && expr[pos].codeUnitAt(0) <= 57))) {
      pos++;
    }
    // Handle function calls
    if (pos < expr.length && expr[pos] == '(' && start < pos) {
      final funcName = expr.substring(start, pos);
      final (arg, newPos) = _parseAddSub(expr, pos + 1);
      double result;
      switch (funcName) {
        case 'sin': result = _sinFunction(arg); break;
        case 'cos': result = _cosFunction(arg); break;
        case 'tan': result = _tanFunction(arg); break;
        case 'log': result = _logFunction(arg); break;
        case 'ln': result = _lnFunction(arg); break;
        case 'sqrt': result = _sqrtFunction(arg); break;
        default: result = 0;
      }
      return (result, newPos + 1);
    }
    if (start == pos) return (0, pos);
    return (double.parse(expr.substring(start, pos)), pos);
  }

  Widget _buildButton(String label, {Color? color, Color? textColor, int flex = 1, bool isLarge = false}) {
    final colorScheme = Theme.of(context).colorScheme;
    final bgColor = color ?? colorScheme.surfaceContainerHighest;
    final fgColor = textColor ?? colorScheme.onSurface;

    return Expanded(
      flex: flex,
      child: Padding(
        padding: const EdgeInsets.all(2),
        child: SizedBox(
          height: isLarge ? 56 : 48,
          child: FilledButton(
            onPressed: () => _onButtonPressed(label),
            style: FilledButton.styleFrom(
              backgroundColor: bgColor,
              foregroundColor: fgColor,
              padding: EdgeInsets.zero,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(8),
              ),
            ),
            child: Text(
              label,
              style: TextStyle(
                fontSize: isLarge ? 18 : 14,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Column(
      children: [
        // Header
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
            border: Border(
              bottom: BorderSide(
                color: colorScheme.outline.withValues(alpha: 0.2),
              ),
            ),
          ),
          child: Row(
            children: [
              Icon(Icons.calculate, color: colorScheme.primary, size: 20),
              const SizedBox(width: 8),
              Flexible(
                child: Text(
                  'Calculator',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color: colorScheme.onSurface,
                  ),
                ),
              ),
              const Spacer(),
              TextButton(
                onPressed: () => setState(() => _showHistory = !_showHistory),
                child: Text(_showHistory ? 'Hide History' : 'History'),
              ),
              Switch(
                value: _isScientific,
                onChanged: (v) => setState(() => _isScientific = v),
                activeThumbColor: colorScheme.primary,
              ),
              Text('Sci', style: TextStyle(fontSize: 12, color: colorScheme.onSurface)),
            ],
          ),
        ),
        // History panel
        if (_showHistory)
          Container(
            height: 120,
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
              border: Border(
                bottom: BorderSide(
                  color: colorScheme.outline.withValues(alpha: 0.2),
                ),
              ),
            ),
            child: _history.isEmpty
                ? Center(
                    child: Text(
                      'No history yet',
                      style: TextStyle(color: colorScheme.onSurface.withValues(alpha: 0.5)),
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(8),
                    itemCount: _history.length,
                    itemBuilder: (context, index) {
                      return Padding(
                        padding: const EdgeInsets.symmetric(vertical: 2),
                        child: Text(
                          _history[index],
                          textAlign: TextAlign.right,
                          style: TextStyle(
                            color: colorScheme.onSurface.withValues(alpha: 0.7),
                            fontSize: 12,
                          ),
                        ),
                      );
                    },
                  ),
          ),
        // Display
        Expanded(
          flex: 2,
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            child: AutoAdjustBox(
              alignment: Alignment.bottomRight,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Text(
                    _expression.isEmpty ? '0' : _expression,
                    style: TextStyle(
                      fontSize: 20,
                      color: colorScheme.onSurface.withValues(alpha: 0.6),
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    _result,
                    style: TextStyle(
                      fontSize: 40,
                      fontWeight: FontWeight.bold,
                      color: colorScheme.onSurface,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        // Scientific buttons
        if (_isScientific)
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: Column(
              children: [
                Row(
                  children: [
                    _buildButton('sin', color: colorScheme.tertiaryContainer, textColor: colorScheme.onTertiaryContainer),
                    _buildButton('cos', color: colorScheme.tertiaryContainer, textColor: colorScheme.onTertiaryContainer),
                    _buildButton('tan', color: colorScheme.tertiaryContainer, textColor: colorScheme.onTertiaryContainer),
                    _buildButton('log', color: colorScheme.tertiaryContainer, textColor: colorScheme.onTertiaryContainer),
                    _buildButton('ln', color: colorScheme.tertiaryContainer, textColor: colorScheme.onTertiaryContainer),
                  ],
                ),
                Row(
                  children: [
                    _buildButton('sqrt', color: colorScheme.tertiaryContainer, textColor: colorScheme.onTertiaryContainer),
                    _buildButton('x²', color: colorScheme.tertiaryContainer, textColor: colorScheme.onTertiaryContainer),
                    _buildButton('(', color: colorScheme.tertiaryContainer, textColor: colorScheme.onTertiaryContainer),
                    _buildButton(')', color: colorScheme.tertiaryContainer, textColor: colorScheme.onTertiaryContainer),
                    _buildButton('π', color: colorScheme.tertiaryContainer, textColor: colorScheme.onTertiaryContainer),
                  ],
                ),
                const SizedBox(height: 4),
              ],
            ),
          ),
        // Main buttons
        Padding(
          padding: const EdgeInsets.all(4),
          child: Column(
            children: [
              // Memory row
              Row(
                children: [
                  _buildButton('MC', color: colorScheme.secondaryContainer, textColor: colorScheme.onSecondaryContainer),
                  _buildButton('MR', color: colorScheme.secondaryContainer, textColor: colorScheme.onSecondaryContainer),
                  _buildButton('M+', color: colorScheme.secondaryContainer, textColor: colorScheme.onSecondaryContainer),
                  _buildButton('M-', color: colorScheme.secondaryContainer, textColor: colorScheme.onSecondaryContainer),
                  _buildButton('e', color: colorScheme.tertiaryContainer, textColor: colorScheme.onTertiaryContainer),
                ],
              ),
              // Row 1: C, (, ), ⌫, ÷
              Row(
                children: [
                  _buildButton('C', color: colorScheme.error, textColor: colorScheme.onError),
                  _buildButton('(', color: colorScheme.surfaceContainerHighest),
                  _buildButton(')', color: colorScheme.surfaceContainerHighest),
                  _buildButton('⌫', color: colorScheme.surfaceContainerHighest),
                  _buildButton('÷', color: colorScheme.primaryContainer, textColor: colorScheme.onPrimaryContainer),
                ],
              ),
              // Row 2: 7, 8, 9, ×, %
              Row(
                children: [
                  _buildButton('7'),
                  _buildButton('8'),
                  _buildButton('9'),
                  _buildButton('×', color: colorScheme.primaryContainer, textColor: colorScheme.onPrimaryContainer),
                  _buildButton('%', color: colorScheme.surfaceContainerHighest),
                ],
              ),
              // Row 3: 4, 5, 6, -, +/-
              Row(
                children: [
                  _buildButton('4'),
                  _buildButton('5'),
                  _buildButton('6'),
                  _buildButton('-', color: colorScheme.primaryContainer, textColor: colorScheme.onPrimaryContainer),
                  _buildButton('+/-', color: colorScheme.surfaceContainerHighest),
                ],
              ),
              // Row 4: 1, 2, 3, +, =
              Row(
                children: [
                  _buildButton('1'),
                  _buildButton('2'),
                  _buildButton('3'),
                  _buildButton('+', color: colorScheme.primaryContainer, textColor: colorScheme.onPrimaryContainer),
                  _buildButton('=', color: Colors.green, textColor: Colors.white, flex: 1),
                ],
              ),
              // Row 5: 0 (wide), ., =
              Row(
                children: [
                  _buildButton('0', flex: 2, isLarge: true),
                  _buildButton('.'),
                  _buildButton('e', color: colorScheme.tertiaryContainer, textColor: colorScheme.onTertiaryContainer),
                ],
              ),
            ],
          ),
        ),
      ],
    );
  }
}
