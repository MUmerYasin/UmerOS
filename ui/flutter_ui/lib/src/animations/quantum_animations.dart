/// UmerOS Flutter UI — Quantum animations
/// ======================================
/// Quantum-themed motion that mirrors the project's "Hybrid Quantum
/// AI Operating System" identity.  These are the signature animations
/// used on the splash screen, the quantum simulator, the boot manager
/// and anywhere else the OS needs to remind the user it is **not** a
/// beige Linux desktop.
///
/// The three signature effects are:
///
///  * [QuantumOrb] — a glowing sphere with a probability-cloud
///    halo that breathes continuously.  Use it as a logo, a
///    loading marker, or a hero element on a screen.
///
///  * [QuantumParticleField] — N particles that follow
///    "wave-function" trajectories (superposed sine waves) and
///    randomly collapse, then re-superpose.  Use it as a background
///    for the splash or as a hero on the quantum app.
///
///  * [QuantumBootProgress] — a layered progress bar that fills
///    in three "phases" (init, coherence, measurement) to mimic a
///    quantum state-preparation + measurement cycle.
library;

import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'animation_tokens.dart';
import 'widget_animations.dart';

/// A breathing, glowing orb.  Animates a continuous pulse + slow
/// rotation.  Drop it anywhere a logo is needed.
///
/// ```dart
/// const QuantumOrb(size: 80, color: Colors.deepPurpleAccent)
/// ```
class QuantumOrb extends StatefulWidget {
  final double size;
  final Color color;
  final double pulseAmplitude;
  final Duration pulseDuration;
  final bool rotate;

  const QuantumOrb({
    super.key,
    this.size = 64,
    this.color = Colors.deepPurpleAccent,
    this.pulseAmplitude = 0.18,
    this.pulseDuration = UmerDurations.long2,
    this.rotate = true,
  });

  @override
  State<QuantumOrb> createState() => _QuantumOrbState();
}

class _QuantumOrbState extends State<QuantumOrb>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: widget.pulseDuration,
    )..repeat();
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
        final pulse = 1.0 +
            widget.pulseAmplitude *
                math.sin(t * 2 * math.pi);
        final halo = 0.4 + 0.4 * (0.5 + 0.5 * math.sin(t * 2 * math.pi));
        return SizedBox(
          width: widget.size * 1.6,
          height: widget.size * 1.6,
          child: Stack(
            alignment: Alignment.center,
            children: [
              // Outer probability cloud
              Container(
                width: widget.size * 1.4,
                height: widget.size * 1.4,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  gradient: RadialGradient(
                    colors: [
                      widget.color.withValues(alpha: halo * 0.45),
                      widget.color.withValues(alpha: 0.0),
                    ],
                  ),
                ),
              ),
              // Orb itself
              Transform.rotate(
                angle: widget.rotate ? t * 2 * math.pi : 0,
                child: Container(
                  width: widget.size * pulse,
                  height: widget.size * pulse,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    gradient: RadialGradient(
                      colors: [
                        widget.color.withValues(alpha: 0.95),
                        widget.color.withValues(alpha: 0.55),
                      ],
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: widget.color.withValues(alpha: 0.55),
                        blurRadius: 24,
                        spreadRadius: 4,
                      ),
                    ],
                  ),
                  child: CustomPaint(painter: _OrbRingsPainter(
                    color: widget.color,
                    rotation: t,
                  )),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

class _OrbRingsPainter extends CustomPainter {
  final Color color;
  final double rotation;
  _OrbRingsPainter({required this.color, required this.rotation});

  @override
  void paint(Canvas canvas, Size size) {
    final c = size.center(Offset.zero);
    final p1 = Paint()
      ..color = Colors.white.withValues(alpha: 0.35)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;
    final p2 = Paint()
      ..color = Colors.white.withValues(alpha: 0.25)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1.0;
    canvas.save();
    canvas.translate(c.dx, c.dy);
    canvas.rotate(rotation);
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset.zero,
        width: size.width * 0.78,
        height: size.height * 0.42,
      ),
      0,
      math.pi,
      false,
      p1,
    );
    canvas.rotate(math.pi / 1.7);
    canvas.drawArc(
      Rect.fromCenter(
        center: Offset.zero,
        width: size.width * 0.78,
        height: size.height * 0.42,
      ),
      0,
      math.pi,
      false,
      p2,
    );
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _OrbRingsPainter old) =>
      old.rotation != rotation || old.color != color;
}

/// A field of [count] particles that follow superposed sine waves
/// across the available space.  Each particle has a random phase,
/// frequency, and amplitude — the visual effect is a shimmering
/// quantum "fog".
class QuantumParticleField extends StatefulWidget {
  final int count;
  final Color color;
  final double maxRadius;
  final Duration period;
  final Widget? foreground;

  const QuantumParticleField({
    super.key,
    this.count = 48,
    this.color = Colors.deepPurpleAccent,
    this.maxRadius = 2.0,
    this.period = UmerDurations.long2,
    this.foreground,
  });

  @override
  State<QuantumParticleField> createState() => _QuantumParticleFieldState();
}

class _QuantumParticleFieldState extends State<QuantumParticleField>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final List<_Particle> _particles;
  final math.Random _rng = math.Random(42);

  @override
  void initState() {
    super.initState();
    _controller =
        AnimationController(vsync: this, duration: widget.period)..repeat();
    _particles = List.generate(widget.count, (_) => _Particle.random(_rng));
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, constraints) {
        final w = constraints.maxWidth;
        final h = constraints.maxHeight;
        return AnimatedBuilder(
          animation: _controller,
          builder: (context, _) {
            return CustomPaint(
              painter: _ParticleFieldPainter(
                t: _controller.value,
                particles: _particles,
                color: widget.color,
                size: Size(w, h),
                maxRadius: widget.maxRadius,
              ),
              child: widget.foreground,
            );
          },
        );
      },
    );
  }
}

