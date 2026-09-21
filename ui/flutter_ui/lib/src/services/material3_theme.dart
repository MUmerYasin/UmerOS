/// UmerOS — Material Design 3 Theme Tokens
/// =========================================
/// Design tokens following the M3 specification for surface hierarchy,
/// color roles, shape scale, and elevation. Replaces the former
/// glassmorphism token set with a fully M3-compliant system.
///
/// Reference: https://m3.material.io/
library;

import 'package:flutter/material.dart';

/// M3 shape scale — corner radii matching the Material 3 spec.
class M3Shape {
  const M3Shape._();

  /// 4dp — chips, badges
  static const double extraSmall = 4.0;

  /// 8dp — buttons, small cards
  static const double small = 8.0;

  /// 12dp — menus, dialogs, text fields
  static const double medium = 12.0;

  /// 16dp — cards, sheets
  static const double large = 16.0;

  /// 28dp — extended FABs, large dialogs
  static const double extraLarge = 28.0;

  // ── BorderRadius shortcuts ──────────────────────────────────

  static const BorderRadius radiusExtraSmall =
      BorderRadius.all(Radius.circular(extraSmall));
  static const BorderRadius radiusSmall =
      BorderRadius.all(Radius.circular(small));
  static const BorderRadius radiusMedium =
      BorderRadius.all(Radius.circular(medium));
  static const BorderRadius radiusLarge =
      BorderRadius.all(Radius.circular(large));
  static const BorderRadius radiusExtraLarge =
      BorderRadius.all(Radius.circular(extraLarge));
}

/// M3 elevation levels — shadow tokens for surface hierarchy.
class M3Elevation {
  const M3Elevation._();

  /// Level 0 — flat surface, no shadow.
  static const List<BoxShadow> none = [];

  /// Level 1 — subtle lift (menus, cards at rest).
  static const List<BoxShadow> level1 = [
    BoxShadow(
      color: Color(0x1A000000),
      blurRadius: 3,
      offset: Offset(0, 1),
    ),
  ];

  /// Level 2 — slightly more prominent (hovered cards).
  static const List<BoxShadow> level2 = [
    BoxShadow(
      color: Color(0x1F000000),
      blurRadius: 6,
      offset: Offset(0, 1),
    ),
    BoxShadow(
      color: Color(0x0D000000),
      blurRadius: 2,
      offset: Offset(0, 1),
    ),
  ];

  /// Level 3 — menus, popovers, FABs.
  static const List<BoxShadow> level3 = [
    BoxShadow(
      color: Color(0x24000000),
      blurRadius: 8,
      offset: Offset(0, 3),
    ),
    BoxShadow(
      color: Color(0x0D000000),
      blurRadius: 4,
      offset: Offset(0, 1),
    ),
  ];

  /// Level 4 — navigation drawers, side sheets.
  static const List<BoxShadow> level4 = [
    BoxShadow(
      color: Color(0x29000000),
      blurRadius: 12,
      offset: Offset(0, 4),
    ),
    BoxShadow(
      color: Color(0x0D000000),
      blurRadius: 4,
      offset: Offset(0, 2),
    ),
  ];

  /// Level 5 — highest elevation (modals, snackbar).
  static const List<BoxShadow> level5 = [
    BoxShadow(
      color: Color(0x2E000000),
      blurRadius: 16,
      offset: Offset(0, 6),
    ),
    BoxShadow(
      color: Color(0x0D000000),
      blurRadius: 6,
      offset: Offset(0, 3),
    ),
  ];
}

/// UmerOS Material 3 Theme Tokens
///
/// Provides static helpers that resolve M3 color roles from the current
/// [BuildContext]'s [Theme]. All helpers pull directly from
/// [ColorScheme] — no glassmorphism, no opacity hacks.
///
/// ### Migration from GlassmorphicTheme
///
/// | Old (Glassmorphic)              | New (M3)                                         |
/// |---------------------------------|--------------------------------------------------|
/// | `GlassmorphicTheme.blurRadius`  | *(removed — M3 uses surface tint, not blur)*     |
/// | `GlassmorphicTheme.backgroundColor` | `M3Theme.surfaceContainer(context)`          |
/// | `GlassmorphicTheme.borderColor`     | `M3Theme.outlineVariant(context)`             |
/// | `GlassmorphicTheme.textColor`       | `M3Theme.onSurface(context)`                  |
/// | `GlassmorphicTheme.subtleTextColor` | `M3Theme.onSurfaceVariant(context)`           |
/// | `GlassmorphicTheme.shadow`          | `M3Elevation.level3`                          |
/// | `GlassmorphicTheme.borderRadius`    | `M3Shape.medium` (12dp)                       |
/// | `GlassmorphicTheme.backdrop()`      | *(removed — use M3 surface containers)*       |
class M3Theme {
  const M3Theme._();

  // ── Shape (backward-compat aliases) ────────────────────────

  /// Alias — use [M3Shape.medium] instead.
  static const double borderRadius = M3Shape.medium;

  /// Alias — use [M3Shape.small] instead.
  static const double borderRadiusSmall = M3Shape.small;

  /// Border width for M3 outlined surfaces.
  static const double borderWidth = 1.0;

  /// Elevation shadow for M3 surfaces (level 3).
  static const List<BoxShadow> shadow = M3Elevation.level3;

  /// Opacity for hover overlays on interactive surfaces.
  static const double hoverOpacity = 0.15;

  // ── Animation (kept from old theme, still lightweight) ─────

  /// Total animation duration for menu appearing / dismissing.
  static const Duration animDuration = Duration(milliseconds: 180);

