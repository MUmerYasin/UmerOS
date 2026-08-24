/// UmerOS Flutter UI — Widget animation wrappers
/// =============================================
/// Drop-in animation widgets that wrap any [child] in a common motion
/// pattern: fade-in, slide-in, scale-in, stagger, etc.
///
/// All wrappers:
///
///  * read their [Duration] / [Curve] from [UmerMotion] tokens
///  * use [flutter_animate] **and** the barebones [AnimationController]
///    + [Tween] for portability
///  * trigger on first build (use [key] to force re-trigger)
///  * do not block the build pipeline (synchronous on the first frame)
library;

import 'package:flutter/material.dart';
import 'animation_tokens.dart';

/// Fades [child] in from 0→1 opacity the first time it is mounted.
///
/// ```dart
/// FadeInOnMount(
///   delay: const Duration(milliseconds: 100),
///   child: MyWidget(),
/// )
/// ```
class FadeInOnMount extends StatefulWidget {
  /// The widget to animate in.
  final Widget child;

  /// How long the fade should take.  Defaults to
  /// [UmerMotionIntent.fadeIn] (300 ms, decelerate).
  final Duration duration;

  /// Optional delay before the fade starts.
  final Duration delay;

  /// Curve to use (default: [UmerCurves.decelerate]).
  final Curve curve;

  /// Fade from 0 to 1 when true; reverse direction when false.
  final bool fadeIn;

  const FadeInOnMount({
    super.key,
    required this.child,
    this.duration = UmerDurations.medium2,
    this.curve = UmerCurves.decelerate,
    this.delay = Duration.zero,
    this.fadeIn = true,
  });

  @override
  State<FadeInOnMount> createState() => _FadeInOnMountState();
}

class _FadeInOnMountState extends State<FadeInOnMount>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _opacity;

  @override
  void initState() {
    super.initState();
    final spec = UmerMotion.of(
      widget.fadeIn ? UmerMotionIntent.fadeIn : UmerMotionIntent.fadeOut,
    );
    _controller = AnimationController(
      vsync: this,
      duration: widget.duration == UmerDurations.medium2
          ? spec.duration
          : widget.duration,
    );
    _opacity = CurvedAnimation(
      parent: _controller,
      curve: widget.curve,
    );
    if (widget.fadeIn) {
      _controller.value = 0;
      Future.delayed(widget.delay, () {
        if (mounted) _controller.forward();
      });
    } else {
      _controller.value = 1;
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _opacity,
      child: widget.child,
    );
  }
}

/// Slides [child] in from [from] to its natural position, with an
/// optional fade-in.
class SlideInOnMount extends StatefulWidget {
  /// The widget to animate in.
  final Widget child;

  /// Direction the slide should originate from.
  final SlideDirection direction;

  /// Distance to travel (default 32 px).
  final double distance;

  /// Animation duration.
  final Duration duration;

  /// Animation delay.
  final Duration delay;

  /// Animation curve.
  final Curve curve;

  /// Whether to also fade in.
  final bool fadeIn;

  const SlideInOnMount({
    super.key,
    required this.child,
    this.direction = SlideDirection.fromBottom,
    this.distance = 32.0,
    this.duration = UmerDurations.medium2,
    this.curve = UmerCurves.emphasized,
    this.delay = Duration.zero,
    this.fadeIn = true,
  });

  @override
  State<SlideInOnMount> createState() => _SlideInOnMountState();
}

enum SlideDirection { fromTop, fromBottom, fromLeft, fromRight }

class _SlideInOnMountState extends State<SlideInOnMount>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<Offset> _offset;
  late final Animation<double> _opacity;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: widget.duration,
    );
    _offset = Tween<Offset>(
      begin: _beginOffset(),
      end: Offset.zero,
    ).animate(CurvedAnimation(parent: _controller, curve: widget.curve));
    _opacity = widget.fadeIn
        ? Tween<double>(begin: 0, end: 1).animate(
            CurvedAnimation(parent: _controller, curve: widget.curve),
          )
        : ConstantTween<double>(1).animate(_controller);
    Future.delayed(widget.delay, () {
      if (mounted) _controller.forward();
    });
  }

  Offset _beginOffset() {
    switch (widget.direction) {
      case SlideDirection.fromTop:
        return Offset(0, -widget.distance / 100);
      case SlideDirection.fromBottom:
        return Offset(0, widget.distance / 100);
      case SlideDirection.fromLeft:
        return Offset(-widget.distance / 100, 0);
      case SlideDirection.fromRight:
        return Offset(widget.distance / 100, 0);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return SlideTransition(
      position: _offset,
      child: widget.fadeIn
          ? FadeTransition(opacity: _opacity, child: widget.child)
          : widget.child,
    );
  }
}

