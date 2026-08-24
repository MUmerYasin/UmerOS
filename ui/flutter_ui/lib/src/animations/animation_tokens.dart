/// UmerOS Flutter UI — Animation tokens
/// =====================================
/// Centralised design tokens for **all** animations in the Flutter UI so
/// that motion is consistent across every screen, widget, and transition.
///
/// The two token groups are:
///
///  * [UmerMotion] — a single static surface that exposes a canonical
///    :class:`Duration` and :class:`Curve` for every motion "intention":
///    hover, press, fade-in, page-transition, splash, error, success,
///    loading, etc.  Use these instead of hard-coding values in widgets.
///
///  * The two extension types (:class:`UmerCurves` and :class:`UmerDurations`)
///    give a more functional feel — call sites read
///    ``UmerCurves.emphasized`` / ``UmerDurations.short3`` directly.
///
/// Material 3 motion principles are baked in: every duration is
/// between 100 ms (perceptible) and 600 ms (no waiting), every curve
/// is on the "emphasized" / "standard" / "decelerate" set so the
/// motion feels cohesive across the desktop shell, dock, windows and
/// app bodies.
///
/// Reference:
///   * https://m3.material.io/styles/motion/overview
///   * https://api.flutter.dev/flutter/animation/Curves-class.html
library;

import 'package:flutter/animation.dart';

/// Standard easing curves used across the UmerOS UI.
///
/// Material 3 "emphasized" is the **default** for any entry / exit
/// transition; "standard" is the curve for property changes such as
/// colour or size.  "Decelerate" is used when something is entering
/// the screen and "accelerate" when it is leaving.
class UmerCurves {
  const UmerCurves._();

  /// Material 3 **emphasized** curve — the default for new transitions.
  /// A composed cubic-bezier of (0.2, 0, 0, 1) and (0, 0, 0, 1).
  static const Curve emphasized = Cubic(0.2, 0.0, 0.0, 1.0);

  /// Material 3 **standard** curve — for property changes (colour, size).
  static const Curve standard = Cubic(0.2, 0.0, 0.0, 1.0);

  /// Decelerate — used for elements entering the screen.
  static const Curve decelerate = Curves.easeOutCubic;

  /// Accelerate — used for elements leaving the screen.
  static const Curve accelerate = Curves.easeInCubic;

  /// Overshoot — used for bounces (dock icon scale-up, success states).
  static const Curve overshoot = Curves.elasticOut;

  /// Spring / "back" — used for dock hover and modal pop.
  static const Curve spring = Curves.easeOutBack;

  /// Linear — used for loops (spinners, pulse).
  static const Curve linear = Curves.linear;
}

/// Canonical duration buckets (Material 3 motion scale).
///
/// | Bucket | Range        | Use                                          |
/// |--------|--------------|----------------------------------------------|
/// | short  | 50–200 ms    | micro-interactions, hover, press             |
/// | medium | 200–400 ms   | state changes, focus, page transitions       |
/// | long   | 400–600 ms   | entrance, splash, hero, open/close window    |
class UmerDurations {
  const UmerDurations._();

  // Short bucket (50–200 ms)

  /// 50 ms — fastest perceptible change.
  static const Duration short1 = Duration(milliseconds: 50);

  /// 100 ms — quick state change.
  static const Duration short2 = Duration(milliseconds: 100);

  /// 150 ms — default hover, small property change.
  static const Duration short3 = Duration(milliseconds: 150);

  /// 200 ms — press feedback, ripple, minor scale.
  static const Duration short4 = Duration(milliseconds: 200);

  // Medium bucket (200–400 ms)

  /// 250 ms — focus state, icon swap.
  static const Duration medium1 = Duration(milliseconds: 250);

  /// 300 ms — default state change (chip selection, toggle).
  static const Duration medium2 = Duration(milliseconds: 300);

  /// 350 ms — page transition.
  static const Duration medium3 = Duration(milliseconds: 350);

  /// 400 ms — modal open.
  static const Duration medium4 = Duration(milliseconds: 400);

  // Long bucket (400–600 ms)

  /// 450 ms — drawer / sheet open.
  static const Duration long1 = Duration(milliseconds: 450);

  /// 500 ms — default entrance, window open.
  static const Duration long2 = Duration(milliseconds: 500);

