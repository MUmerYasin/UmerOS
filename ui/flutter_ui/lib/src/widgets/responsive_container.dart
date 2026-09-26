import 'package:flutter/material.dart';

enum ResponsiveZone {
  topLeft,
  left,
  right,
  center,
}

class ResponsiveContainer extends StatelessWidget {
  final ResponsiveZone zone;
  final Widget child;

  const ResponsiveContainer({super.key, required this.zone, required this.child});

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    final double width = size.width;
    final double height = size.height;
    Rect rect;
    switch (zone) {
      case ResponsiveZone.topLeft:
        rect = Rect.fromLTWH(0, 0, width * 0.25, height * 0.25);
        break;
      case ResponsiveZone.left:
        rect = Rect.fromLTWH(0, 0, width * 0.5, height);
        break;
      case ResponsiveZone.right:
        rect = Rect.fromLTWH(width * 0.5, 0, width * 0.5, height);
        break;
      case ResponsiveZone.center:
        rect = Rect.fromLTWH(width * 0.1, height * 0.1, width * 0.8, height * 0.8);
        break;
    }
    return Positioned.fromRect(
      rect: rect,
      child: child,
    );
  }
}