class _Particle {
  final double baseX;     // 0..1
  final double baseY;     // 0..1
  final double phase;     // 0..2π
  final double freqX;     // Hz
  final double freqY;
  final double ampX;      // 0..0.1
  final double ampY;
  final double size;      // 0..1
  final double fadePhase; // 0..2π
  _Particle({
    required this.baseX,
    required this.baseY,
    required this.phase,
    required this.freqX,
    required this.freqY,
    required this.ampX,
    required this.ampY,
    required this.size,
    required this.fadePhase,
  });
  factory _Particle.random(math.Random r) => _Particle(
        baseX: r.nextDouble(),
        baseY: r.nextDouble(),
        phase: r.nextDouble() * 2 * math.pi,
        freqX: 0.6 + r.nextDouble() * 0.8,
        freqY: 0.6 + r.nextDouble() * 0.8,
        ampX: 0.04 + r.nextDouble() * 0.06,
        ampY: 0.04 + r.nextDouble() * 0.06,
        size: 0.4 + r.nextDouble() * 0.6,
        fadePhase: r.nextDouble() * 2 * math.pi,
      );
}

class _ParticleFieldPainter extends CustomPainter {
  final double t;
  final List<_Particle> particles;
  final Color color;
  final Size size;
  final double maxRadius;

  _ParticleFieldPainter({
    required this.t,
    required this.particles,
    required this.color,
    required this.size,
    required this.maxRadius,
  });

  @override
  void paint(Canvas canvas, Size s) {
    final paint = Paint()..color = color.withValues(alpha: 0.85);
    for (final p in particles) {
      final x = (p.baseX +
              math.sin(t * 2 * math.pi * p.freqX + p.phase) * p.ampX) *
          s.width;
      final y = (p.baseY +
              math.cos(t * 2 * math.pi * p.freqY + p.phase) * p.ampY) *
          s.height;
      final fade = (0.5 + 0.5 * math.sin(t * 2 * math.pi + p.fadePhase));
      paint.color = color.withValues(alpha: 0.25 + fade * 0.65);
      canvas.drawCircle(Offset(x, y), maxRadius * p.size, paint);
    }
  }

  @override
  bool shouldRepaint(covariant _ParticleFieldPainter old) =>
      old.t != t || old.color != color;
}

/// A three-phase boot-style progress bar:
///   1. **init**       — initialise qubits
///   2. **coherence**  — apply gates, build superposition
///   3. **measurement** — collapse to a classical state
///
/// The phases light up in sequence with a soft sweep animation.
///
/// ```dart
/// QuantumBootProgress(value: 0.7)
/// ```
class QuantumBootProgress extends StatelessWidget {
  final double value;
  final Color color;
  final double height;

  const QuantumBootProgress({
    super.key,
    required this.value,
    this.color = Colors.deepPurpleAccent,
    this.height = 8.0,
  });

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(builder: (context, constraints) {
      final w = constraints.maxWidth;
      return SizedBox(
        height: height,
        child: Stack(
          children: [
            // Track
            Container(
              decoration: BoxDecoration(
                color: color.withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(height / 2),
              ),
            ),
            // Phase markers
            for (int i = 0; i < 3; i++)
              Positioned(
                left: w * (i / 3),
                top: 0,
                bottom: 0,
                child: Container(
                  width: 2,
                  color: color.withValues(alpha: 0.55),
                ),
              ),
            // Sweep
            AnimatedContainer(
              duration: UmerDurations.medium2,
              curve: UmerCurves.emphasized,
              width: w * value.clamp(0.0, 1.0),
              decoration: BoxDecoration(
                gradient: LinearGradient(
                  colors: [
                    color.withValues(alpha: 0.6),
                    color,
                  ],
                ),
                borderRadius: BorderRadius.circular(height / 2),
                boxShadow: [
                  BoxShadow(
                    color: color.withValues(alpha: 0.6),
                    blurRadius: 8,
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    });
  }
}

/// A "splash" that fades a [QuantumOrb] + brand name in from black,
/// then holds.  Use it on app startup.
class QuantumSplash extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Color color;
  final VoidCallback? onComplete;

  const QuantumSplash({
    super.key,
    this.title = 'UmerOS',
    this.subtitle,
    this.color = Colors.deepPurpleAccent,
    this.onComplete,
  });

  @override
  Widget build(BuildContext context) {
    return Material(
      color: Colors.black,
      child: Stack(
        fit: StackFit.expand,
        children: [
          const QuantumParticleField(
            count: 80,
            color: Colors.deepPurpleAccent,
          ),
          Center(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                FadeInOnMount(
                  delay: const Duration(milliseconds: 200),
                  child: QuantumOrb(size: 96, color: color),
                ),
                const SizedBox(height: 24),
                ScaleInOnMount(
                  begin: 0.7,
                  delay: const Duration(milliseconds: 600),
                  child: Text(
                    title,
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 32,
                      fontWeight: FontWeight.w300,
                      letterSpacing: 6,
                    ),
                  ),
                ),
                if (subtitle != null) ...[
                  const SizedBox(height: 8),
                  FadeInOnMount(
                    delay: const Duration(milliseconds: 1100),
                    child: Text(
                      subtitle!,
                      style: TextStyle(
                        color: Colors.white.withValues(alpha: 0.6),
                        fontSize: 14,
                        letterSpacing: 2,
                      ),
                    ),
                  ),
                ],
                const SizedBox(height: 32),
                FadeInOnMount(
                  delay: const Duration(milliseconds: 1400),
                  child: SizedBox(
                    width: 200,
                    child: QuantumBootProgress(
                      value: 0.0,
                      color: color,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
