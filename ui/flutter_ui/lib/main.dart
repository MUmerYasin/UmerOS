import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flex_color_scheme/flex_color_scheme.dart';
import 'package:google_fonts/google_fonts.dart';
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
          final fontBase = GoogleFonts.interTextTheme();

          return MaterialApp(
            title: 'UmerOS Desktop',
            debugShowCheckedModeBanner: false,
            theme: FlexThemeData.light(
              scheme: themeProvider.flexScheme,
              surfaceMode: FlexSurfaceMode.levelSurfacesLowScaffold,
              blendLevel: 7,
              subThemesData: const FlexSubThemesData(
                blendOnLevel: 10,
                blendOnColors: false,
                useMaterial3Typography: true,
                useM2StyleDividerInM3: false,
                inputDecoratorBorderType: FlexInputBorderType.outline,
                inputDecoratorRadius: 16.0,
                chipRadius: 20.0,
                cardRadius: 20.0,
                dialogRadius: 28.0,
                fabRadius: 16.0,
                navigationBarIndicatorRadius: 16.0,
                tooltipRadius: 10.0,
              ),
              visualDensity: FlexColorScheme.comfortablePlatformDensity,
              useMaterial3: true,
              fontFamily: GoogleFonts.inter().fontFamily,
              textTheme: fontBase,
            ),
            darkTheme: FlexThemeData.dark(
              scheme: themeProvider.flexScheme,
              surfaceMode: FlexSurfaceMode.levelSurfacesLowScaffold,
              blendLevel: 14,
              subThemesData: const FlexSubThemesData(
                blendOnLevel: 20,
                useMaterial3Typography: true,
                useM2StyleDividerInM3: false,
                inputDecoratorBorderType: FlexInputBorderType.outline,
                inputDecoratorRadius: 16.0,
                chipRadius: 20.0,
                cardRadius: 20.0,
                dialogRadius: 28.0,
                fabRadius: 16.0,
                navigationBarIndicatorRadius: 16.0,
                tooltipRadius: 10.0,
              ),
              visualDensity: FlexColorScheme.comfortablePlatformDensity,
              useMaterial3: true,
              fontFamily: GoogleFonts.inter().fontFamily,
              textTheme: fontBase,
            ),
            themeMode: themeProvider.themeMode,
            home: const DesktopShell(),
          );
        },
      ),
    );
  }
}
