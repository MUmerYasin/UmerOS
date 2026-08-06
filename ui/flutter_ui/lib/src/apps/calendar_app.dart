import 'package:flutter/material.dart';

class CalendarApp extends StatefulWidget {
  const CalendarApp({super.key});

  @override
  State<CalendarApp> createState() => _CalendarAppState();
}

class _CalendarAppState extends State<CalendarApp> {
  late DateTime _currentDate;
  late DateTime _selectedDate;
  final Map<int, List<Map<String, dynamic>>> _events = {};
  final TextEditingController _eventController = TextEditingController();
  TimeOfDay _selectedTime = TimeOfDay.now();
  Color _selectedEventColor = Colors.blue;

  final List<Color> _eventColors = [
    Colors.blue,
    Colors.green,
    Colors.orange,
    Colors.purple,
    Colors.red,
    Colors.teal,
    Colors.pink,
    Colors.amber,
  ];

  @override
  void initState() {
    super.initState();
    _currentDate = DateTime.now();
    _selectedDate = DateTime.now();
    _initEvents();
  }

  void _initEvents() {
    final now = DateTime.now();
    _events[15] = [{'title': 'Team Meeting', 'time': '10:00 AM', 'color': Colors.blue}];
    _events[20] = [{'title': 'Project Review', 'time': '2:00 PM', 'color': Colors.orange}];
    _events[25] = [{'title': 'Release v1.0', 'time': '9:00 AM', 'color': Colors.green}];
    if (_events[now.day] == null) {
      _events[now.day] = [];
    }
  }

  @override
  void dispose() {
    _eventController.dispose();
    super.dispose();
  }

  int get _daysInMonth => DateTime(_currentDate.year, _currentDate.month + 1, 0).day;
  int get _firstDayOfWeek => DateTime(_currentDate.year, _currentDate.month, 1).weekday % 7;
  int get _totalCells => ((_firstDayOfWeek + _daysInMonth + 6) ~/ 7) * 7;

  void _previousMonth() {
    setState(() {
      _currentDate = DateTime(_currentDate.year, _currentDate.month - 1);
    });
  }

  void _nextMonth() {
    setState(() {
      _currentDate = DateTime(_currentDate.year, _currentDate.month + 1);
    });
  }

  void _selectDay(int day) {
    if (day < 1 || day > _daysInMonth) return;
    setState(() {
      _selectedDate = DateTime(_currentDate.year, _currentDate.month, day);
    });
  }

  void _addEvent() {
    if (_eventController.text.trim().isEmpty) return;
    final day = _selectedDate.day;
    setState(() {
      if (_events[day] == null) _events[day] = [];
      _events[day]!.add({
        'title': _eventController.text.trim(),
        'time': _selectedTime.format(context),
        'color': _selectedEventColor,
      });
    });
    _eventController.clear();
  }

  void _removeEvent(int day, int index) {
    setState(() {
      _events[day]?.removeAt(index);
    });
  }

