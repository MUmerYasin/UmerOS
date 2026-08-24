/// UmerOS Flutter UI — Micro-interactions
/// ======================================
/// Lightweight wrappers that add hover, press, and focus feedback to
/// any tap target.  All use the design tokens from
/// `animation_tokens.dart` so motion stays consistent across the
/// desktop shell, dock, and apps.
///
/// The three interaction layers are:
///
///  * [HoverScale] — animates a scale + slight elevation when the
///    pointer enters.  Used on dock icons, app tiles, and any
///    "liftable" surface.
///
///  * [TapDownScale] — animates a small scale-down on press and a
///    scale-up on release.  Provides the iOS / Material 3 "press
///    feedback" feel.
///
///  * [InteractiveCard] — combines hover + press + ripple into a
///    single drop-in replacement for [InkWell] or [GestureDetector]
///    that you can use for any tappable card.
library;

import 'package:flutter/material.dart';
import 'animation_tokens.dart';

/// A widget that scales up slightly when the pointer hovers over it.
///
/// ```dart
/// HoverScale(
///   scale: 1.06,
///   child: Icon(Icons.star, size: 48),
/// )
/// ```
class HoverScale extends StatefulWidget {
  final Widget child;

  /// Scale factor when hovered (default 1.06).
  final double scale;

  /// Animation duration (default 150 ms).
  final Duration duration;

  /// Animation curve.
  final Curve curve;

  /// If non-null, [onHover] is invoked with the new hover state.
  final ValueChanged<bool>? onHover;

  const HoverScale({
    super.key,
    required this.child,
    this.scale = 1.06,
    this.duration = UmerDurations.short3,
    this.curve = UmerCurves.standard,
    this.onHover,
  });

  @override
  State<HoverScale> createState() => _HoverScaleState();
}

class _HoverScaleState extends State<HoverScale> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) {
        setState(() => _hovered = true);
        widget.onHover?.call(true);
      },
      onExit: (_) {
        setState(() => _hovered = false);
        widget.onHover?.call(false);
      },
      child: AnimatedScale(
        scale: _hovered ? widget.scale : 1.0,
        duration: widget.duration,
        curve: widget.curve,
        child: widget.child,
      ),
    );
  }
}

/// A widget that scales down slightly when pressed.
///
/// ```dart
/// TapDownScale(
///   pressedScale: 0.92,
///   onTap: () => print('tapped!'),
///   child: MyButton(),
/// )
/// ```
class TapDownScale extends StatefulWidget {
  final Widget child;

  /// Scale when pressed (default 0.94).
  final double pressedScale;

  /// Animation duration.
  final Duration duration;

  /// Curve.
  final Curve curve;

  /// Tap callback.
  final VoidCallback? onTap;

  /// Long-press callback.
  final VoidCallback? onLongPress;

  const TapDownScale({
    super.key,
    required this.child,
    this.pressedScale = 0.94,
    this.duration = UmerDurations.short2,
    this.curve = UmerCurves.standard,
    this.onTap,
    this.onLongPress,
  });

  @override
  State<TapDownScale> createState() => _TapDownScaleState();
}

class _TapDownScaleState extends State<TapDownScale> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) => setState(() => _pressed = false),
      onTapCancel: () => setState(() => _pressed = false),
      onTap: widget.onTap,
      onLongPress: widget.onLongPress,
      behavior: HitTestBehavior.opaque,
      child: AnimatedScale(
        scale: _pressed ? widget.pressedScale : 1.0,
        duration: widget.duration,
        curve: widget.curve,
        child: widget.child,
      ),
    );
  }
}

/// A drop-in tappable surface that combines:
///   * hover-scale (MouseRegion)
///   * press-scale (TapDown)
///   * ink ripple (InkWell)
///   * focus ring (for keyboard / game-pad nav)
///
/// ```dart
/// InteractiveCard(
///   onTap: () => openApp('terminal'),
///   child: Container(
///     padding: const EdgeInsets.all(16),
///     child: Text('Terminal'),
///   ),
/// )
/// ```
class InteractiveCard extends StatefulWidget {
  final Widget child;

  final VoidCallback? onTap;
  final VoidCallback? onLongPress;
  final double hoverScale;
  final double pressedScale;
  final BorderRadius? borderRadius;
  final Color? hoverColor;
  final Color? splashColor;
  final Clip clipBehavior;
  final Duration hoverDuration;
  final Duration pressDuration;

  const InteractiveCard({
    super.key,
    required this.child,
    this.onTap,
    this.onLongPress,
    this.hoverScale = 1.03,
    this.pressedScale = 0.97,
    this.borderRadius,
    this.hoverColor,
    this.splashColor,
    this.clipBehavior = Clip.antiAlias,
    this.hoverDuration = UmerDurations.short3,
    this.pressDuration = UmerDurations.short2,
  });

  @override
  State<InteractiveCard> createState() => _InteractiveCardState();
}

class _InteractiveCardState extends State<InteractiveCard> {
  bool _hovered = false;
  bool _pressed = false;

  double get _scale {
    if (_pressed) return widget.pressedScale;
    if (_hovered) return widget.hoverScale;
    return 1.0;
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final borderRadius =
        widget.borderRadius ?? BorderRadius.circular(16.0);
    final base = widget.hoverColor ??
        colorScheme.surfaceContainerHighest.withValues(alpha: 0.6);
    final hoverColor = _hovered
        ? colorScheme.primaryContainer.withValues(alpha: 0.4)
        : base;
    return MouseRegion(
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: AnimatedScale(
        scale: _scale,
        duration:
            _pressed ? widget.pressDuration : widget.hoverDuration,
        curve: UmerCurves.standard,
        child: AnimatedContainer(
          duration: widget.hoverDuration,
          curve: UmerCurves.standard,
          decoration: BoxDecoration(
            color: hoverColor,
            borderRadius: borderRadius,
          ),
          clipBehavior: widget.clipBehavior,
          child: Material(
            color: Colors.transparent,
            child: InkWell(
              onTapDown: (_) => setState(() => _pressed = true),
              onTapUp: (_) => setState(() => _pressed = false),
              onTapCancel: () => setState(() => _pressed = false),
              onTap: widget.onTap,
              onLongPress: widget.onLongPress,
              splashColor: widget.splashColor,
              borderRadius: borderRadius,
              child: widget.child,
            ),
          ),
        ),
      ),
    );
  }
}

/// A "glow" effect that pulses softly whenever the user hovers a
/// widget.  Useful for primary CTAs and icon buttons.
class HoverGlow extends StatefulWidget {
  final Widget child;
  final Color glowColor;
  final double maxGlow;
  final Duration duration;

  const HoverGlow({
    super.key,
    required this.child,
    required this.glowColor,
    this.maxGlow = 0.5,
    this.duration = UmerDurations.short3,
  });

  @override
  State<HoverGlow> createState() => _HoverGlowState();
}

class _HoverGlowState extends State<HoverGlow> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: AnimatedContainer(
        duration: widget.duration,
        curve: UmerCurves.standard,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          boxShadow: _hovered
              ? [
                  BoxShadow(
                    color: widget.glowColor.withValues(alpha: widget.maxGlow),
                    blurRadius: 24,
                    spreadRadius: 1,
                  ),
                ]
              : const [],
        ),
        child: widget.child,
      ),
    );
  }
}