  /// Duration for individual item hover transitions.
  static const Duration hoverDuration = Duration(milliseconds: 100);

  // ── Layout (kept from old theme) ───────────────────────────

  static const double itemHeight = 32.0;
  static const double itemPaddingH = 12.0;
  static const double itemPaddingV = 4.0;
  static const double iconSize = 16.0;
  static const double separatorHeight = 1.0;
  static const double submenuArrowSize = 14.0;

  // ── Typography (kept from old theme) ───────────────────────

  static const double fontSizeItem = 13.0;
  static const double fontSizeShortcut = 11.5;
  static const double fontSizeLabel = 10.5;
  static const double fontSizeSectionHeader = 11.0;

  // ── M3 Surface Roles ───────────────────────────────────────

  /// Primary surface — the base background.
  static Color surface(BuildContext context) =>
      Theme.of(context).colorScheme.surface;

  /// Dimmed surface (M3: `surfaceDim`).
  static Color surfaceDim(BuildContext context) =>
      Theme.of(context).colorScheme.surfaceDim;

  /// Bright surface (M3: `surfaceBright`).
  static Color surfaceBright(BuildContext context) =>
      Theme.of(context).colorScheme.surfaceBright;

  /// Lowest container level.
  static Color surfaceContainerLowest(BuildContext context) =>
      Theme.of(context).colorScheme.surfaceContainerLowest;

  /// Low container level.
  static Color surfaceContainerLow(BuildContext context) =>
      Theme.of(context).colorScheme.surfaceContainerLow;

  /// Default container level — used for menus, cards.
  static Color surfaceContainer(BuildContext context) =>
      Theme.of(context).colorScheme.surfaceContainer;

  /// High container level — popovers, elevated cards.
  static Color surfaceContainerHigh(BuildContext context) =>
      Theme.of(context).colorScheme.surfaceContainerHigh;

  /// Highest container level — side sheets, nav rails.
  static Color surfaceContainerHighest(BuildContext context) =>
      Theme.of(context).colorScheme.surfaceContainerHighest;

  // ── M3 Color Roles ─────────────────────────────────────────

  static Color primary(BuildContext context) =>
      Theme.of(context).colorScheme.primary;

  static Color onPrimary(BuildContext context) =>
      Theme.of(context).colorScheme.onPrimary;

  static Color primaryContainer(BuildContext context) =>
      Theme.of(context).colorScheme.primaryContainer;

  static Color onPrimaryContainer(BuildContext context) =>
      Theme.of(context).colorScheme.onPrimaryContainer;

  static Color secondary(BuildContext context) =>
      Theme.of(context).colorScheme.secondary;

  static Color onSecondary(BuildContext context) =>
      Theme.of(context).colorScheme.onSecondary;

  static Color secondaryContainer(BuildContext context) =>
      Theme.of(context).colorScheme.secondaryContainer;

  static Color onSecondaryContainer(BuildContext context) =>
      Theme.of(context).colorScheme.onSecondaryContainer;

  static Color tertiary(BuildContext context) =>
      Theme.of(context).colorScheme.tertiary;

  static Color onTertiary(BuildContext context) =>
      Theme.of(context).colorScheme.onTertiary;

  static Color tertiaryContainer(BuildContext context) =>
      Theme.of(context).colorScheme.tertiaryContainer;

  static Color onTertiaryContainer(BuildContext context) =>
      Theme.of(context).colorScheme.onTertiaryContainer;

  static Color error(BuildContext context) =>
      Theme.of(context).colorScheme.error;

  static Color onError(BuildContext context) =>
      Theme.of(context).colorScheme.onError;

  static Color errorContainer(BuildContext context) =>
      Theme.of(context).colorScheme.errorContainer;

  static Color onErrorContainer(BuildContext context) =>
      Theme.of(context).colorScheme.onErrorContainer;

  // ── M3 Text / Icon Roles ───────────────────────────────────

  /// High-emphasis text on surfaces — replaces old `textColor`.
  static Color onSurface(BuildContext context) =>
      Theme.of(context).colorScheme.onSurface;

  /// Medium-emphasis text — replaces old `subtleTextColor`.
  static Color onSurfaceVariant(BuildContext context) =>
      Theme.of(context).colorScheme.onSurfaceVariant;

  /// Outline color — borders, dividers.
  static Color outline(BuildContext context) =>
      Theme.of(context).colorScheme.outline;

  /// Subtle outline — container borders, separator lines.
  static Color outlineVariant(BuildContext context) =>
      Theme.of(context).colorScheme.outlineVariant;

  // ── Composite Helpers ──────────────────────────────────────

  /// Menu / panel background — M3 surfaceContainer is the correct
  /// role for menus and popovers.
  static Color backgroundColor(BuildContext context) =>
      surfaceContainer(context);

  /// Container border — uses outlineVariant for subtle separation.
  static Color borderColor(BuildContext context) =>
      outlineVariant(context);

  /// Primary text on menu items.
  static Color textColor(BuildContext context) =>
      onSurface(context);

  /// Secondary text for shortcuts, hints, labels.
  static Color subtleTextColor(BuildContext context) =>
      onSurfaceVariant(context);

  /// Hover overlay color — 15% of primary, applied on hover.
  static Color hoverOverlay(BuildContext context) =>
      primary(context).withValues(alpha: 0.15);

  /// Active / selected overlay — 22% of primary.
  static Color activeOverlay(BuildContext context) =>
      primary(context).withValues(alpha: 0.22);

  /// Separator color — very subtle line.
  static Color separatorColor(BuildContext context) =>
      outlineVariant(context).withValues(alpha: 0.3);
}
