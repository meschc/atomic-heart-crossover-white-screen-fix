# Atomic Heart на Mac: белый экран вместо видео в CrossOver — фикс

**Atomic Heart white screen instead of videos and cutscenes on Mac (CrossOver, Apple Silicon) — fix.** [English version below ↓](#english)

Играете в Atomic Heart (Атомик Харт) на Mac через CrossOver, и вместо роликов и катсцен белый прямоугольник, хотя звук идёт? Файлы игры целы, настройки графики тут ни при чём. Это ошибка в самом CrossOver. Исправляется за пару минут: скрипт меняет 4 байта в одном файле CrossOver, `winegstreamer.dll`.

Проверено: CrossOver 26.2, macOS 26, MacBook Pro M1 Pro, Atomic Heart из Steam вместе с DLC «Инстинкт истребления». На других Mac с Apple Silicon (M1, M2, M3, M4) и тем же CrossOver всё должно работать так же, но проверяли только на M1 Pro.

## Это ваша проблема?

Да, если в Atomic Heart на Mac белым экраном заменяются:

- анимация на экране смерти;
- ролики-превью на экране способностей (Шок, Телекинез и другие);
- вступительный ролик DLC «Инстинкт истребления»;
- финальный ролик после битвы с Близняшками;
- мультфильмы «Ну, погоди!»;
- телевизоры и голограммы внутри игры.

При этом **звук у роликов есть**, а заставка при запуске игры показывается нормально.

## Способ 1. Скрипт (проще всего)

1. Закройте игру и CrossOver: CrossOver в Dock → ⌘Q.
2. Скачайте этот репозиторий: зелёная кнопка **Code** вверху страницы → **Download ZIP**. Safari сам распаковывает архив в папку «Загрузки». Если там лежит файл `.zip`, дважды щёлкните по нему, и появится папка.
3. Откройте **Терминал**: ⌘ + Пробел, наберите «Терминал», Enter.
4. Наберите в Терминале `python3` и пробел. Перетащите в окно Терминала файл `patch_winegstreamer.py` из скачанной папки. Допишите пробел и `apply`, нажмите Enter. Строка будет выглядеть примерно так:

   ```
   python3 /Users/вы/Downloads/atomic-heart-crossover-white-screen-fix-main/patch_winegstreamer.py apply
   ```

   Если macOS предложит установить «инструменты командной строки» (Command Line Tools), соглашайтесь. Дождитесь конца установки и выполните команду ещё раз.
5. В конце должно быть написано `Готово (apply)`, а у всех четырёх правок — `пропатчен`. Если написано `Уже в нужном состоянии`, фикс уже стоит.
6. Запустите игру и проверьте любой ролик, например экран способностей.

Другие команды. Везде это та же строка, меняется только последнее слово:

| Команда | Что делает |
|---|---|
| `python3 …/patch_winegstreamer.py` | Только проверяет и ничего не меняет. Показывает, пропатчен ли CrossOver. |
| `python3 …/patch_winegstreamer.py apply` | Ставит фикс. Перед этим сохраняет оригинал в папку `backups` рядом со скриптом. |
| `python3 …/patch_winegstreamer.py restore` | Возвращает всё как было. |

### Если написано «Нет прав на запись»

macOS не даёт Терминалу менять файлы внутри других программ. Откройте **Системные настройки → Конфиденциальность и безопасность → Управление приложениями** и включите **Терминал**. Закройте Терминал (⌘Q), откройте его снова и повторите команду.

### Если написано «Ошибка: … найдено 0»

У вас другая версия CrossOver, и нужный код в ней поменялся. Скрипт в таком случае **ничего не меняет**. Возможно, CodeWeavers уже исправили ошибку сами: проверьте видео в игре.

### Если написано «Ошибка: не нашёл …»

CrossOver лежит не в папке «Программы». Перенесите его туда или допишите в конец команды пробел, `--app`, ещё пробел и перетащите в Терминал сам CrossOver.app. Получится примерно так:

```
python3 /Users/вы/Downloads/atomic-heart-crossover-white-screen-fix-main/patch_winegstreamer.py apply --app /Users/вы/Downloads/CrossOver.app
```

## Способ 2. Вручную, без скрипта

Способ подходит **только для CrossOver 26.2**. Для других версий используйте скрипт: он сам находит нужные места.

**Шаг 1. Проверьте версию файла.** Закройте CrossOver, откройте Терминал (как в способе 1), вставьте эти строки (⌘V) и нажмите Enter:

```
DLL="/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/lib/wine/x86_64-windows/winegstreamer.dll"
shasum -a 256 "$DLL"
```

Первые символы ответа должны быть `1c3b73f59e9f5c14`. Если там что-то другое, **остановитесь**: либо файл уже пропатчен (сравните с шагом 3), либо версия другая, тогда нужен способ 1.

**Шаг 2. Сделайте копию и поменяйте 4 байта.** В том же окне Терминала вставьте и нажмите Enter:

```
cp "$DLL" ~/Desktop/winegstreamer.dll.backup
printf '\xEB' | dd of="$DLL" bs=1 seek=$((0x2bab2)) conv=notrunc
printf '\x00' | dd of="$DLL" bs=1 seek=$((0x33350)) conv=notrunc
printf '\x00' | dd of="$DLL" bs=1 seek=$((0x33374)) conv=notrunc
printf '\x00' | dd of="$DLL" bs=1 seek=$((0xdc8b)) conv=notrunc
```

Первая строка сохранит оригинал на Рабочий стол. Остальные четыре записывают по одному байту. Сообщения вида `1 bytes transferred` — это нормально. Если вместо них `Operation not permitted`, включите Терминал в «Управлении приложениями» (см. выше), закройте Терминал (⌘Q), откройте его снова и начните заново с шага 1.

**Шаг 3. Проверьте результат** в том же окне (вставьте и нажмите Enter):

```
shasum -a 256 "$DLL"
```

Должно получиться `5ada14c57ec5a9b1d56002eb3b6648295f920577cbfb543dd556acc3eca403da`. Если значение другое, верните оригинал командой `cp ~/Desktop/winegstreamer.dll.backup "$DLL"`.

Если вам привычнее hex-редактор (например, Hex Fiend), замените байты по таблице:

| Смещение | Было | Стало | Что это |
|---|---|---|---|
| `0x2bab2` | `75` | `EB` | CrossOver перестаёт прятать формат NV12 на macOS |
| `0x33350` | `01` | `00` | `MF_SA_D3D_AWARE = 0` |
| `0x33374` | `01` | `00` | `MF_SA_D3D11_AWARE = 0` |
| `0xdc8b` | `0F` | `00` | выравнивание кадра 15 → 0 |

## Дополнительно: настройки в Engine.ini (рекомендуется)

Фикс проверяли вместе с этими строками. Сами по себе, без патча, они видео не чинят, но вреда от них нет.

1. Запустите игру хотя бы раз, чтобы она создала свои настройки, и закройте её.
2. В CrossOver выберите бутылку с игрой и нажмите **Open C: Drive**.
3. Откройте папку `users/crossover/AppData/Local/AtomicHeart/Saved/Config/WindowsNoEditor/`.
4. Откройте `Engine.ini` через TextEdit (правый клик → «Открыть в программе» → TextEdit) и допишите в конец:

   ```ini
   [SystemSettings]
   Electra.PC.UseSoftwareDecoding=1

   [ConsoleVariables]
   Electra.PC.UseSoftwareDecoding=1

   [/Script/WmfMediaFactory.WmfMediaSettings]
   HardwareAcceleratedVideoDecoding=False
   ```

   Если раздел `[SystemSettings]` или `[ConsoleVariables]` в файле уже есть, допишите строку внутрь него, а не создавайте второй такой же.
5. Сохраните файл (⌘S).

## Что важно знать

- **После обновления CrossOver фикс пропадает**, и видео снова станут белыми. Просто повторите способ 1.
- Фикс действует на **все бутылки CrossOver**, а не только на Atomic Heart. Если в другой игре видео вдруг испортятся, верните всё командой `restore`.
- Фикс нарушает цифровую подпись CrossOver.app. На 26.2 CrossOver после этого запускается как обычно.
- Меняется только 64-битный `winegstreamer.dll`. 32-битный скрипт не трогает.
- Фикс только для CrossOver. У Whisky, GameHub и других программ свои сборки Wine, для них он не подходит.
- Скрипт ничего не скачивает и не устанавливает. Он меняет ровно 4 байта и прежде сохраняет оригинал. Если хоть одно место нашлось не так, как ожидалось, он не меняет ничего.

## Как вернуть всё как было

Любой из вариантов:

- `python3 …/patch_winegstreamer.py restore`;
- вернуть свою копию с Рабочего стола (для способа 2):

  ```
  cp ~/Desktop/winegstreamer.dll.backup "/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/lib/wine/x86_64-windows/winegstreamer.dll"
  ```

- переустановить или обновить CrossOver.

## Почему видео белые

Внутриигровые ролики Atomic Heart играет плеер Unreal Engine 4.27 (ElectraPlayer) через Media Foundation, а CrossOver декодирует H.264 своим `winegstreamer`. Сходятся три проблемы:

1. **CrossOver прячет NV12 на macOS.** В `winegstreamer` есть хак: если система — Darwin, декодер H.264 не предлагает выходной формат NV12, а плеер игры ждёт именно его.
2. **Кадр не влезает в буфер.** Декодер выравнивает плоскости кадра (`output_plane_align = 15`). Из-за этого кадр 1920×1080 становится 1920×1088, то есть 3 133 440 байт. Игра выделяет буфер ровно под 1920×1080, это 3 110 400 байт. Декодер пишет `Output buffer is too small`, возвращает `STATUS_BUFFER_TOO_SMALL` (в логе видно как `0xD0000023`) и останавливается. Текстура остаётся белой, а звук идёт отдельным потоком и играет дальше.
3. **Лишняя D3D-совместимость.** Декодер объявляет себя D3D-aware, и игра может пытаться получать кадры сразу в видеотекстурах. Эти флаги выключены по примеру MacGameVideoFix и winevideo, чтобы кадры шли через обычную память. Без этой правки фикс отдельно не проверяли.

Скрипт не привязан к смещениям. Каждое место он находит по шаблону байт и проверяет смысл:

- переход стоит прямо перед сравнением с GUID NV12, в функции, где упоминается строка `Darwin`;
- флаги — это именно GUID `MF_SA_D3D_AWARE` и `MF_SA_D3D11_AWARE`;
- выравнивание стоит в функции, которая создаёт декодер H.264.

Поэтому при мелких обновлениях CrossOver он продолжит работать, а при крупных честно откажется.

## Другие игры

Та же ошибка может давать белые видео и в других играх на Unreal Engine 4 под CrossOver, но проверено только на Atomic Heart. Для игр на Unreal Engine 5 с роликами VP9 есть отдельный проект: [MacGameVideoFix](https://github.com/MathiasKowoll/MacGameVideoFix).

## Как нашли решение

Путь от «видео белые» до четырёх байт описан в [STORY.md](STORY.md).

## Спасибо

- [MathiasKowoll/MacGameVideoFix](https://github.com/MathiasKowoll/MacGameVideoFix) и [Jfishin/winevideo](https://github.com/Jfishin/winevideo). Их разборы похожих проблем с видео под Wine на Mac помогли найти хак с NV12 и флаги D3D-aware. Код здесь свой, их файлы не используются.

## Лицензия

[MIT](LICENSE). Скрипт меняет файл CrossOver на вашем Mac. Используйте на свой риск; оригинал он сохраняет.

---

## English

**Atomic Heart shows a white screen instead of videos and cutscenes on Mac under CrossOver, while the audio keeps playing.** This repo fixes it by patching 4 bytes in CrossOver's `winegstreamer.dll`.

Tested on CrossOver 26.2, macOS 26, MacBook Pro M1 Pro, Atomic Heart (Steam) with the Annihilation Instinct DLC.

### Symptoms

White rectangle instead of video, audio plays fine:

- death screen animation;
- ability preview videos in the upgrade menu;
- Annihilation Instinct DLC intro;
- ending cutscene after the Twins fight;
- "Well, Just You Wait!" (Nu, pogodi!) cartoons;
- in-game TVs and holograms.

The launch intro video plays fine.

### Fix with the script

1. Quit the game and CrossOver (⌘Q).
2. Download this repo: **Code → Download ZIP**.
3. Open **Terminal**. Type `python3 `, drag `patch_winegstreamer.py` into the window, add ` apply`, press Enter. If macOS offers to install the command line developer tools, accept, wait for the install to finish, then run the command again.
4. You should see `Готово (apply)` ("done"), with all four sites reported as `пропатчен` ("patched"). `исходный` means "original". `Уже в нужном состоянии` means the fix is already in place.

Run it without arguments to only check the state, or with `restore` to undo. The original DLL is backed up to `backups/` next to the script.

If it prints `Нет прав на запись` ("no write permission"), macOS is blocking Terminal from modifying other apps. Enable Terminal in **System Settings → Privacy & Security → App Management**, quit Terminal (⌘Q), reopen it and run the command again.

If it prints `Ошибка: … найдено 0` ("error: … found 0"), your CrossOver version differs and the script changed nothing. CodeWeavers may have fixed the bug already, so check the videos first.

If it prints `Ошибка: не нашёл …` ("not found"), CrossOver is not in /Applications. Move it there, or append `--app /path/to/CrossOver.app` to the command (you can drag CrossOver.app into Terminal to get the path).

### Manual fix (CrossOver 26.2 only)

For other versions use the script: it locates the sites itself.

**Step 1. Check the file.** Quit CrossOver, open Terminal, paste these lines and press Enter:

```
DLL="/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/lib/wine/x86_64-windows/winegstreamer.dll"
shasum -a 256 "$DLL"
```

Continue only if the hash starts with `1c3b73f59e9f5c14`. Anything else means the file is already patched (compare with step 3) or your version differs, so use the script.

**Step 2. Back up and change 4 bytes.** In the same Terminal window, paste and press Enter:

```
cp "$DLL" ~/Desktop/winegstreamer.dll.backup
printf '\xEB' | dd of="$DLL" bs=1 seek=$((0x2bab2)) conv=notrunc
printf '\x00' | dd of="$DLL" bs=1 seek=$((0x33350)) conv=notrunc
printf '\x00' | dd of="$DLL" bs=1 seek=$((0x33374)) conv=notrunc
printf '\x00' | dd of="$DLL" bs=1 seek=$((0xdc8b)) conv=notrunc
```

The first line saves the original to your Desktop. `1 bytes transferred` messages are expected. If you see `Operation not permitted`, enable Terminal in **App Management** (see above), quit Terminal (⌘Q), reopen it and start again from step 1.

**Step 3. Verify** in the same window:

```
shasum -a 256 "$DLL"
```

It must be `5ada14c57ec5a9b1d56002eb3b6648295f920577cbfb543dd556acc3eca403da`. If it differs, or to undo the fix later, restore the backup:

```
cp ~/Desktop/winegstreamer.dll.backup "/Applications/CrossOver.app/Contents/SharedSupport/CrossOver/lib/wine/x86_64-windows/winegstreamer.dll"
```

With a hex editor, the same change is: `0x2bab2` `75`→`EB`, `0x33350` `01`→`00`, `0x33374` `01`→`00`, `0xdc8b` `0F`→`00`.

### Recommended Engine.ini lines

The fix was tested together with these lines appended to `drive_c/users/crossover/AppData/Local/AtomicHeart/Saved/Config/WindowsNoEditor/Engine.ini` inside the bottle. To get there, use **Open C: Drive** in CrossOver.

```ini
[SystemSettings]
Electra.PC.UseSoftwareDecoding=1

[ConsoleVariables]
Electra.PC.UseSoftwareDecoding=1

[/Script/WmfMediaFactory.WmfMediaSettings]
HardwareAcceleratedVideoDecoding=False
```

### Good to know

- A CrossOver update overwrites the file, so re-run the script after updating.
- The patch applies to all bottles. If videos break in another game, run `restore`.
- It breaks the CrossOver.app bundle signature. CrossOver 26.2 still launches normally.
- Only the 64-bit DLL is patched.
- CrossOver only. Whisky, GameHub and other wrappers ship their own Wine builds.

### Root cause (for Wine/CrossOver developers)

In-game videos go through UE 4.27 ElectraPlayer → Media Foundation → winegstreamer's H.264 decoder.

1. CrossOver's H.264 decoder skips the NV12 output type when `uname` reports `Darwin` (`CW HACK 26265` in CrossOver's Wine source; trace: `Skipping NV12 output format`). Electra requires NV12. Patch: `jne` → `jmp`.
2. `h264_decoder_create` sets `output_plane_align = 15`, so 1920×1080 NV12 is padded to 1920×1088 (3,133,440 bytes). Electra supplies tightly packed 1920×1080 samples (3,110,400 bytes). The unix side logs `Output buffer is too small` and returns `STATUS_BUFFER_TOO_SMALL` (logged as HRESULT `0xD0000023`), and Electra stops the video decoder while audio continues. Patch: alignment `15` → `0`.
3. `video_decoder_create_with_types` sets `MF_SA_D3D_AWARE` and `MF_SA_D3D11_AWARE` to 1, which may steer Electra to a D3D texture path. Patch: both set to `0`, so frames use system-memory buffers. This follows MacGameVideoFix and winevideo; the fix was not tested without this change.

The script locates each site by byte pattern plus semantic checks: NV12 GUID and `Darwin` string references, the AWARE attribute GUIDs, and a call to the decoder constructor. It refuses to change anything unless each site matches exactly once.

Credits: [MacGameVideoFix](https://github.com/MathiasKowoll/MacGameVideoFix) and [winevideo](https://github.com/Jfishin/winevideo) analyse related video issues under Wine on macOS. No code from them is used here.

How the fix was found (in Russian): [STORY.md](STORY.md).
