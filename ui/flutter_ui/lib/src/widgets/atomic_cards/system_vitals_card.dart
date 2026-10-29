/// System Vitals Atomic Card — Live mini-charts of CPU%, RAM%, temperature.
library;

import 'package:flutter/material.dart';

import 'atomic_card_base.dart';

class SystemVitalsCard extends StatelessWidget {
  const SystemVitalsCard({super.key, this.onExpand});

  final VoidCallback? onExpand;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return AtomicCardBase(
      title: 'System Vitals',
      icon: Icons.monitor_heart,
      size: CardSize.medium,
      onExpand: onExpand,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _VitalRow(
            label: 'CPU',
            value: 0.42,
            color: colorScheme.primary,
          ),
          const SizedBox(height: 8),
          _VitalRow(
            label: 'RAM',
            value: 0.67,
            color: colorScheme.secondary,
          ),
          const SizedBox(height: 8),
          _VitalRow(
            label: 'Temp',
            value: 0.55,
            color: colorScheme.tertiary,
          ),
          const SizedBox(height: 8),
          Text(
            '3 active kernel tasks',
            style: TextStyle(
              fontSize: 11,
              color: colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}

class _VitalRow extends StatelessWidget {
  const _VitalRow({
    required this.label,
    required this.value,
    required this.color,
  });

  final String label;
  final double value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        SizedBox(
          width: 40,
          child: Text(
            label,
            style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w500),
          ),
        ),
        Expanded(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: value,
              backgroundColor: color.withValues(alpha: 0.15),
              valueColor: AlwaysStoppedAnimation<Color>(color),
              minHeight: 6,
            ),
          ),
        ),
        const SizedBox(width: 8),
        Text(
          '${(value * 100).toInt()}%',
          style: TextStyle(fontSize: 11, color: color),
        ),
      ],
    );
  }
}