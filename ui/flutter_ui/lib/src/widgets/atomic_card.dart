// UmerOS Atomic Service Card Widget
// NEXT Atomic Services (Meta-Services).
// Provides lightweight, interactive, glassmorphic cards for the desktop canvas.

import 'package:flutter/material.dart';

enum AtomicCardSize {
  small, // 160x160 (1x1)
  medium, // 340x160 (2x1)
  large, // 340x340 (2x2)
}

class AtomicCard extends StatelessWidget {
  final String title;
  final String? subtitle;
  final IconData icon;
  final Color accentColor;
  final AtomicCardSize size;
  final Widget? content;
  final List<Widget>? actions;
  final VoidCallback? onExpand;
  final VoidCallback? onTap;

  const AtomicCard({
    super.key,
    required this.title,
    this.subtitle,
    required this.icon,
    this.accentColor = Colors.cyanAccent,
    this.size = AtomicCardSize.medium,
    this.content,
    this.actions,
    this.onExpand,
    this.onTap,
  });

  double get width {
    switch (size) {
      case AtomicCardSize.small:
        return 160.0;
      case AtomicCardSize.medium:
        return 340.0;
      case AtomicCardSize.large:
        return 340.0;
    }
  }

  double get height {
    switch (size) {
      case AtomicCardSize.small:
        return 160.0;
      case AtomicCardSize.medium:
        return 160.0;
      case AtomicCardSize.large:
        return 340.0;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      width: width,
      height: height,
      margin: const EdgeInsets.all(8.0),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.65),
        borderRadius: BorderRadius.circular(20.0),
        border: Border.all(
          color: accentColor.withValues(alpha: 0.35),
          width: 1.2,
        ),
        boxShadow: [
          BoxShadow(
            color: accentColor.withValues(alpha: 0.15),
            blurRadius: 12.0,
            spreadRadius: 1.0,
          )
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: BorderRadius.circular(20.0),
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(14.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Header: Icon + Title + Expand Button
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.all(6.0),
                      decoration: BoxDecoration(
                        color: accentColor.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(10.0),
                      ),
                      child: Icon(icon, size: 16.0, color: accentColor),
                    ),
                    const SizedBox(width: 8.0),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            title,
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 13.0,
                              fontWeight: FontWeight.bold,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          if (subtitle != null)
                            Text(
                              subtitle!,
                              style: TextStyle(
                                color: Colors.white.withValues(alpha: 0.6),
                                fontSize: 10.0,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                        ],
                      ),
                    ),
                    if (onExpand != null)
                      IconButton(
                        icon: const Icon(Icons.open_in_new, size: 14.0),
                        color: Colors.white70,
                        padding: EdgeInsets.zero,
                        constraints: const BoxConstraints(),
                        tooltip: 'Open full app',
                        onPressed: onExpand,
                      ),
                  ],
                ),
                const SizedBox(height: 10.0),

                // Main Card Content Area
                Expanded(
                  child: content ?? const SizedBox.shrink(),
                ),

                // Footer Quick Actions
                if (actions != null && actions!.isNotEmpty) ...[
                  const SizedBox(height: 8.0),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: actions!,
                  ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