/// Scales [child] in from [begin] to 1.0 with a spring curve, useful
/// for "pop in" effects (modal, dock item, success badge).
class ScaleInOnMount extends StatefulWidget {
  final Widget child;
  final double begin;
  final Duration duration;
  final Duration delay;
  final Curve curve;

  const ScaleInOnMount({
    super.key,
    required this.child,
    this.begin = 0.85,
    this.duration = UmerDurations.medium2,
    this.curve = UmerCurves.spring,
    this.delay = Duration.zero,
  });

  @override
  State<ScaleInOnMount> createState() => _ScaleInOnMountState();
}

class _ScaleInOnMountState extends State<ScaleInOnMount>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _scale;
  late final Animation<double> _opacity;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(vsync: this, duration: widget.duration);
    _scale = Tween<double>(begin: widget.begin, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: widget.curve),
    );
    _opacity = Tween<double>(begin: 0, end: 1).animate(
      CurvedAnimation(parent: _controller, curve: widget.curve),
    );
    Future.delayed(widget.delay, () {
      if (mounted) _controller.forward();
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return FadeTransition(
      opacity: _opacity,
      child: ScaleTransition(scale: _scale, child: widget.child),
    );
  }
}

/// Stagger-fade a list of children.  The first child appears at
/// [initialDelay], and each subsequent child is offset by [staggerDelay].
class StaggeredFadeIn extends StatelessWidget {
  /// Children to stagger.
  final List<Widget> children;

  /// Delay between each child's appearance.
  final Duration staggerDelay;

  /// Initial delay before the first child appears.
  final Duration initialDelay;

  /// Duration of each child's fade.
  final Duration duration;

  /// Curve of each child's fade.
  final Curve curve;

  /// Direction of slide.
  final SlideDirection slideDirection;

  /// Distance to slide.
  final double slideDistance;

  const StaggeredFadeIn({
    super.key,
    required this.children,
    this.staggerDelay = const Duration(milliseconds: 60),
    this.initialDelay = Duration.zero,
    this.duration = UmerDurations.medium2,
    this.curve = UmerCurves.decelerate,
    this.slideDirection = SlideDirection.fromBottom,
    this.slideDistance = 16.0,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (int i = 0; i < children.length; i++)
          SlideInOnMount(
            delay: initialDelay + (staggerDelay * i),
            direction: slideDirection,
            distance: slideDistance,
            duration: duration,
            curve: curve,
            child: children[i],
          ),
      ],
    );
  }
}

/// A simple ticker that re-runs an [animationBuilder] every
/// [interval] while [enabled] is true.  Useful for breathing /
/// pulsing effects.
class TickerBuilder extends StatefulWidget {
  final Widget Function(BuildContext context, double t) animationBuilder;
  final Duration interval;
  final bool enabled;
  final Curve curve;

  const TickerBuilder({
    super.key,
    required this.animationBuilder,
    this.interval = UmerDurations.long2,
    this.enabled = true,
    this.curve = UmerCurves.linear,
  });

  @override
  State<TickerBuilder> createState() => _TickerBuilderState();
}

class _TickerBuilderState extends State<TickerBuilder>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: widget.interval,
    );
    if (widget.enabled) {
      _controller.repeat();
    }
  }

  @override
  void didUpdateWidget(covariant TickerBuilder oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.enabled != oldWidget.enabled) {
      widget.enabled ? _controller.repeat() : _controller.stop();
    }
    if (widget.interval != oldWidget.interval) {
      _controller.duration = widget.interval;
      if (widget.enabled) _controller.repeat();
    }
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
        final t = widget.curve.transform(_controller.value);
        return widget.animationBuilder(context, t);
      },
    );
  }
}
