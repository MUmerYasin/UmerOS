import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flex_color_scheme/flex_color_scheme.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:flutter_animate/flutter_animate.dart';
import 'src/core/desktop_shell.dart';
import 'src/core/app_state.dart';
import 'src/core/theme_provider.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const UmerOSApp());
}

class UmerOSApp extends StatelessWidget {
  const UmerOSApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => ThemeProvider()),
        ChangeNotifierProvider(create: (_) => AppState()),
      ],
      child: Consumer<ThemeProvider>(
        builder: (context, themeProvider, _) {
          return MaterialApp(
            title: 'UmerOS',
            debugShowCheckedModeBanner: false,
            theme: FlexThemeData.light(
              scheme: FlexScheme.deepPurple,
              surfaceMode: FlexSurfaceMode.levelSurfacesLowScaffold,
              blendLevel: 7,
              subThemesData: const FlexSubThemesData(
                blendOnLevel: 10,
                blendOnColors: false,
                useTextTheme: true,
                useM2StyleDividerInM3: true,
                inputDecoratorBorderType: FlexInputBorderType.outline,
                inputDecoratorRadius: 12.0,
                chipRadius: 20.0,
                cardRadius: 16.0,
                dialogRadius: 20.0,
               fabRadius: 16.0,
                navigationBarIndicatorRadius: 16.0,
              ),
              visualDensity: FlexColorScheme.comfortablePlatformDensity,
              useMaterial3: true,
              fontFamily: GoogleFonts.inter().fontFamily,
            ),
            darkTheme: FlexThemeData.dark(
              scheme: FlexScheme.deepPurple,
              surfaceMode: FlexSurfaceMode.levelSurfacesLowScaffold,
              blendLevel: 13,
              subThemesData: const FlexSubThemesData(
                blendOnLevel: 20,
                useTextTheme: true,
                useM2StyleDividerInM3: true,
                inputDecoratorBorderType: FlexInputBorderType.outline,
                inputDecoratorRadius: 12.0,
                chipRadius: 20.0,
                cardRadius: 16.0,
                dialogRadius: 20.0,
                fabRadius: 16.0,
                navigationBarIndicatorRadius: 16.0,
              ),
              visualDensity: FlexColorScheme.comfortablePlatformDensity,
              useMaterial3: true,
              fontFamily: GoogleFonts.inter().fontFamily,
            ),
            themeMode: themeProvider.themeMode,
            home: const DesktopShell(),
          );
        },
      ),
    );
  }
}
