/// UmerOS Flutter UI — Page transitions
/// =====================================
/// Custom :class:`PageRouteBuilder` implementations that give every
/// route a consistent, on-brand motion.
///
/// Three transitions ship in this file:
///
///  * [UmerFadeRoute] — opacity 0→1 + small Y-translation.  Default
///    for modal dialogs and modal sheets.
///
///  * [UmerSlideRoute] — slide-in from the right, used for app
///    navigation and the standard "push" of an app body.
///
///  * [UmerZoomRoute] — scale + fade.  Used when entering a focused
///    task (e.g. opening a single app from the launcher).
///
/// All three use the [UmerMotion] tokens so timing stays in sync with
/// the rest of the UI.
library;

import 'package:flutter/material.dart';
import 'animation_tokens.dart';

/// A page route that fades and translates the new page in.
class UmerFadeRoute<T> extends PageRouteBuilder<T> {
  UmerFadeRoute({
    required WidgetBuilder builder,
    super.settings,
    super.transitionDuration = UmerDurations.medium3,
    super.reverseTransitionDuration = UmerDurations.short4,
  }) : super(
          pageBuilder: (context, animation, secondaryAnimation) =>
              builder(context),
          transitionsBuilder: (context, animation, secondaryAnimation, child) {
            final spec = UmerMotion.of(UmerMotionIntent.fadeIn);
            final curved =
                CurvedAnimation(parent: animation, curve: spec.curve);
            final offsetTween = Tween<Offset>(
              begin: const Offset(0, 0.04),
              end: Offset.zero,
            ).animate(curved);
            return FadeTransition(
              opacity: curved,
              child: SlideTransition(position: offsetTween, child: child),
            );
          },
        );
}

/// A page route that slides the new page in from the right.
class UmerSlideRoute<T> extends PageRouteBuilder<T> {
  UmerSlideRoute({
    required WidgetBuilder builder,
    super.settings,
    super.transitionDuration = UmerDurations.medium3,
    super.reverseTransitionDuration = UmerDurations.short4,
  }) : super(
          pageBuilder: (context, animation, secondaryAnimation) =>
              builder(context),
          transitionsBuilder: (context, animation, secondaryAnimation, child) {
            final spec = UmerMotion.of(UmerMotionIntent.slide);
            final curved =
                CurvedAnimation(parent: animation, curve: spec.curve);
            final offsetTween = Tween<Offset>(
              begin: const Offset(0.2, 0),
              end: Offset.zero,
            ).animate(curved);
            return SlideTransition(
              position: offsetTween,
              child: FadeTransition(opacity: curved, child: child),
            );
          },
        );
}

/// A page route that zooms in (scale + fade).  Used for focused
/// tasks (single-app launch, document viewer).
class UmerZoomRoute<T> extends PageRouteBuilder<T> {
  UmerZoomRoute({
    required WidgetBuilder builder,
    super.settings,
    super.transitionDuration = UmerDurations.medium3,
    super.reverseTransitionDuration = UmerDurations.short4,
  }) : super(
          pageBuilder: (context, animation, secondaryAnimation) =>
              builder(context),
          transitionsBuilder: (context, animation, secondaryAnimation, child) {
            final spec = UmerMotion.of(UmerMotionIntent.scale);
            final curved =
                CurvedAnimation(parent: animation, curve: spec.curve);
            final scaleTween = Tween<double>(begin: 0.9, end: 1.0)
                .animate(curved);
            return FadeTransition(
              opacity: curved,
              child: ScaleTransition(scale: scaleTween, child: child),
            );
          },
        );
}

/// A page route for modals (sheet / dialog) that uses a vertical
/// slide-up + fade.
class UmerModalRoute<T> extends PageRouteBuilder<T> {
  UmerModalRoute({
    required WidgetBuilder builder,
    super.settings,
    super.transitionDuration = UmerDurations.medium4,
    super.reverseTransitionDuration = UmerDurations.short4,
    super.barrierDismissible = true,
  }) : super(
          opaque: false,
          barrierColor: Colors.black54,
          pageBuilder: (context, animation, secondaryAnimation) =>
              builder(context),
          transitionsBuilder: (context, animation, secondaryAnimation, child) {
            final spec = UmerMotion.of(UmerMotionIntent.modalOpen);
            final curved =
                CurvedAnimation(parent: animation, curve: spec.curve);
            final offsetTween = Tween<Offset>(
              begin: const Offset(0, 0.1),
              end: Offset.zero,
            ).animate(curved);
            return SlideTransition(
              position: offsetTween,
              child: FadeTransition(opacity: curved, child: child),
            );
          },
        );
}
