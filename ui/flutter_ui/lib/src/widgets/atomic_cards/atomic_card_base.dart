/// Atomic Service Card — style desktop widget base.
///
/// Supports sizes: Small (160x160), Medium (340x160), Large (340x340).
/// Glassmorphism design with frosted blur, subtle border, and
/// "Expand to App" / settings flip-card actions.
library;

import 'dart:ui';

import 'package:flutter/material.dart';

enum CardSize { small, medium, large, wide }

extension CardSizeExt on CardSize {
  Size get dimensions {
    switch (this) {
      case CardSize.small:
        return const Size(160, 160);
      case CardSize.medium:
        return const Size(340, 160);
      case CardSize.large:
        return const Size(340, 340);
      case CardSize.wide:
        return const Size(520, 160);
    }
  }
}

class AtomicCardBase extends StatefulWidget {
  const AtomicCardBase({
    super.key,
    required this.child,
    this.size = CardSize.medium,
    this.title = '',
    this.icon,
    this.onExpand,
    this.onSettings,
    this.onRefresh,
  });

  final Widget child;
  final CardSize size;
  final String title;
  final IconData? icon;
  final VoidCallback? onExpand;
  final VoidCallback? onSettings;
  final VoidCallback? onRefresh;

  @override
  State<AtomicCardBase> createState() => _AtomicCardBaseState();
}

class _AtomicCardBaseState extends State<AtomicCardBase> {
  bool _isFlipped = false;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final dims = widget.size.dimensions;

    return SizedBox(
      width: dims.width,
      height: dims.height,
      child: AnimatedSwitcher(
        duration: const Duration(milliseconds: 300),
        transitionBuilder: (child, anim) => RotationYTransition(
          turns: anim,
          child: child,
        ),
        child: _isFlipped
            ? _buildBack(context, colorScheme, dims)
            : _buildFront(context, colorScheme, dims),
      ),
    );
  }

  Widget _buildFront(BuildContext context, ColorScheme colorScheme, Size dims) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerHigh.withValues(alpha: 0.6),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: colorScheme.outlineVariant.withValues(alpha: 0.3),
              width: 1,
            ),
            boxShadow: [
              BoxShadow(
                color: Colors.black.withValues(alpha: 0.2),
                blurRadius: 16,
                spreadRadius: 1,
              ),
            ],
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Header
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                child: Row(
                  children: [
                    if (widget.icon != null)
                      Icon(widget.icon, size: 16, color: colorScheme.primary),
                    if (widget.icon != null) const SizedBox(width: 6),
                    Expanded(
                      child: Text(
                        widget.title,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.bold,
                          color: colorScheme.onSurface,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (widget.onRefresh != null)
                      IconButton(
                        icon: const Icon(Icons.refresh, size: 16),
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(minWidth: 24, minHeight: 24),
                        onPressed: widget.onRefresh,
                      ),
                    IconButton(
                      icon: const Icon(Icons.open_in_full, size: 16),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(minWidth: 24, minHeight: 24),
                      onPressed: widget.onExpand,
                      tooltip: 'Expand to App',
                    ),
                    IconButton(
                      icon: const Icon(Icons.settings, size: 16),
                      padding: EdgeInsets.zero,
                      constraints: const BoxConstraints(minWidth: 24, minHeight: 24),
                      onPressed: () => setState(() => _isFlipped = true),
                      tooltip: 'Settings',
                    ),
                  ],
                ),
              ),
              const Divider(height: 1, thickness: 0.5),
              // Content
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: widget.child,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBack(BuildContext context, ColorScheme colorScheme, Size dims) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: BackdropFilter(
        filter: ImageFilter.blur(sigmaX: 12, sigmaY: 12),
        child: Container(
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerHigh.withValues(alpha: 0.8),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(
              color: colorScheme.outlineVariant.withValues(alpha: 0.3),
              width: 1,
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.settings, size: 32, color: colorScheme.primary),
              const SizedBox(height: 8),
              Text(
                'Card Settings',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: colorScheme.onSurface,
                ),
              ),
              const SizedBox(height: 16),
              ElevatedButton.icon(
                onPressed: () => setState(() => _isFlipped = false),
                icon: const Icon(Icons.arrow_back, size: 16),
                label: const Text('Back'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Rotation transition for card flip effect.
class RotationYTransition extends AnimatedWidget {
  const RotationYTransition({
    super.key,
    required this.turns,
    required this.child,
  }) : super(listenable: turns);

  final Animation<double> turns;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final angle = turns.value * 3.141592653589793;
    return Transform(
      transform: Matrix4.identity()
        ..setEntry(3, 2, 0.001)
        ..rotateY(angle),
      alignment: Alignment.center,
      child: child,
    );
  }
}