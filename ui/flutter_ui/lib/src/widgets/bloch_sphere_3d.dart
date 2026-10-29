/// 3D Bloch Sphere Visualization Widget
///
/// Renders a 3D Bloch sphere using CustomPaint with perspective
/// projection. Supports rotation, zoom, and state vector display.
library;

import 'dart:math' as math;
import 'package:flutter/material.dart';

class BlochSphere3D extends StatefulWidget {
  const BlochSphere3D({
    super.key,
    this.theta = 0.0,
    this.phi = 0.0,
    this.color = Colors.cyan,
    this.size = 300.0,
  });

  final double theta; // polar angle (0 to pi)
  final double phi;   // azimuthal angle (0 to 2pi)
  final Color color;
  final double size;

  @override
  State<BlochSphere3D> createState() => _BlochSphere3DState();
}

class _BlochSphere3DState extends State<BlochSphere3D> {
  double _rotX = 0.3;
  double _rotY = 0.5;
  final double _zoom = 1.0;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onPanUpdate: (details) {
        setState(() {
          _rotY += details.delta.dx * 0.01;
          _rotX += details.delta.dy * 0.01;
        });
      },
      child: CustomPaint(
        size: Size(widget.size, widget.size),
        painter: _BlochSphere3DPainter(
          theta: widget.theta,
          phi: widget.phi,
          color: widget.color,
          rotX: _rotX,
          rotY: _rotY,
          zoom: _zoom,
        ),
      ),
    );
  }
}

class _BlochSphere3DPainter extends CustomPainter {
  _BlochSphere3DPainter({
    required this.theta,
    required this.phi,
    required this.color,
    required this.rotX,
    required this.rotY,
    required this.zoom,
  });

  final double theta;
  final double phi;
  final Color color;
  final double rotX;
  final double rotY;
  final double zoom;

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 * 0.85 * zoom;

    // Draw sphere wireframe (equator + meridians)
    _drawWireframe(canvas, center, radius);

    // Draw axes
    _drawAxes(canvas, center, radius);

    // Draw state vector
    _drawStateVector(canvas, center, radius);

    // Draw labels
    _drawLabels(canvas, center, radius);
  }

  void _drawWireframe(Canvas canvas, Offset center, double radius) {
    final paint = Paint()
      ..color = Colors.grey.withValues(alpha: 0.3)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 0.5;

    // Equator circle
    canvas.drawCircle(center, radius, paint);

    // Meridian circles (rotated)
    for (var i = 0; i < 3; i++) {
      final angle = i * math.pi / 3;
      final path = Path();
      for (var j = 0; j <= 64; j++) {
        final t = j / 64 * 2 * math.pi;
        final x = radius * math.cos(t) * math.cos(angle);
        final y = radius * math.sin(t);
        final z = radius * math.cos(t) * math.sin(angle);
        final (px, py) = _project(x, y, z, radius);
        if (j == 0) {
          path.moveTo(center.dx + px, center.dy + py);
        } else {
          path.lineTo(center.dx + px, center.dy + py);
        }
      }
      canvas.drawPath(path, paint);
    }
  }

  void _drawAxes(Canvas canvas, Offset center, double radius) {
    final paint = Paint()
      ..color = Colors.grey.withValues(alpha: 0.5)
      ..strokeWidth = 1.0;

    // X axis (red)
    final (x1, y1) = _project(radius, 0, 0, radius);
    final (x2, y2) = _project(-radius, 0, 0, radius);
    canvas.drawLine(Offset(center.dx + x1, center.dy + y1), Offset(center.dx + x2, center.dy + y2), paint..color = Colors.red.withValues(alpha: 0.6));

    // Y axis (green)
    final (y1a, y1b) = _project(0, radius, 0, radius);
    final (y2a, y2b) = _project(0, -radius, 0, radius);
    canvas.drawLine(Offset(center.dx + y1a, center.dy + y1b), Offset(center.dx + y2a, center.dy + y2b), paint..color = Colors.green.withValues(alpha: 0.6));

    // Z axis (blue)
    final (z1a, z1b) = _project(0, 0, radius, radius);
    final (z2a, z2b) = _project(0, 0, -radius, radius);
    canvas.drawLine(Offset(center.dx + z1a, center.dy + z1b), Offset(center.dx + z2a, center.dy + z2b), paint..color = Colors.blue.withValues(alpha: 0.6));
  }

  void _drawStateVector(Canvas canvas, Offset center, double radius) {
    // Convert spherical to Cartesian
    final x = radius * math.sin(theta) * math.cos(phi);
    final y = radius * math.sin(theta) * math.sin(phi);
    final z = radius * math.cos(theta);

    final (px, py) = _project(x, y, z, radius);

    // Draw line from origin to point
    final linePaint = Paint()
      ..color = color
      ..strokeWidth = 2.5
      ..strokeCap = StrokeCap.round;
    canvas.drawLine(center, Offset(center.dx + px, center.dy + py), linePaint);

    // Draw point
    final pointPaint = Paint()
      ..color = color
      ..style = PaintingStyle.fill;
    canvas.drawCircle(Offset(center.dx + px, center.dy + py), 6, pointPaint);

    // Glow
    final glowPaint = Paint()
      ..color = color.withValues(alpha: 0.3)
      ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 8);
    canvas.drawCircle(Offset(center.dx + px, center.dy + py), 10, glowPaint);
  }

  void _drawLabels(Canvas canvas, Offset center, double radius) {
    final textStyle = TextStyle(fontSize: 10, color: Colors.grey.shade600);
    final textPainter = TextPainter(textDirection: TextDirection.ltr);

    // |0> label
    final (zx, zy) = _project(0, 0, radius + 15, radius);
    textPainter.text = TextSpan(text: '|0⟩', style: textStyle);
    textPainter.layout();
    textPainter.paint(canvas, Offset(center.dx + zx - textPainter.width / 2, center.dy + zy - textPainter.height / 2));

    // |1> label
    final (zx2, zy2) = _project(0, 0, -radius - 15, radius);
    textPainter.text = TextSpan(text: '|1⟩', style: textStyle);
    textPainter.layout();
    textPainter.paint(canvas, Offset(center.dx + zx2 - textPainter.width / 2, center.dy + zy2 - textPainter.height / 2));

    // |+> label
    final (x1, y1) = _project(radius + 15, 0, 0, radius);
    textPainter.text = TextSpan(text: '|+⟩', style: textStyle);
    textPainter.layout();
    textPainter.paint(canvas, Offset(center.dx + x1 - textPainter.width / 2, center.dy + y1 - textPainter.height / 2));
  }

  (double, double) _project(double x, double y, double z, double radius) {
    // Rotate around Y axis
    final cosY = math.cos(rotY);
    final sinY = math.sin(rotY);
    final x1 = x * cosY + z * sinY;
    final z1 = -x * sinY + z * cosY;

    // Rotate around X axis
    final cosX = math.cos(rotX);
    final sinX = math.sin(rotX);
    final y1 = y * cosX - z1 * sinX;
    final z2 = y * sinX + z1 * cosX;

    // Perspective projection
    final perspective = 1.0 / (1.0 + z2 / (radius * 3));
    return (x1 * perspective, y1 * perspective);
  }

  @override
  bool shouldRepaint(covariant _BlochSphere3DPainter old) {
    return old.theta != theta || old.phi != phi || old.rotX != rotX || old.rotY != rotY || old.zoom != zoom;
  }
}