  /// 600 ms — splash, hero transition, large entrance.
  static const Duration long3 = Duration(milliseconds: 600);
}

/// "Intent" — a semantic mapping from a design purpose to a
/// duration+curve pair.  This is the recommended way to wire
/// animations: pick the intent that matches the action, and let
/// the tokens translate it into raw values.
enum UmerMotionIntent {
  /// A pointer entered or left a tappable region.
  hover,

  /// A button or list item is pressed.
  press,

  /// A widget faded in (mounted, setState visibility).
  fadeIn,

  /// A widget is fading out (about to unmount).
  fadeOut,

  /// A scale change (dock icon hover, modal pop).
  scale,

  /// A slide / translate change.
  slide,

  /// A full page transition (push, pop, replace).
  pageTransition,

  /// A modal opening.
  modalOpen,

  /// A modal closing.
  modalClose,

  /// A splash screen reveal.
  splash,

  /// An error shake.
  error,

  /// A success pulse.
  success,

  /// A continuous loop (spinner, pulse, breathing).
  loop,

  /// A property change (color, opacity, size) on an existing widget.
  property,
}

/// Static facade that returns the canonical [Duration] and [Curve]
/// for a given [UmerMotionIntent].  Use this from widgets so a single
/// change in the design system ripples across the entire UI:
///
/// ```dart
/// final spec = UmerMotion.of(UmerMotionIntent.pageTransition);
/// final controller = AnimationController(
///   vsync: this,
///   duration: spec.duration,
/// );
/// ```
class UmerMotion {
  const UmerMotion._();

  /// A pair of (duration, curve) returned for a given intent.
  static UmerMotionSpec of(UmerMotionIntent intent) {
    switch (intent) {
      case UmerMotionIntent.hover:
        return const UmerMotionSpec(
          duration: UmerDurations.short3,
          curve: UmerCurves.standard,
        );
      case UmerMotionIntent.press:
        return const UmerMotionSpec(
          duration: UmerDurations.short4,
          curve: UmerCurves.standard,
        );
      case UmerMotionIntent.fadeIn:
        return const UmerMotionSpec(
          duration: UmerDurations.medium2,
          curve: UmerCurves.decelerate,
        );
      case UmerMotionIntent.fadeOut:
        return const UmerMotionSpec(
          duration: UmerDurations.short4,
          curve: UmerCurves.accelerate,
        );
      case UmerMotionIntent.scale:
        return const UmerMotionSpec(
          duration: UmerDurations.short4,
          curve: UmerCurves.spring,
        );
      case UmerMotionIntent.slide:
        return const UmerMotionSpec(
          duration: UmerDurations.medium2,
          curve: UmerCurves.emphasized,
        );
      case UmerMotionIntent.pageTransition:
        return const UmerMotionSpec(
          duration: UmerDurations.medium3,
          curve: UmerCurves.emphasized,
        );
      case UmerMotionIntent.modalOpen:
        return const UmerMotionSpec(
          duration: UmerDurations.medium4,
          curve: UmerCurves.decelerate,
        );
      case UmerMotionIntent.modalClose:
        return const UmerMotionSpec(
          duration: UmerDurations.short4,
          curve: UmerCurves.accelerate,
        );
      case UmerMotionIntent.splash:
        return const UmerMotionSpec(
          duration: UmerDurations.long3,
          curve: UmerCurves.emphasized,
        );
      case UmerMotionIntent.error:
        return const UmerMotionSpec(
          duration: UmerDurations.medium2,
          curve: UmerCurves.standard,
        );
      case UmerMotionIntent.success:
        return const UmerMotionSpec(
          duration: UmerDurations.long2,
          curve: UmerCurves.overshoot,
        );
      case UmerMotionIntent.loop:
        return const UmerMotionSpec(
          duration: UmerDurations.long2,
          curve: UmerCurves.linear,
        );
      case UmerMotionIntent.property:
        return const UmerMotionSpec(
          duration: UmerDurations.short3,
          curve: UmerCurves.standard,
        );
    }
  }
}

/// An immutable pair of (duration, curve) used by [UmerMotion.of].
class UmerMotionSpec {
  final Duration duration;
  final Curve curve;

  const UmerMotionSpec({
    required this.duration,
    required this.curve,
  });

  @override
  String toString() => 'UmerMotionSpec($duration, $curve)';
}
