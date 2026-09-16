/// UmerOS — Glassmorphic Theme
/// ============================
/// Design tokens for the glassmorphism UI language used by the
/// context menu, taskbar, windows, and other chrome elements.
library;

import 'dart:ui';

import 'package:flutter/material.dart';

class GlassmorphicTheme {
  const GlassmorphicTheme._();

  // ── Blur ────────────────────────────────────────────────────

  /// Standard backdrop blur radius for panels.
  static const double blurRadius = 24.0;

  /// Smaller blur for nested elements (tooltips, sub-menus).
  static const double blurRadiusSmall = 12.0;

  // ── Opacity ─────────────────────────────────────────────────

  /// Background opacity for dark mode panels.
  static const double backgroundOpacityDark = 0.95;

  /// Background opacity for light mode panels.
  static const double backgroundOpacityLight = 0.90;

  /// Hover / pressed overlay opacity.
  static const double hoverOpacity = 0.15;

  /// Active (selected) item opacity.
  static const double activeOpacity = 0.22;

  // ── Border ──────────────────────────────────────────────────

  /// Visible border colour for dark mode.
  static const Color borderDark = Color(0x66FFFFFF);

  /// Visible border colour for light mode.
  static const Color borderLight = Color(0x88000000);

  static const double borderWidth = 1.0;

  static const double borderRadius = 12.0;

  static const double borderRadiusSmall = 8.0;

  // ── Shadow ──────────────────────────────────────────────────

  static const List<BoxShadow> shadow = [
    BoxShadow(
      color: Color(0x40000000),
      blurRadius: 32,
      offset: Offset(0, 8),
      spreadRadius: -4,
    ),
    BoxShadow(
      color: Color(0x1A000000),
      blurRadius: 8,
      offset: Offset(0, 2),
    ),
  ];

  // ── Item sizing ─────────────────────────────────────────────

  static const double itemHeight = 32.0;
  static const double itemPaddingH = 12.0;
  static const double itemPaddingV = 4.0;
  static const double iconSize = 16.0;
  static const double separatorHeight = 1.0;
  static const double submenuArrowSize = 14.0;

  // ── Typography ──────────────────────────────────────────────

  static const double fontSizeItem = 13.0;
  static const double fontSizeShortcut = 11.5;
  static const double fontSizeLabel = 10.5;
  static const double fontSizeSectionHeader = 11.0;

  // ── Animation ───────────────────────────────────────────────

  /// Total animation duration for the menu appearing / dismissing.
  static const Duration animDuration = Duration(milliseconds: 180);

  /// Duration for individual item hover transitions.
  static const Duration hoverDuration = Duration(milliseconds: 100);

  // ── Helpers ─────────────────────────────────────────────────

  /// Resolved background colour given the current brightness.
  static Color backgroundColor(BuildContext context) {
    final brightness = Theme.of(context).brightness;
    final opacity =
        brightness == Brightness.dark ? backgroundOpacityDark : backgroundOpacityLight;
    return brightness == Brightness.dark
        ? Colors.white.withAlpha((opacity * 255).round())
        : Colors.black.withAlpha((opacity * 255).round());
  }

  /// Resolved border colour given the current brightness.
  static Color borderColor(BuildContext context) {
    return Theme.of(context).brightness == Brightness.dark
        ? borderDark
        : borderLight;
  }

  /// High-contrast text colour — pure white on dark, near-black on light.
  static Color textColor(BuildContext context) {
    return Theme.of(context).brightness == Brightness.dark
        ? Colors.white
        : Colors.black87;
  }

  /// Subdued text for secondary labels (shortcuts, hints).
  static Color subtleTextColor(BuildContext context) {
    return Theme.of(context).brightness == Brightness.dark
        ? Colors.white70
        : Colors.black54;
  }

  /// Stronger shadow for menus floating over busy backgrounds.
  static List<BoxShadow> elevatedShadow(BuildContext context) {
    return [
      const BoxShadow(
        color: Color(0x55000000),
        blurRadius: 24,
        offset: Offset(0, 6),
        spreadRadius: -2,
      ),
      const BoxShadow(
        color: Color(0x22000000),
        blurRadius: 8,
        offset: Offset(0, 2),
      ),
    ];
  }

  /// Creates the frosted-glass backdrop filter widget.
  static Widget backdrop({required Widget child, double? blur}) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(borderRadius),
      child: BackdropFilter(
        filter: ImageFilter.blur(
          sigmaX: blur ?? blurRadius,
          sigmaY: blur ?? blurRadius,
        ),
        child: Container(
          decoration: BoxDecoration(
            color: Colors.transparent, // filled by caller
            borderRadius: BorderRadius.circular(borderRadius),
          ),
          child: child,
        ),
      ),
    );
  }
}
