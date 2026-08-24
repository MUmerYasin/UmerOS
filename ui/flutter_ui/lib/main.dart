import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:flex_color_scheme/flex_color_scheme.dart';
import 'package:google_fonts/google_fonts.dart';
import 'src/core/desktop_shell.dart';
import 'src/core/app_state.dart';
import 'src/core/theme_provider.dart';
import 'src/animations/animations.dart';
import 'src/services/prefs_service.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Restore persisted user preferences before the first frame so the
  // desktop appears exactly as the user left it (theme, wallpaper,
  // volume, pinned dock items, ...). Storage failures degrade to
  // defaults instead of blocking boot.
  await PrefsService.instance.init();
  final themeProvider = ThemeProvider()..restore();
  final appState = AppState()..restore();

  runApp(UmerOSApp(themeProvider: themeProvider, appState: appState));
}

class UmerOSApp extends StatelessWidget {
  final ThemeProvider themeProvider;
  final AppState appState;

  const UmerOSApp({
    super.key,
    required this.themeProvider,
    required this.appState,
  });

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider.value(value: themeProvider),
        ChangeNotifierProvider.value(value: appState),
      ],
      child: Consumer<ThemeProvider>(
        builder: (context, theme, _) {
          final fontBase = GoogleFonts.interTextTheme();

          return MaterialApp(
            title: 'UmerOS',
            debugShowCheckedModeBanner: false,
            theme: FlexThemeData.light(
              scheme: theme.flexScheme,
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
              scheme: theme.flexScheme,
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
            themeMode: theme.themeMode,
            // Wrap the desktop shell in a fade-in so the first paint
            // doesn't pop in jarringly. This is a soft entrance
            // (300 ms) that respects the user's "I want my desktop
            // NOW" expectation while still feeling animated.
            home: FadeInOnMount(
              duration: UmerDurations.medium2,
              child: DesktopShell(),
            ),
          );
        },
      ),
    );
  }
}
