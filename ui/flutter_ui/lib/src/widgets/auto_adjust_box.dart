import 'package:flutter/material.dart';

/// Reusable overflow guards for UmerOS windows.
///
/// Every app window can be resized to arbitrary sizes; these widgets make
/// layouts degrade gracefully instead of painting striped
/// "RenderFlex overflow" errors on any side (top/bottom/left/right).

/// Scales its [child] down proportionally when the available space is
/// smaller than the child's natural size, so fixed tiles (icon + label,
/// stat cards, badges) can never clip on any edge.
///
/// Only use with content that has a finite intrinsic size. Never place
/// scrollables (ListView, GridView, SingleChildScrollView) or
/// Expanded/Flexible children inside.
class AutoAdjustBox extends StatelessWidget {
  const AutoAdjustBox({
    super.key,
    required this.child,
    this.maxWidth,
    this.maxHeight,
    this.alignment = Alignment.center,
  });

  final Widget child;
  final double? maxWidth;
  final double? maxHeight;
  final Alignment alignment;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: FittedBox(
        fit: BoxFit.scaleDown,
        alignment: alignment,
        child: ConstrainedBox(
          constraints: BoxConstraints(
            maxWidth: maxWidth ?? double.infinity,
            maxHeight: maxHeight ?? double.infinity,
          ),
          child: child,
        ),
      ),
    );
  }
}

/// Drop-in replacement for [Row] whose children are all fixed-size:
/// overflowing children flow onto a second line instead of painting past
/// the right edge.
///
/// Never place Expanded, Flexible or Spacer children inside — use a plain
/// Row when flexible children are required.
class AutoAdjustRow extends StatelessWidget {
  const AutoAdjustRow({
    super.key,
    required this.children,
    this.spacing = 8,
    this.runSpacing = 8,
    this.crossAxisAlignment = WrapCrossAlignment.center,
    this.alignment = WrapAlignment.start,
  });

  final List<Widget> children;
  final double spacing;
  final double runSpacing;
  final WrapCrossAlignment crossAxisAlignment;
  final WrapAlignment alignment;

  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: spacing,
      runSpacing: runSpacing,
      crossAxisAlignment: crossAxisAlignment,
      alignment: alignment,
      children: children,
    );
  }
}

/// Column that becomes vertically scrollable when its [children] exceed
/// the available height, instead of overflowing the bottom edge.
///
/// Use for panels built from stacked sections that have no scroll view of
/// their own. Do not wrap columns that already live inside a scrollable.
class AutoAdjustColumn extends StatelessWidget {
  const AutoAdjustColumn({
    super.key,
    required this.children,
    this.padding = EdgeInsets.zero,
    this.crossAxisAlignment = CrossAxisAlignment.start,
  });

  final List<Widget> children;
  final EdgeInsetsGeometry padding;
  final CrossAxisAlignment crossAxisAlignment;

  @override
  Widget build(BuildContext context) {
    final column = Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: crossAxisAlignment,
      children: children,
    );
    return LayoutBuilder(
      builder: (context, constraints) {
        if (!constraints.maxHeight.isFinite) return column;
        return SingleChildScrollView(
          padding: padding,
          child: column,
        );
      },
    );
  }
}
