/// Accessible Widget Wrappers
///
/// HCI-aligned widget wrappers that add Semantics labels,
/// tooltips, and keyboard navigation support.
/// Based on Nielsen's 10 Heuristics and WCAG 2.2 guidelines.
library;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// An accessible card with Semantics label for screen readers.
class AccessibleCard extends StatelessWidget {
  final String label;
  final Widget child;
  final VoidCallback? onTap;
  final String? tooltip;

  const AccessibleCard({
    super.key,
    required this.label,
    required this.child,
    this.onTap,
    this.tooltip,
  });

  @override
  Widget build(BuildContext context) {
    Widget result = Semantics(
      label: label,
      button: onTap != null,
      child: child,
    );
    if (tooltip != null) {
      result = Tooltip(message: tooltip!, child: result);
    }
    if (onTap != null) {
      result = InkWell(onTap: onTap, child: result);
    }
    return result;
  }
}

/// An accessible tab button with Semantics and tooltip.
class AccessibleTabButton extends StatelessWidget {
  final String label;
  final IconData icon;
  final bool isSelected;
  final VoidCallback onTap;
  final String? tooltip;

  const AccessibleTabButton({
    super.key,
    required this.label,
    required this.icon,
    required this.isSelected,
    required this.onTap,
    this.tooltip,
  });

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Semantics(
      label: '$label tab${isSelected ? ", selected" : ""}',
      button: true,
      selected: isSelected,
      child: Tooltip(
        message: tooltip ?? label,
        child: InkWell(
          onTap: onTap,
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              border: Border(
                bottom: BorderSide(
                  width: 2,
                  color: isSelected ? scheme.primary : Colors.transparent,
                ),
              ),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(icon, size: 16, color: isSelected ? scheme.primary : scheme.onSurfaceVariant),
                const SizedBox(width: 6),
                Text(
                  label,
                  style: GoogleFonts.inter(
                    fontSize: 12,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                    color: isSelected ? scheme.primary : scheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// An accessible info card with Semantics.
class AccessibleInfoCard extends StatelessWidget {
  final String title;
  final String body;

  const AccessibleInfoCard({
    super.key,
    required this.title,
    required this.body,
  });

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: '$title: $body',
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Colors.blue.shade50,
          borderRadius: BorderRadius.circular(10),
          border: Border.all(color: Colors.blue.shade100),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: GoogleFonts.inter(fontSize: 13, fontWeight: FontWeight.w600, color: Colors.blue.shade900)),
            const SizedBox(height: 4),
            Text(body, style: GoogleFonts.inter(fontSize: 12, color: Colors.blue.shade800, height: 1.4)),
          ],
        ),
      ),
    );
  }
}

/// An empty state widget for better UX (Nielsen #1 visibility).
class EmptyState extends StatelessWidget {
  final String title;
  final String message;
  final IconData icon;
  final VoidCallback? onAction;
  final String? actionLabel;

  const EmptyState({
    super.key,
    required this.title,
    required this.message,
    this.icon = Icons.inbox,
    this.onAction,
    this.actionLabel,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48, color: Colors.grey.shade400),
            const SizedBox(height: 16),
            Text(
              title,
              style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.grey.shade700),
            ),
            const SizedBox(height: 8),
            Text(
              message,
              style: GoogleFonts.inter(fontSize: 13, color: Colors.grey.shade500),
              textAlign: TextAlign.center,
            ),
            if (onAction != null && actionLabel != null) ...[
              const SizedBox(height: 16),
              FilledButton(onPressed: onAction, child: Text(actionLabel!)),
            ],
          ],
        ),
      ),
    );
  }
}

/// A loading state widget for better UX (Nielsen #1 visibility).
class LoadingState extends StatelessWidget {
  final String message;

  const LoadingState({super.key, this.message = 'Loading...'});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const CircularProgressIndicator(),
          const SizedBox(height: 16),
          Text(message, style: GoogleFonts.inter(fontSize: 13, color: Colors.grey.shade600)),
        ],
      ),
    );
  }
}

/// An error state widget for better UX (Nielsen #9 error recovery).
class ErrorState extends StatelessWidget {
  final String title;
  final String message;
  final VoidCallback? onRetry;

  const ErrorState({
    super.key,
    this.title = 'Something went wrong',
    required this.message,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.error_outline, size: 48, color: Colors.red.shade400),
            const SizedBox(height: 16),
            Text(
              title,
              style: GoogleFonts.inter(fontSize: 16, fontWeight: FontWeight.w600, color: Colors.red.shade700),
            ),
            const SizedBox(height: 8),
            Text(
              message,
              style: GoogleFonts.inter(fontSize: 13, color: Colors.grey.shade600),
              textAlign: TextAlign.center,
            ),
            if (onRetry != null) ...[
              const SizedBox(height: 16),
              FilledButton.tonal(onPressed: onRetry, child: const Text('Retry')),
            ],
          ],
        ),
      ),
    );
  }
}