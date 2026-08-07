import 'package:flutter/material.dart';
import 'dart:async';
import 'dart:math';

// ─── Games App (Hub) ────────────────────────────────────────────────────────

class GamesApp extends StatefulWidget {
  const GamesApp({super.key});

  @override
  State<GamesApp> createState() => _GamesAppState();
}

class _GamesAppState extends State<GamesApp> {
  String _currentView = 'hub';
  String _currentGame = '';

  void _openGame(String game) {
    setState(() {
      _currentView = 'game';
      _currentGame = game;
    });
  }

  void _backToHub() {
    setState(() {
      _currentView = 'hub';
      _currentGame = '';
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      backgroundColor:
          isDark ? theme.scaffoldBackgroundColor : theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: isDark ? Colors.grey[850] : theme.primaryColor,
        leading: _currentView != 'hub'
            ? IconButton(
                icon: const Icon(Icons.arrow_back),
                onPressed: _backToHub,
              )
            : null,
        title: Text(
          _currentView == 'hub'
              ? '🎮 Games'
              : _getGameTitle(_currentGame),
          style: const TextStyle(color: Colors.white),
        ),
        elevation: 2,
      ),
      body: _currentView == 'hub' ? _buildHub(isDark) : _buildGameView(),
    );
  }

  String _getGameTitle(String game) {
    switch (game) {
      case 'snake':
        return '🐍 Snake';
      case 'tictactoe':
        return '⭕ Tic-Tac-Toe';
      case 'memory':
        return '🧠 Memory';
      default:
        return 'Games';
    }
  }

