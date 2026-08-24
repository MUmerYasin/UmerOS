/// UmerOS Flutter UI — Loading indicators
/// ======================================
/// Bespoke loading widgets that go beyond the default
/// :class:`CircularProgressIndicator` and :class:`LinearProgressIndicator`.
///
/// The four shipped widgets are:
///
///  * [QuantumDots] — three pulsing dots with a staggered phase, the
///    classic "typing" indicator.
///
///  * [QuantumRing] — a rotating ring of particles that draws a
///    partial arc and rotates it; a small "Q" mark in the centre.
///
///  * [SkeletonBox] — a shimmering placeholder for a block of
///    content.  Use it in lists / cards while the real data is
///    loading.
///
///  * [PulsingDot] — a single dot that breathes; useful for
///    "system is alive" status indicators.
library;

import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'animation_tokens.dart';

/// Three pulsing dots — a classic typing / loading indicator.
class QuantumDots extends StatefulWidget {
  final Color color;
  final double size;
  final Duration period;
  final int count;

  const QuantumDots({
    super.key,
    this.color = Colors.deepPurpleAccent,
    this.size = 8.0,
    this.period = UmerDurations.long2,
    this.count = 3,
  });

  @override
  State<QuantumDots> createState() => _QuantumDotsState();
}

class _QuantumDotsState extends State<QuantumDots>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller =
        AnimationController(vsync: this, duration: widget.period)..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(widget.count, (i) {
        return AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            final t = (_controller.value + i / widget.count) % 1.0;
            final scale = 0.7 + 0.6 * t;
            final opacity = 0.4 + 0.6 * t;
            return Padding(
              padding: EdgeInsets.symmetric(horizontal: widget.size * 0.3),
              child: Container(
                width: widget.size,
                height: widget.size,
                decoration: BoxDecoration(
                  color: widget.color.withValues(alpha: opacity),
                  shape: BoxShape.circle,
                  boxShadow: [
                    BoxShadow(
                      color: widget.color.withValues(alpha: opacity * 0.4),
                      blurRadius: 8,
                    ),
                  ],
                ),
                child: SizedBox(
                  width: widget.size * scale,
                  height: widget.size * scale,
                ),
              ),
            );
          },
        );
      }),
    );
  }
}

/// A rotating arc — like a CircularProgressIndicator but with a
/// longer trail and a small dot at the leading edge.
class QuantumRing extends StatefulWidget {
  final double size;
  final double strokeWidth;
  final Color color;
  final Duration period;

  const QuantumRing({
    super.key,
    this.size = 36.0,
    this.strokeWidth = 3.0,
    this.color = Colors.deepPurpleAccent,
    this.period = UmerDurations.long2,
  });

  @override
  State<QuantumRing> createState() => _QuantumRingState();
}

class _QuantumRingState extends State<QuantumRing>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller =
        AnimationController(vsync: this, duration: widget.period)..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: widget.size,
      height: widget.size,
      child: AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          return CustomPaint(
            painter: _QuantumRingPainter(
              t: _controller.value,
              color: widget.color,
              strokeWidth: widget.strokeWidth,
            ),
          );
        },
      ),
    );
  }
}

class _QuantumRingPainter extends CustomPainter {
  final double t;
  final Color color;
  final double strokeWidth;
  _QuantumRingPainter({
    required this.t,
    required this.color,
    required this.strokeWidth,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final r = math.min(size.width, size.height) / 2 - strokeWidth;

    // Faint background ring
    final bg = Paint()
      ..color = color.withValues(alpha: 0.18)
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth;
    canvas.drawCircle(c, r, bg);

    // Foreground arc — sweeps a 270° arc.
    final fg = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = strokeWidth
      ..strokeCap = StrokeCap.round;
    final rect = Rect.fromCircle(center: c, radius: r);
    canvas.drawArc(rect, t * 2 * math.pi, math.pi * 1.5, false, fg);

    // Leading-edge dot
    final angle = t * 2 * math.pi + math.pi * 1.5;
    final dot = Paint()..color = color;
    canvas.drawCircle(
      Offset(c.dx + r * math.cos(angle), c.dy + r * math.sin(angle)),
      strokeWidth * 0.9,
      dot,
    );
  }

  @override
  bool shouldRepaint(covariant _QuantumRingPainter old) =>
      old.t != t || old.color != color;
}

/// A skeleton placeholder for a single block of content.
///
/// ```dart
/// SkeletonBox(width: 200, height: 18)
/// ```
class SkeletonBox extends StatefulWidget {
  final double? width;
  final double height;
  final BorderRadius? borderRadius;
  final Color baseColor;
  final Color highlightColor;
  final Duration period;

  const SkeletonBox({
    super.key,
    this.width,
    this.height = 14,
    this.borderRadius,
    this.baseColor = const Color(0xFFE0E0E0),
    this.highlightColor = const Color(0xFFF5F5F5),
    this.period = UmerDurations.long2,
  });

  @override
  State<SkeletonBox> createState() => _SkeletonBoxState();
}

class _SkeletonBoxState extends State<SkeletonBox>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller =
        AnimationController(vsync: this, duration: widget.period)..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final t = _controller.value;
        return Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            borderRadius: widget.borderRadius ?? BorderRadius.circular(8),
            gradient: LinearGradient(
              begin: Alignment(-1.0 + t * 2, 0),
              end: Alignment(1.0 + t * 2, 0),
              colors: [
                widget.baseColor,
                widget.highlightColor,
                widget.baseColor,
              ],
              stops: const [0.0, 0.5, 1.0],
            ),
          ),
        );
      },
    );
  }
}

/// A single breathing dot.
class PulsingDot extends StatefulWidget {
  final double size;
  final Color color;
  final Duration period;
  final double maxOpacity;

  const PulsingDot({
    super.key,
    this.size = 10.0,
    this.color = Colors.deepPurpleAccent,
    this.period = UmerDurations.long2,
    this.maxOpacity = 0.8,
  });

  @override
  State<PulsingDot> createState() => _PulsingDotState();
}

class _PulsingDotState extends State<PulsingDot>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller =
        AnimationController(vsync: this, duration: widget.period)..repeat(reverse: true);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _controller,
      builder: (context, _) {
        final t = _controller.value;
        return Container(
          width: widget.size,
          height: widget.size,
          decoration: BoxDecoration(
            color: widget.color.withValues(alpha: widget.maxOpacity * t),
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                color: widget.color.withValues(alpha: 0.4 * t),
                blurRadius: 12,
                spreadRadius: 2,
              ),
            ],
          ),
        );
      },
    );
  }
}
