// UmerOS Live Window / Live View Status Capsule
// HarmonyOS NEXT Live Window.
// Provides a real-time, interactive glanceable status capsule in the top bar.

import 'package:flutter/material.dart';

class LiveTaskInfo {
  final String taskId;
  final String title;
  final IconData icon;
  final double progress; // 0.0 to 1.0
  final String statusText;
  final bool isCompleted;

  LiveTaskInfo({
    required this.taskId,
    required this.title,
    this.icon = Icons.hourglass_empty,
    this.progress = 0.0,
    this.statusText = 'In progress...',
    this.isCompleted = false,
  });

  factory LiveTaskInfo.fromJson(Map<String, dynamic> json) {
    return LiveTaskInfo(
      taskId: json['task_id'] as String? ?? 'task',
      title: json['title'] as String? ?? 'Background Task',
      progress: (json['progress'] as num?)?.toDouble() ?? 0.0,
      statusText: json['status_text'] as String? ?? '',
      isCompleted: json['is_completed'] as bool? ?? false,
    );
  }
}

class LiveViewCapsule extends StatefulWidget {
  final List<LiveTaskInfo> activeTasks;
  final void Function(String taskId)? onCancelTask;
  final void Function(String taskId)? onTapTask;

  const LiveViewCapsule({
    super.key,
    required this.activeTasks,
    this.onCancelTask,
    this.onTapTask,
  });

  @override
  State<LiveViewCapsule> createState() => _LiveViewCapsuleState();
}

class _LiveViewCapsuleState extends State<LiveViewCapsule>
    with SingleTickerProviderStateMixin {
  bool _isExpanded = false;
  late AnimationController _pulseController;

  @override
  void initState() {
    super.initState();
    _pulseController = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    );
    if (widget.activeTasks.isNotEmpty && widget.activeTasks.any((t) => !t.isCompleted)) {
      _pulseController.repeat(reverse: true);
    }
  }

  @override
  void didUpdateWidget(LiveViewCapsule oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.activeTasks.isNotEmpty && widget.activeTasks.any((t) => !t.isCompleted)) {
      if (!_pulseController.isAnimating) {
        _pulseController.repeat(reverse: true);
      }
    } else {
      if (_pulseController.isAnimating) {
        _pulseController.stop();
      }
    }
  }

  @override
  void dispose() {
    _pulseController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (widget.activeTasks.isEmpty) {
      return const SizedBox.shrink();
    }

    final primaryTask = widget.activeTasks.first;
    final accentColor = primaryTask.isCompleted ? Colors.greenAccent : Colors.cyanAccent;

    return AnimatedContainer(
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeOutCubic,
      margin: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.75),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(
          color: accentColor.withValues(alpha: 0.5),
          width: 1.2,
        ),
        boxShadow: [
          BoxShadow(
            color: accentColor.withValues(alpha: 0.25),
            blurRadius: 8,
            spreadRadius: 1,
          )
        ],
      ),
      child: InkWell(
        onTap: () {
          setState(() {
            _isExpanded = !_isExpanded;
          });
          if (widget.onTapTask != null) {
            widget.onTapTask!(primaryTask.taskId);
          }
        },
        borderRadius: BorderRadius.circular(20),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            FadeTransition(
              opacity: Tween<double>(begin: 0.6, end: 1.0).animate(_pulseController),
              child: Icon(primaryTask.icon, size: 14, color: accentColor),
            ),
            const SizedBox(width: 6),
            Text(
              primaryTask.title,
              style: const TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            const SizedBox(width: 6),
            if (!primaryTask.isCompleted) ...[
              SizedBox(
                width: 36,
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(2),
                  child: LinearProgressIndicator(
                    value: primaryTask.progress,
                    backgroundColor: Colors.white24,
                    color: accentColor,
                    minHeight: 3,
                  ),
                ),
              ),
              const SizedBox(width: 4),
              Text(
                '${(primaryTask.progress * 100).toInt()}%',
                style: TextStyle(
                  fontSize: 10,
                  color: accentColor,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ] else ...[
              const Icon(Icons.check_circle, size: 12, color: Colors.greenAccent),
            ],
            if (_isExpanded && widget.onCancelTask != null && !primaryTask.isCompleted) ...[
              const SizedBox(width: 6),
              InkWell(
                onTap: () => widget.onCancelTask!(primaryTask.taskId),
                child: const Icon(Icons.close, size: 12, color: Colors.white70),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