  Widget _buildHub(bool isDark) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'Available Games',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 12),
          GridView.count(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisCount: 2,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            children: [
              _buildGameCard(
                icon: Icons.play_arrow,
                name: 'Snake',
                description: 'Classic snake game',
                highScore: 42,
                onTap: () => _openGame('snake'),
                color: Colors.green,
              ),
              _buildGameCard(
                icon: Icons.grid_3x3,
                name: 'Tic-Tac-Toe',
                description: '3x3 strategy game',
                highScore: 10,
                onTap: () => _openGame('tictactoe'),
                color: Colors.blue,
              ),
              _buildGameCard(
                icon: Icons.memory,
                name: 'Memory',
                description: 'Match the pairs',
                highScore: 28,
                onTap: () => _openGame('memory'),
                color: Colors.purple,
              ),
              _buildDownloadCard(),
            ],
          ),
          const SizedBox(height: 24),
          Text(
            'Download Games',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 12),
          _buildDownloadSection(),
          const SizedBox(height: 24),
          Text(
            'Prerequisites',
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
          ),
          const SizedBox(height: 12),
          _buildPrerequisitesSection(),
        ],
      ),
    );
  }

  Widget _buildGameCard({
    required IconData icon,
    required String name,
    required String description,
    required int highScore,
    required VoidCallback onTap,
    required Color color,
  }) {
    final theme = Theme.of(context);

    return Card(
      elevation: 3,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                color.withValues(alpha: 0.15),
                color.withValues(alpha: 0.05),
              ],
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 48, color: color),
              const SizedBox(height: 8),
              Text(
                name,
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                description,
                style: theme.textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
              const Spacer(),
              Text(
                'High Score: $highScore',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: Colors.amber[700],
                  fontWeight: FontWeight.w600,
                ),
              ),
              const SizedBox(height: 8),
              ElevatedButton.icon(
                onPressed: onTap,
                icon: const Icon(Icons.play_arrow, size: 18),
                label: const Text('Play'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: color,
                  foregroundColor: Colors.white,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(20),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDownloadCard() {
    final theme = Theme.of(context);

    return Card(
      elevation: 3,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: InkWell(
        onTap: () {
          // Scroll to download section
        },
        borderRadius: BorderRadius.circular(12),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [
                Colors.orange.withValues(alpha: 0.15),
                Colors.orange.withValues(alpha: 0.05),
              ],
            ),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.download, size: 48, color: Colors.orange[600]),
              const SizedBox(height: 8),
              Text(
                'Download Games',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                '5 open-source games',
                style: theme.textTheme.bodySmall,
              ),
              const Spacer(),
              Text(
                'Browse Collection',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: Colors.orange[700],
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildDownloadSection() {
    final games = [
      {
        'name': 'SuperTux',
        'desc': 'Fun platformer featuring Tux the penguin',
        'rating': '4.5',
        'size': '250 MB',
        'cmd': 'sudo apt install supertux',
      },
      {
        'name': 'OpenTTD',
        'desc': 'Business simulation game',
        'rating': '4.7',
        'size': '180 MB',
        'cmd': 'sudo apt install openttd',
      },
      {
        'name': '0 A.D.',
        'desc': 'Real-time strategy game',
        'rating': '4.6',
        'size': '450 MB',
        'cmd': 'sudo apt install 0ad',
      },
      {
        'name': 'Wesnoth',
        'desc': 'Turn-based fantasy strategy',
        'rating': '4.4',
        'size': '320 MB',
        'cmd': 'sudo apt install wesnoth',
      },
      {
        'name': 'OpenRA',
        'desc': 'RTS game engine (C&C, Dune)',
        'rating': '4.3',
        'size': '200 MB',
        'cmd': 'sudo snap install openra',
      },
    ];

    return Column(
      children: games.map((game) => _buildDownloadItem(game)).toList(),
    );
  }

  Widget _buildDownloadItem(Map<String, String> game) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      elevation: 1,
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: Colors.orange.withValues(alpha: 0.2),
          child: const Icon(Icons.games, color: Colors.orange),
        ),
        title: Text(game['name']!, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(game['desc']!, style: theme.textTheme.bodySmall),
            const SizedBox(height: 4),
            Row(
              children: [
                Icon(Icons.star, size: 14, color: Colors.amber[600]),
                const SizedBox(width: 4),
                Text(game['rating']!, style: theme.textTheme.bodySmall),
                const SizedBox(width: 12),
                Icon(Icons.sd_storage, size: 14, color: Colors.grey[600]),
                const SizedBox(width: 4),
                Text(game['size']!, style: theme.textTheme.bodySmall),
              ],
            ),
          ],
        ),
        trailing: ElevatedButton.icon(
          onPressed: () {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(content: Text('Running: ${game['cmd']}')),
            );
          },
          icon: const Icon(Icons.download, size: 16),
          label: const Text('Install'),
          style: ElevatedButton.styleFrom(
            backgroundColor: isDark ? Colors.grey[700] : Colors.blue[600],
            foregroundColor: Colors.white,
          ),
        ),
        isThreeLine: true,
      ),
    );
  }

  Widget _buildPrerequisitesSection() {
    final prereqs = [
      {'name': 'DOSBox', 'desc': 'MS-DOS emulator for classic games', 'icon': Icons.computer},
      {'name': 'LÖVE', 'desc': 'Lua game framework', 'icon': Icons.favorite},
      {'name': 'Godot', 'desc': 'Full game engine', 'icon': Icons.build},
      {'name': 'ScummVM', 'desc': 'Adventure game engine', 'icon': Icons.explore},
    ];

    return Column(
      children: prereqs.map((p) {
        return Card(
          margin: const EdgeInsets.only(bottom: 8),
          child: ListTile(
            leading: CircleAvatar(
              backgroundColor: Colors.teal.withValues(alpha: 0.2),
              child: Icon(p['icon'] as IconData, color: Colors.teal),
            ),
            title: Text(p['name'] as String, style: const TextStyle(fontWeight: FontWeight.w600)),
            subtitle: Text(p['desc'] as String),
            trailing: OutlinedButton.icon(
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Installing ${(p['name'] as String).toLowerCase()}...')),
                );
              },
              icon: const Icon(Icons.download, size: 16),
              label: const Text('Install'),
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildGameView() {
    switch (_currentGame) {
      case 'snake':
        return const SnakeGame();
      case 'tictactoe':
        return const TicTacToeGame();
      case 'memory':
        return const MemoryGame();
      default:
        return const Center(child: Text('Game not found'));
    }
  }
}

// ─── Snake Game ──────────────────────────────────────────────────────────────

class SnakeGame extends StatefulWidget {
  const SnakeGame({super.key});

  @override
  State<SnakeGame> createState() => _SnakeGameState();
}

class _SnakeGameState extends State<SnakeGame> {
  static const int gridSize = 20;
  List<Point<int>> _snake = [const Point(10, 10)];
  Point<int> _food = const Point(5, 5);
  String _direction = 'right';
  bool _isRunning = false;
  bool _isPaused = false;
  bool _isGameOver = false;
  int _score = 0;
  int _highScore = 42;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _spawnFood();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _startGame() {
    setState(() {
      _snake = [const Point(10, 10)];
      _direction = 'right';
      _score = 0;
      _isRunning = true;
      _isPaused = false;
      _isGameOver = false;
    });
    _spawnFood();
    _timer?.cancel();
    _timer = Timer.periodic(const Duration(milliseconds: 150), (_) => _tick());
  }

  void _pauseGame() {
    setState(() => _isPaused = !_isPaused);
    if (_isPaused) {
      _timer?.cancel();
    } else {
      _timer = Timer.periodic(const Duration(milliseconds: 150), (_) => _tick());
    }
  }

  void _resetGame() {
    _timer?.cancel();
    setState(() {
      _snake = [const Point(10, 10)];
      _direction = 'right';
      _score = 0;
      _isRunning = false;
      _isPaused = false;
      _isGameOver = false;
    });
    _spawnFood();
  }

  void _spawnFood() {
    final rng = Random();
    Point<int> newFood;
    do {
      newFood = Point(rng.nextInt(gridSize), rng.nextInt(gridSize));
    } while (_snake.contains(newFood));
    setState(() => _food = newFood);
  }

  void _tick() {
    if (!_isRunning || _isPaused || _isGameOver) return;

    setState(() {
      final head = _snake.first;
      Point<int> newHead;

      switch (_direction) {
        case 'up':
          newHead = Point(head.x, head.y - 1);
          break;
        case 'down':
          newHead = Point(head.x, head.y + 1);
          break;
        case 'left':
          newHead = Point(head.x - 1, head.y);
          break;
        case 'right':
          newHead = Point(head.x + 1, head.y);
          break;
        default:
          newHead = head;
      }

      // Wall collision
      if (newHead.x < 0 ||
          newHead.x >= gridSize ||
          newHead.y < 0 ||
          newHead.y >= gridSize) {
        _endGame();
        return;
      }

      // Self collision
      if (_snake.contains(newHead)) {
        _endGame();
        return;
      }

      _snake.insert(0, newHead);

      if (newHead == _food) {
        _score += 10;
        _spawnFood();
      } else {
        _snake.removeLast();
      }
    });
  }

  void _endGame() {
    _timer?.cancel();
    setState(() {
      _isGameOver = true;
      _isRunning = false;
      if (_score > _highScore) _highScore = _score;
    });
  }

  void _changeDirection(String dir) {
    final opposites = {'up': 'down', 'down': 'up', 'left': 'right', 'right': 'left'};
    if (opposites[dir] != _direction) {
      setState(() => _direction = dir);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Stack(
      children: [
        Column(
          children: [
            // Score bar
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              color: isDark ? Colors.grey[850] : theme.primaryColor,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Score: $_score',
                    style: const TextStyle(
                      color: Colors.white,
                      fontSize: 16,
                      fontWeight: FontWeight.bold,
                    ),
                  ),
                  Text(
                    'High: $_highScore',
                    style: const TextStyle(color: Colors.amber, fontSize: 14),
                  ),
                  Row(
                    children: [
                      IconButton(
                        icon: Icon(
                          _isPaused ? Icons.play_arrow : Icons.pause,
                          color: Colors.white,
                        ),
                        onPressed: _isRunning ? _pauseGame : null,
                      ),
                      IconButton(
                        icon: const Icon(Icons.refresh, color: Colors.white),
                        onPressed: _resetGame,
                      ),
                    ],
                  ),
                ],
              ),
            ),

            // Grid
            Expanded(
              child: Center(
                child: Container(
                  constraints: const BoxConstraints(maxWidth: 400, maxHeight: 400),
                  margin: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    border: Border.all(
                      color: isDark ? Colors.grey[700]! : Colors.grey[300]!,
                      width: 2,
                    ),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: GridView.builder(
                    physics: const NeverScrollableScrollPhysics(),
                    gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                      crossAxisCount: gridSize,
                    ),
                    itemCount: gridSize * gridSize,
                    itemBuilder: (context, index) {
                      final x = index % gridSize;
                      final y = index ~/ gridSize;
                      final point = Point(x, y);

                      Color cellColor;
                      if (_snake.first == point) {
                        cellColor = Colors.green[800]!;
                      } else if (_snake.contains(point)) {
                        cellColor = Colors.green[400]!;
                      } else if (point == _food) {
                        cellColor = Colors.red[600]!;
                      } else {
                        cellColor = isDark ? Colors.grey[900]! : Colors.grey[100]!;
                      }

                      return Container(
                        decoration: BoxDecoration(
                          color: cellColor,
                          border: Border.all(
                            color: isDark ? Colors.grey[800]! : Colors.grey[200]!,
                            width: 0.5,
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ),
            ),

            // Controls
            Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                children: [
                  IconButton(
                    icon: const Icon(Icons.arrow_drop_up, size: 40),
                    onPressed: () => _changeDirection('up'),
                  ),
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      IconButton(
                        icon: const Icon(Icons.arrow_left, size: 40),
                        onPressed: () => _changeDirection('left'),
                      ),
                      const SizedBox(width: 40),
                      IconButton(
                        icon: const Icon(Icons.arrow_right, size: 40),
                        onPressed: () => _changeDirection('right'),
                      ),
                    ],
                  ),
                  IconButton(
                    icon: const Icon(Icons.arrow_drop_down, size: 40),
                    onPressed: () => _changeDirection('down'),
                  ),
                ],
              ),
            ),

            // Start button
            if (!_isRunning && !_isGameOver)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: ElevatedButton.icon(
                  onPressed: _startGame,
                  icon: const Icon(Icons.play_arrow),
                  label: const Text('Start Game'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green,
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 12),
                  ),
                ),
              ),
          ],
        ),

        // Game Over overlay
        if (_isGameOver)
          Container(
            color: Colors.black54,
            child: Center(
              child: Card(
                margin: const EdgeInsets.all(32),
                child: Padding(
                  padding: const EdgeInsets.all(32),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.sentiment_dissatisfied, size: 64, color: Colors.red),
                      const SizedBox(height: 16),
                      Text(
                        'Game Over!',
                        style: theme.textTheme.headlineMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        'Score: $_score',
                        style: theme.textTheme.titleLarge?.copyWith(
                          color: Colors.amber[700],
                        ),
                      ),
                      if (_score >= _highScore) ...[
                        const SizedBox(height: 8),
                        const Text(
                          '🎉 New High Score!',
                          style: TextStyle(color: Colors.green, fontWeight: FontWeight.bold),
                        ),
                      ],
                      const SizedBox(height: 24),
                      ElevatedButton.icon(
                        onPressed: _startGame,
                        icon: const Icon(Icons.refresh),
                        label: const Text('Play Again'),
                        style: ElevatedButton.styleFrom(
                          backgroundColor: Colors.green,
                          foregroundColor: Colors.white,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
      ],
    );
  }
}

// ─── Tic-Tac-Toe Game ────────────────────────────────────────────────────────

class TicTacToeGame extends StatefulWidget {
  const TicTacToeGame({super.key});

  @override
  State<TicTacToeGame> createState() => _TicTacToeGameState();
}

class _TicTacToeGameState extends State<TicTacToeGame> {
  List<String> _board = List.filled(9, '');
  String _currentPlayer = 'X';
  bool _gameOver = false;
  String _winner = '';
  List<int> _winningLine = [];
  int _scoreX = 0;
  int _scoreO = 0;
  int _draws = 0;

  static const List<List<int>> _winConditions = [
    [0, 1, 2], [3, 4, 5], [6, 7, 8], // rows
    [0, 3, 6], [1, 4, 7], [2, 5, 8], // cols
    [0, 4, 8], [2, 4, 6],             // diagonals
  ];

  void _handleTap(int index) {
    if (_board[index] != '' || _gameOver) return;

    setState(() {
      _board[index] = _currentPlayer;

      // Check win
      for (final line in _winConditions) {
        if (_board[line[0]] == _currentPlayer &&
            _board[line[1]] == _currentPlayer &&
            _board[line[2]] == _currentPlayer) {
          _winner = _currentPlayer;
          _winningLine = line;
          _gameOver = true;
          if (_currentPlayer == 'X') {
            _scoreX++;
          } else {
            _scoreO++;
          }
          return;
        }
      }

      // Check draw
      if (!_board.contains('')) {
        _gameOver = true;
        _draws++;
        return;
      }

      _currentPlayer = _currentPlayer == 'X' ? 'O' : 'X';
    });
  }

  void _resetGame() {
    setState(() {
      _board = List.filled(9, '');
      _currentPlayer = 'X';
      _gameOver = false;
      _winner = '';
      _winningLine = [];
    });
  }

  void _resetScores() {
    setState(() {
      _scoreX = 0;
      _scoreO = 0;
      _draws = 0;
    });
    _resetGame();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Column(
      children: [
        // Score board
        Container(
          padding: const EdgeInsets.all(16),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _buildScoreChip('X', _scoreX, Colors.blue, isDark),
              _buildScoreChip('Draw', _draws, Colors.grey, isDark),
              _buildScoreChip('O', _scoreO, Colors.red, isDark),
            ],
          ),
        ),

        // Current player indicator
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 8),
          decoration: BoxDecoration(
            color: _currentPlayer == 'X'
                ? Colors.blue.withValues(alpha: 0.2)
                : Colors.red.withValues(alpha: 0.2),
            borderRadius: BorderRadius.circular(20),
          ),
          child: Text(
            _gameOver
                ? (_winner.isNotEmpty ? '$_winner Wins!' : 'Draw!')
                : 'Player $_currentPlayer\'s Turn',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
              color: _winner == 'X'
                  ? Colors.blue
                  : _winner == 'O'
                      ? Colors.red
                      : null,
            ),
          ),
        ),

        const SizedBox(height: 24),

        // 3x3 Grid
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 48),
          child: Column(
            children: List.generate(3, (row) {
              return Row(
                children: List.generate(3, (col) {
                  final index = row * 3 + col;
                  final isWinning = _winningLine.contains(index);
                  final cell = _board[index];

                  return GestureDetector(
                    onTap: () => _handleTap(index),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      width: 90,
                      height: 90,
                      margin: const EdgeInsets.all(4),
                      decoration: BoxDecoration(
                        color: isWinning
                            ? (_winner == 'X'
                                ? Colors.blue.withValues(alpha: 0.3)
                                : Colors.red.withValues(alpha: 0.3))
                            : (isDark ? Colors.grey[800] : Colors.grey[200]),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: isWinning
                              ? (_winner == 'X' ? Colors.blue : Colors.red)
                              : (isDark ? Colors.grey[700]! : Colors.grey[300]!),
                          width: isWinning ? 3 : 1,
                        ),
                      ),
                      child: Center(
                        child: Text(
                          cell,
                          style: TextStyle(
                            fontSize: 36,
                            fontWeight: FontWeight.bold,
                            color: cell == 'X'
                                ? Colors.blue
                                : cell == 'O'
                                    ? Colors.red
                                    : Colors.transparent,
                          ),
                        ),
                      ),
                    ),
                  );
                }),
              );
            }),
          ),
        ),

        const SizedBox(height: 24),

        // Reset button
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            ElevatedButton.icon(
              onPressed: _resetGame,
              icon: const Icon(Icons.refresh),
              label: const Text('New Game'),
              style: ElevatedButton.styleFrom(
                backgroundColor: theme.primaryColor,
                foregroundColor: Colors.white,
              ),
            ),
            const SizedBox(width: 12),
            OutlinedButton.icon(
              onPressed: _resetScores,
              icon: const Icon(Icons.delete),
              label: const Text('Reset Scores'),
            ),
          ],
        ),

        const SizedBox(height: 24),

        // Game over overlay
        if (_gameOver)
          Container(
            padding: const EdgeInsets.all(16),
            margin: const EdgeInsets.symmetric(horizontal: 32),
            decoration: BoxDecoration(
              color: _winner.isNotEmpty
                  ? (_winner == 'X' ? Colors.blue.withValues(alpha: 0.1) : Colors.red.withValues(alpha: 0.1))
                  : Colors.grey.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: _winner.isNotEmpty
                    ? (_winner == 'X' ? Colors.blue : Colors.red)
                    : Colors.grey,
              ),
            ),
            child: Column(
              children: [
                Icon(
                  _winner.isNotEmpty ? Icons.emoji_events : Icons.handshake,
                  size: 48,
                  color: _winner == 'X'
                      ? Colors.blue
                      : _winner == 'O'
                          ? Colors.red
                          : Colors.grey,
                ),
                const SizedBox(height: 8),
                Text(
                  _winner.isNotEmpty ? '$_winner Wins!' : 'It\'s a Draw!',
                  style: theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: _winner == 'X'
                        ? Colors.blue
                        : _winner == 'O'
                            ? Colors.red
                            : Colors.grey,
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _buildScoreChip(String label, int score, Color color, bool isDark) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Column(
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
          Text(
            '$score',
            style: TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}

// ─── Memory Game ─────────────────────────────────────────────────────────────

class MemoryGame extends StatefulWidget {
  const MemoryGame({super.key});

  @override
  State<MemoryGame> createState() => _MemoryGameState();
}

class _MemoryGameState extends State<MemoryGame> {
  static const _emojis = ['🍎', '🍊', '🍋', '🍇', '🍉', '🍓', '🫐', '🍑'];

  late List<String> _cards;
  late List<bool> _flipped;
  late List<bool> _matched;
  int _firstIndex = -1;
  int _secondIndex = -1;
  bool _isChecking = false;
  int _moves = 0;
  int _matchesFound = 0;
  int _timerSeconds = 0;
  Timer? _timer;
  bool _gameStarted = false;
  bool _allMatched = false;

  @override
  void initState() {
    super.initState();
    _initializeGame();
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  void _initializeGame() {
    // Create pairs
    final allEmojis = [..._emojis, ..._emojis];
    allEmojis.shuffle(Random());

    setState(() {
      _cards = allEmojis;
      _flipped = List.filled(16, false);
      _matched = List.filled(16, false);
      _firstIndex = -1;
      _secondIndex = -1;
      _isChecking = false;
      _moves = 0;
      _matchesFound = 0;
      _timerSeconds = 0;
      _gameStarted = false;
      _allMatched = false;
    });

    _timer?.cancel();
  }

  void _startTimer() {
    if (_gameStarted) return;
    _gameStarted = true;
    _timer = Timer.periodic(const Duration(seconds: 1), (timer) {
      setState(() => _timerSeconds++);
    });
  }

  void _stopTimer() {
    _timer?.cancel();
  }

  void _resetGame() {
    _stopTimer();
    _initializeGame();
  }

  void _handleTap(int index) {
    if (_isChecking) return;
    if (_flipped[index] || _matched[index]) return;

    _startTimer();

    setState(() {
      _flipped[index] = true;

      if (_firstIndex == -1) {
        _firstIndex = index;
      } else {
        _secondIndex = index;
        _moves++;
        _isChecking = true;

        // Check match after a short delay
        Future.delayed(const Duration(milliseconds: 800), () {
          if (!mounted) return;

          setState(() {
            if (_cards[_firstIndex] == _cards[_secondIndex]) {
              _matched[_firstIndex] = true;
              _matched[_secondIndex] = true;
              _matchesFound++;

              if (_matchesFound == 8) {
                _stopTimer();
                _allMatched = true;
              }
            } else {
              _flipped[_firstIndex] = false;
              _flipped[_secondIndex] = false;
            }

            _firstIndex = -1;
            _secondIndex = -1;
            _isChecking = false;
          });
        });
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Column(
      children: [
        // Stats bar
        Container(
          padding: const EdgeInsets.all(16),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceEvenly,
            children: [
              _buildStat('Moves', '$_moves', Icons.touch_app, isDark),
              _buildStat(
                'Time',
                '${(_timerSeconds ~/ 60).toString().padLeft(2, '0')}:${(_timerSeconds % 60).toString().padLeft(2, '0')}',
                Icons.timer,
                isDark,
              ),
              _buildStat('Matched', '$_matchesFound/8', Icons.check_circle, isDark),
            ],
          ),
        ),

        const SizedBox(height: 8),

        // Reset button
        ElevatedButton.icon(
          onPressed: _resetGame,
          icon: const Icon(Icons.refresh),
          label: const Text('New Game'),
          style: ElevatedButton.styleFrom(
            backgroundColor: theme.primaryColor,
            foregroundColor: Colors.white,
          ),
        ),

        const SizedBox(height: 16),

        // 4x4 Card Grid
        Expanded(
          child: Center(
            child: Container(
              constraints: const BoxConstraints(maxWidth: 360),
              padding: const EdgeInsets.all(12),
              child: GridView.builder(
                physics: const NeverScrollableScrollPhysics(),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 4,
                  crossAxisSpacing: 8,
                  mainAxisSpacing: 8,
                ),
                itemCount: 16,
                itemBuilder: (context, index) {
                  final isFlipped = _flipped[index] || _matched[index];
                  final emoji = _cards[index];

                  return GestureDetector(
                    onTap: () => _handleTap(index),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 300),
                      curve: Curves.easeInOut,
                      decoration: BoxDecoration(
                        color: isFlipped
                            ? (_matched[index]
                                ? Colors.green.withValues(alpha: 0.2)
                                : isDark
                                    ? Colors.grey[700]
                                    : Colors.white)
                            : (isDark ? Colors.indigo[800] : Colors.indigo[300]),
                        borderRadius: BorderRadius.circular(8),
                        border: Border.all(
                          color: _matched[index]
                              ? Colors.green
                              : (isDark ? Colors.grey[600]! : Colors.grey[300]!),
                          width: _matched[index] ? 2 : 1,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.black.withValues(alpha: 0.2),
                            blurRadius: 4,
                            offset: const Offset(0, 2),
                          ),
                        ],
                      ),
                      child: Center(
                        child: AnimatedSwitcher(
                          duration: const Duration(milliseconds: 300),
                          child: isFlipped
                              ? Text(
                                  emoji,
                                  key: ValueKey('emoji_$index'),
                                  style: const TextStyle(fontSize: 28),
                                )
                              : Icon(
                                  Icons.question_mark,
                                  key: ValueKey('back_$index'),
                                  color: Colors.white.withValues(alpha: 0.7),
                                  size: 24,
                                ),
                        ),
                      ),
                    ),
                  );
                },
              ),
            ),
          ),
        ),

        // Win overlay
        if (_allMatched)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            margin: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              gradient: LinearGradient(
                colors: [Colors.green.withValues(alpha: 0.2), Colors.teal.withValues(alpha: 0.2)],
              ),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(color: Colors.green),
            ),
            child: Column(
              children: [
                const Text('🎉', style: TextStyle(fontSize: 48)),
                const SizedBox(height: 8),
                Text(
                  'You Won!',
                  style: theme.textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                    color: Colors.green,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  'Completed in $_moves moves and ${(_timerSeconds ~/ 60).toString().padLeft(2, '0')}:${(_timerSeconds % 60).toString().padLeft(2, '0')}',
                  style: theme.textTheme.bodyMedium,
                ),
                const SizedBox(height: 12),
                ElevatedButton.icon(
                  onPressed: _resetGame,
                  icon: const Icon(Icons.replay),
                  label: const Text('Play Again'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.green,
                    foregroundColor: Colors.white,
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _buildStat(String label, String value, IconData icon, bool isDark) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      decoration: BoxDecoration(
        color: isDark ? Colors.grey[800] : Colors.grey[100],
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 18, color: Colors.teal),
          const SizedBox(width: 6),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                label,
                style: const TextStyle(fontSize: 10, color: Colors.grey),
              ),
              Text(
                value,
                style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
