import 'package:flutter/material.dart';

class NetworkManagerApp extends StatefulWidget {
  const NetworkManagerApp({super.key});

  @override
  State<NetworkManagerApp> createState() => _NetworkManagerAppState();
}

class _NetworkManagerAppState extends State<NetworkManagerApp>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final List<Map<String, dynamic>> _wifiNetworks = [
    {'name': 'UmerOS-Home', 'signal': 4, 'security': 'WPA3', 'connected': true},
    {'name': 'UmerOS-5G', 'signal': 3, 'security': 'WPA2', 'connected': false},
    {'name': 'Neighbor_Network', 'signal': 2, 'security': 'WPA2', 'connected': false},
    {'name': 'Cafe_WiFi', 'signal': 3, 'security': 'Open', 'connected': false},
    {'name': 'UmerOS-Guest', 'signal': 1, 'security': 'WPA3', 'connected': false},
  ];

  final List<Map<String, dynamic>> _interfaces = [
    {'name': 'eth0', 'type': 'Ethernet', 'mac': '00:1A:2B:3C:4D:5E', 'ip': '192.168.1.100', 'gateway': '192.168.1.1', 'dns': '8.8.8.8', 'status': 'up', 'enabled': true},
    {'name': 'wlan0', 'type': 'WiFi', 'mac': 'AA:BB:CC:DD:EE:FF', 'ip': '192.168.1.105', 'gateway': '192.168.1.1', 'dns': '8.8.4.4', 'status': 'up', 'enabled': true},
    {'name': 'lo', 'type': 'Loopback', 'mac': '00:00:00:00:00:00', 'ip': '127.0.0.1', 'gateway': '127.0.0.1', 'dns': '127.0.0.1', 'status': 'up', 'enabled': true},
  ];

  final List<Map<String, dynamic>> _firewallRules = [
    {'source': '192.168.1.0/24', 'destination': '*', 'port': '80,443', 'action': 'Allow', 'protocol': 'TCP'},
    {'source': '*', 'destination': '192.168.1.50', 'port': '22', 'action': 'Block', 'protocol': 'TCP'},
    {'source': '10.0.0.0/8', 'destination': '*', 'port': '*', 'action': 'Allow', 'protocol': 'UDP'},
    {'source': '*', 'destination': '*', 'port': '3389', 'action': 'Block', 'protocol': 'TCP'},
  ];

  String _defaultPolicy = 'Allow';

  final List<Map<String, dynamic>> _vpnProfiles = [
    {'name': 'UmerOS-VPN', 'server': 'vpn.umeros.dev', 'protocol': 'WireGuard', 'connected': true},
    {'name': 'Office-VPN', 'server': 'office.corp.net', 'protocol': 'OpenVPN', 'connected': false},
    {'name': 'Secure-Tunnel', 'server': 'tunnel.secure.io', 'protocol': 'IKEv2', 'connected': false},
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 4, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  IconData _getSignalIcon(int strength) {
    switch (strength) {
      case 4:
        return Icons.signal_cellular_4_bar;
      case 3:
        return Icons.signal_cellular_alt;
      case 2:
        return Icons.signal_cellular_alt_2_bar;
      case 1:
        return Icons.signal_cellular_alt_1_bar;
      default:
        return Icons.signal_cellular_off;
    }
  }

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;

    return Column(
      children: [
        Container(
          decoration: BoxDecoration(
            color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
            border: Border(
              bottom: BorderSide(
                color: colorScheme.outline.withValues(alpha: 0.2),
              ),
            ),
          ),
          child: TabBar(
            controller: _tabController,
            tabs: const [
              Tab(icon: Icon(Icons.wifi), text: 'Connections'),
              Tab(icon: Icon(Icons.lan), text: 'Interfaces'),
              Tab(icon: Icon(Icons.shield), text: 'Firewall'),
              Tab(icon: Icon(Icons.vpn_key), text: 'VPN'),
            ],
          ),
        ),
        Expanded(
          child: TabBarView(
            controller: _tabController,
            children: [
              _buildConnectionsTab(colorScheme),
              _buildInterfacesTab(colorScheme),
              _buildFirewallTab(colorScheme),
              _buildVpnTab(colorScheme),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildConnectionsTab(ColorScheme colorScheme) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Icon(Icons.wifi, color: colorScheme.primary),
              const SizedBox(width: 12),
              Text(
                'WiFi Networks',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: colorScheme.onSurface,
                ),
              ),
              const Spacer(),
              Switch(
                value: true,
                onChanged: (v) {},
                activeThumbColor: colorScheme.primary,
              ),
              const SizedBox(width: 8),
              Text('WiFi', style: TextStyle(color: colorScheme.onSurface)),
            ],
          ),
        ),
        Expanded(
          child: ListView.builder(
            itemCount: _wifiNetworks.length,
            itemBuilder: (context, index) {
              final network = _wifiNetworks[index];
              final isConnected = network['connected'];
              return Card(
                margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                color: isConnected
                    ? colorScheme.primaryContainer.withValues(alpha: 0.3)
                    : null,
                child: ListTile(
                  leading: Icon(
                    _getSignalIcon(network['signal']),
                    color: isConnected ? colorScheme.primary : colorScheme.onSurface,
                  ),
                  title: Text(
                    network['name'],
                    style: TextStyle(
                      fontWeight: isConnected ? FontWeight.bold : FontWeight.normal,
                      color: colorScheme.onSurface,
                    ),
                  ),
                  subtitle: Text(
                    '${network['security']} ${isConnected ? '(Connected)' : ''}',
                    style: TextStyle(
                      color: colorScheme.onSurface.withValues(alpha: 0.7),
                    ),
                  ),
                  trailing: isConnected
                      ? TextButton(
                          onPressed: () {
                            setState(() {
                              network['connected'] = false;
                            });
                          },
                          child: Text('Disconnect', style: TextStyle(color: colorScheme.error)),
                        )
                      : FilledButton(
                          onPressed: () {
                            setState(() {
                              for (var n in _wifiNetworks) {
                                n['connected'] = false;
                              }
                              network['connected'] = true;
                            });
                          },
                          child: const Text('Connect'),
                        ),
                ),
              );
            },
          ),
        ),
      ],
    );
  }

  Widget _buildInterfacesTab(ColorScheme colorScheme) {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _interfaces.length,
      itemBuilder: (context, index) {
        final iface = _interfaces[index];
        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: ExpansionTile(
            leading: Icon(
              iface['type'] == 'WiFi' ? Icons.wifi : Icons.lan,
              color: iface['status'] == 'up' ? colorScheme.primary : colorScheme.onSurface.withValues(alpha: 0.5),
            ),
            title: Text(
              iface['name'],
              style: TextStyle(
                fontWeight: FontWeight.bold,
                color: colorScheme.onSurface,
              ),
            ),
            subtitle: Text(
              '${iface['type']} • ${iface['status']}',
              style: TextStyle(
                color: iface['status'] == 'up' ? Colors.green : colorScheme.error,
              ),
            ),
            trailing: Switch(
              value: iface['enabled'],
              onChanged: (val) {
                setState(() {
                  iface['enabled'] = val;
                  iface['status'] = val ? 'up' : 'down';
                });
              },
              activeThumbColor: colorScheme.primary,
            ),
            children: [
              Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  children: [
                    _infoRow('MAC Address', iface['mac'], colorScheme),
                    _infoRow('IP Address', iface['ip'], colorScheme),
                    _infoRow('Gateway', iface['gateway'], colorScheme),
                    _infoRow('DNS', iface['dns'], colorScheme),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _infoRow(String label, String value, ColorScheme colorScheme) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: TextStyle(
              color: colorScheme.onSurface.withValues(alpha: 0.7),
            ),
          ),
          Text(
            value,
            style: TextStyle(
              fontWeight: FontWeight.w500,
              color: colorScheme.onSurface,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFirewallTab(ColorScheme colorScheme) {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Text(
                'Firewall Rules',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.bold,
                  color: colorScheme.onSurface,
                ),
              ),
              const Spacer(),
              DropdownButton<String>(
                value: _defaultPolicy,
                items: ['Allow', 'Block'].map((e) {
                  return DropdownMenuItem(value: e, child: Text(e));
                }).toList(),
                onChanged: (val) {
                  if (val != null) setState(() => _defaultPolicy = val);
                },
              ),
              const SizedBox(width: 8),
              Text('Default Policy', style: TextStyle(color: colorScheme.onSurface)),
              const Spacer(),
              IconButton(
                onPressed: () {},
                icon: const Icon(Icons.add_circle_outline),
                tooltip: 'Add Rule',
              ),
            ],
          ),
        ),
        Expanded(
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: DataTable(
              columns: const [
                DataColumn(label: Text('Source')),
                DataColumn(label: Text('Destination')),
                DataColumn(label: Text('Port')),
                DataColumn(label: Text('Action')),
                DataColumn(label: Text('Protocol')),
                DataColumn(label: Text('')),
              ],
              rows: _firewallRules.map((rule) {
                return DataRow(cells: [
                  DataCell(Text(rule['source'])),
                  DataCell(Text(rule['destination'])),
                  DataCell(Text(rule['port'])),
                  DataCell(
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: rule['action'] == 'Allow'
                            ? Colors.green.withValues(alpha: 0.2)
                            : Colors.red.withValues(alpha: 0.2),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        rule['action'],
                        style: TextStyle(
                          color: rule['action'] == 'Allow' ? Colors.green : Colors.red,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ),
                  DataCell(Text(rule['protocol'])),
                  DataCell(
                    IconButton(
                      onPressed: () {
                        setState(() => _firewallRules.remove(rule));
                      },
                      icon: Icon(Icons.delete_outline, color: colorScheme.error, size: 20),
                    ),
                  ),
                ]);
              }).toList(),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildVpnTab(ColorScheme colorScheme) {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: _vpnProfiles.length,
      itemBuilder: (context, index) {
        final vpn = _vpnProfiles[index];
        final isConnected = vpn['connected'];
        return Card(
          margin: const EdgeInsets.only(bottom: 12),
          child: ListTile(
            leading: Icon(
              Icons.vpn_key,
              color: isConnected ? colorScheme.primary : colorScheme.onSurface.withValues(alpha: 0.6),
            ),
            title: Text(
              vpn['name'],
              style: TextStyle(
                fontWeight: FontWeight.bold,
                color: colorScheme.onSurface,
              ),
            ),
            subtitle: Text(
              '${vpn['server']} • ${vpn['protocol']}',
              style: TextStyle(
                color: colorScheme.onSurface.withValues(alpha: 0.7),
              ),
            ),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  onPressed: () {},
                  icon: Icon(Icons.settings, color: colorScheme.onSurface.withValues(alpha: 0.6)),
                  tooltip: 'Configure',
                ),
                const SizedBox(width: 8),
                isConnected
                    ? TextButton(
                        onPressed: () {
                          setState(() => vpn['connected'] = false);
                        },
                        child: Text('Disconnect', style: TextStyle(color: colorScheme.error)),
                      )
                    : FilledButton(
                        onPressed: () {
                          setState(() {
                            for (var v in _vpnProfiles) {
                              v['connected'] = false;
                            }
                            vpn['connected'] = true;
                          });
                        },
                        child: const Text('Connect'),
                      ),
              ],
            ),
          ),
        );
      },
    );
  }
}