  String _getMonthName(int month) {
    const months = [
      'January', 'February', 'March', 'April', 'May', 'June',
      'July', 'August', 'September', 'October', 'November', 'December',
    ];
    return months[month - 1];
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final selectedDayEvents = _events[_selectedDate.day] ?? [];

    return Row(
      children: [
        // Calendar
        Expanded(
          flex: 3,
          child: Column(
            children: [
              // Header
              Padding(
                padding: const EdgeInsets.all(16),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    IconButton(
                      onPressed: _previousMonth,
                      icon: const Icon(Icons.chevron_left),
                    ),
                    Text(
                      '${_getMonthName(_currentDate.month)} ${_currentDate.year}',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.bold,
                        color: colorScheme.onSurface,
                      ),
                    ),
                    IconButton(
                      onPressed: _nextMonth,
                      icon: const Icon(Icons.chevron_right),
                    ),
                  ],
                ),
              ),
              // Day headers
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                child: Row(
                  children: ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((day) {
                    return Expanded(
                      child: Center(
                        child: Text(
                          day,
                          style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: colorScheme.onSurface.withValues(alpha: 0.6),
                          ),
                        ),
                      ),
                    );
                  }).toList(),
                ),
              ),
              const SizedBox(height: 8),
              // Calendar grid
              Expanded(
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: GridView.builder(
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: 7,
                      childAspectRatio: 1.0,
                    ),
                    itemCount: _totalCells,
                    itemBuilder: (context, index) {
                      final day = index - _firstDayOfWeek + 1;
                      final isValidDay = day >= 1 && day <= _daysInMonth;
                      final isToday = isValidDay &&
                          day == DateTime.now().day &&
                          _currentDate.month == DateTime.now().month &&
                          _currentDate.year == DateTime.now().year;
                      final isSelected = isValidDay &&
                          day == _selectedDate.day &&
                          _currentDate.month == _selectedDate.month;
                      final hasEvents = isValidDay && _events[day] != null && _events[day]!.isNotEmpty;

                      return GestureDetector(
                        onTap: isValidDay ? () => _selectDay(day) : null,
                        child: Container(
                          margin: const EdgeInsets.all(2),
                          decoration: BoxDecoration(
                            color: isSelected
                                ? colorScheme.primary
                                : isToday
                                    ? colorScheme.primaryContainer
                                    : null,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Text(
                                isValidDay ? '$day' : '',
                                style: TextStyle(
                                  fontWeight: isToday || isSelected ? FontWeight.bold : FontWeight.normal,
                                  color: isSelected
                                      ? colorScheme.onPrimary
                                      : isToday
                                          ? colorScheme.onPrimaryContainer
                                          : colorScheme.onSurface,
                                ),
                              ),
                              if (hasEvents)
                                Container(
                                  width: 6,
                                  height: 6,
                                  margin: const EdgeInsets.only(top: 2),
                                  decoration: BoxDecoration(
                                    color: _events[day]![0]['color'] as Color,
                                    shape: BoxShape.circle,
                                  ),
                                ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ),
            ],
          ),
        ),
        // Events panel
        Expanded(
          flex: 2,
          child: Container(
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
              border: Border(
                left: BorderSide(
                  color: colorScheme.outline.withValues(alpha: 0.2),
                ),
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Text(
                    '${_selectedDate.day} ${_getMonthName(_selectedDate.month)}',
                    style: TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: colorScheme.onSurface,
                    ),
                  ),
                ),
                Expanded(
                  child: selectedDayEvents.isEmpty
                      ? Center(
                          child: Text(
                            'No events',
                            style: TextStyle(
                              color: colorScheme.onSurface.withValues(alpha: 0.5),
                            ),
                          ),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.symmetric(horizontal: 16),
                          itemCount: selectedDayEvents.length,
                          itemBuilder: (context, index) {
                            final event = selectedDayEvents[index];
                            return Card(
                              margin: const EdgeInsets.only(bottom: 8),
                              child: ListTile(
                                leading: Container(
                                  width: 4,
                                  height: 40,
                                  decoration: BoxDecoration(
                                    color: event['color'] as Color,
                                    borderRadius: BorderRadius.circular(2),
                                  ),
                                ),
                                title: Text(event['title'] as String),
                                subtitle: Text(event['time'] as String),
                                trailing: IconButton(
                                  onPressed: () => _removeEvent(_selectedDate.day, index),
                                  icon: Icon(
                                    Icons.close,
                                    size: 18,
                                    color: colorScheme.onSurface.withValues(alpha: 0.5),
                                  ),
                                ),
                              ),
                            );
                          },
                        ),
                ),
                // Mini event creator
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    border: Border(
                      top: BorderSide(
                        color: colorScheme.outline.withValues(alpha: 0.2),
                      ),
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'New Event',
                        style: TextStyle(
                          fontWeight: FontWeight.bold,
                          color: colorScheme.onSurface,
                        ),
                      ),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _eventController,
                        decoration: InputDecoration(
                          hintText: 'Event title',
                          border: const OutlineInputBorder(),
                          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        ),
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          // Time picker
                          OutlinedButton.icon(
                            onPressed: () async {
                              final time = await showTimePicker(
                                context: context,
                                initialTime: _selectedTime,
                              );
                              if (time != null) setState(() => _selectedTime = time);
                            },
                            icon: const Icon(Icons.access_time, size: 18),
                            label: Text(_selectedTime.format(context)),
                          ),
                          const SizedBox(width: 8),
                          // Color picker
                          ..._eventColors.map((color) {
                            return GestureDetector(
                              onTap: () => setState(() => _selectedEventColor = color),
                              child: Container(
                                width: 24,
                                height: 24,
                                margin: const EdgeInsets.only(right: 4),
                                decoration: BoxDecoration(
                                  color: color,
                                  shape: BoxShape.circle,
                                  border: _selectedEventColor == color
                                      ? Border.all(color: colorScheme.onSurface, width: 2)
                                      : null,
                                ),
                              ),
                            );
                          }),
                        ],
                      ),
                      const SizedBox(height: 8),
                      SizedBox(
                        width: double.infinity,
                        child: FilledButton(
                          onPressed: _addEvent,
                          child: const Text('Add Event'),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
