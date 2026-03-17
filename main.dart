import 'dart:io';

import 'package:flutter/material.dart';
import 'package:window_manager_plus/window_manager_plus.dart';
import 'package:easy_localization/easy_localization.dart';

import 'HaroControllerApp.dart';

void main(List<String> args) async {
  WidgetsFlutterBinding.ensureInitialized();
  await EasyLocalization.ensureInitialized();

  if (Platform.isWindows || Platform.isLinux || Platform.isMacOS) {
    int windowId = args.isNotEmpty ? int.tryParse(args[0]) ?? 0 : 0;
    await WindowManagerPlus.ensureInitialized(windowId);

    WindowOptions windowOptions = const WindowOptions(
      size: Size(1000, 700),
      minimumSize: Size(800, 600),
      center: true,
      title: "Haro Controller",

      titleBarStyle: TitleBarStyle.hidden,
      backgroundColor: Colors.transparent,
      skipTaskbar: false,
    );

    WindowManagerPlus.current.waitUntilReadyToShow(windowOptions, () async {
      await WindowManagerPlus.current.show();
      await WindowManagerPlus.current.focus();
    });
  }

  runApp(
    EasyLocalization(
      supportedLocales: const [Locale('en'), Locale('zh')],
      path: 'assets/translations',
      fallbackLocale: const Locale('en'),
      startLocale: const Locale('en'),
      child: const HaroControllerApp(),
    ),
  );
}
