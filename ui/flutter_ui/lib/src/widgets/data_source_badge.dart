/// UmerOS Flutter UI — Data-source badge
/// ======================================
/// Tiny chip that tells the user whether the numbers on screen are
/// coming from a live backend or from local simulation.
///
/// This is the visual enforcement of the project honesty rule
/// ("no impossible claims — always label simulations") inside the
/// frontend. Every app that renders service data should show this
/// badge in its header.
library;

import 'package:flutter/material.dart';

class DataSourceBadge extends StatelessWidget {
  /// True when the surrounding screen is showing simulated data.
  final bool simulated;

  const DataSourceBadge({super.key, required this.simulated});

  @override
  Widget build(BuildContext context) {
    final color = simulated ? Colors.amber.shade700 : Colors.green.shade600;
    final label = simulated ? 'Simulated' : 'Live';

    return Tooltip(
      message: simulated
          ? 'Backend unreachable — showing locally generated demo data.'
          : 'Connected to the UmerOS backend.',
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: color.withValues(alpha: 0.15),
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: color.withValues(alpha: 0.5)),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              simulated ? Icons.science_outlined : Icons.verified_outlined,
              size: 11,
              color: color,
            ),
            const SizedBox(width: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.bold,
                letterSpacing: 0.4,
                color: color,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
