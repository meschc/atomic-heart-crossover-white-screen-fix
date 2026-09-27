#!/usr/bin/env python3
"""Патч winegstreamer.dll в CrossOver: белые экраны вместо видео в UE4-играх.

Три правки в 64-битном winegstreamer.dll (декодер H.264 из Media Foundation):
  1. nv12  - не прятать выходной формат NV12 на macOS (хак CrossOver "Darwin");
  2. aware - MF_SA_D3D_AWARE / MF_SA_D3D11_AWARE = 0, чтобы игра брала путь
             с буферами в памяти, а не D3D-текстуры;
  3. align - output_plane_align 15 -> 0: без него 1920x1080 выравнивается до
             1920x1088, кадр не влезает в буфер игры, декодер падает
             (STATUS_BUFFER_TOO_SMALL), и видео остаётся белым.

Места ищутся по смыслу (шаблон байт + проверка, куда ссылается инструкция),
а не по жёстким смещениям, поэтому скрипт переживает мелкие обновления.
Если что-то не нашлось однозначно, скрипт ничего не трогает.

Использование:
  python3 patch_winegstreamer.py            # проверить состояние
  python3 patch_winegstreamer.py apply      # пропатчить (с бэкапом)
  python3 patch_winegstreamer.py restore    # вернуть исходные байты
  --app /путь/к/CrossOver.app               # если CrossOver лежит не в /Applications
"""
import argparse
import hashlib
import os
import plistlib
import re
import shlex
import shutil
import struct
import subprocess
import sys
import uuid
from collections import namedtuple

DEFAULT_APP = '/Applications/CrossOver.app'
DLL_REL = 'Contents/SharedSupport/CrossOver/lib/wine/x86_64-windows/winegstreamer.dll'
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'backups')

NV12_PREFIX = b'NV12\x00\x00\x10\x00'  # первые 8 байт GUID MFVideoFormat_NV12
DARWIN = b'Darwin\x00'
MF_SA_D3D_AWARE = uuid.UUID('eaa35c29-775e-488e-9b61-b3283e49583b').bytes_le
MF_SA_D3D11_AWARE = uuid.UUID('206b4fc8-fcf9-4c51-afe3-9764369e33a0').bytes_le

MAX_AWARE_PAIR_GAP = 64      # байт между SetUINT32(D3D_AWARE) и SetUINT32(D3D11_AWARE)
MAX_ALIGN_TO_FLAG_GAP = 32   # байт между plane_align=15 и allow_format_change=1
PLANE_ALIGN_ORIG = 0x0F

# Одна правка = один байт: смещение в файле, исходное и новое значение.
Site = namedtuple('Site', 'name offset original patched')


class PatchError(Exception):
    pass


class PeImage:
    """Минимальный разбор PE32+: секции, .pdata, чтение по RVA."""

    def __init__(self, data):
        self.data = data
        pe = struct.unpack_from('<I', data, 0x3C)[0]
        if data[pe:pe + 4] != b'PE\x00\x00':
            raise PatchError('это не PE-файл')
        nsec = struct.unpack_from('<H', data, pe + 6)[0]
        opt_size = struct.unpack_from('<H', data, pe + 20)[0]
        opt = pe + 24
        if struct.unpack_from('<H', data, opt)[0] != 0x20B:
            raise PatchError('ожидался 64-битный PE32+')
        self.sections = []
        for i in range(nsec):
            s = opt + opt_size + 40 * i
            vsize, va, rsize, raw = struct.unpack_from('<IIII', data, s + 8)
            self.sections.append((va, max(vsize, rsize), raw, rsize))
        exc_rva, exc_size = struct.unpack_from('<II', data, opt + 112 + 8 * 3)
        exc_off = self.rva_to_off(exc_rva)
        if exc_off is None:
            raise PatchError('в файле нет таблицы функций (.pdata)')
        self.functions = [struct.unpack_from('<II', data, exc_off + 12 * i)
                          for i in range(exc_size // 12)]

    def rva_to_off(self, rva):
        for va, size, raw, rsize in self.sections:
            if va <= rva < va + size and rva - va < rsize:
                return rva - va + raw
        return None

    def off_to_rva(self, off):
        for va, _size, raw, rsize in self.sections:
            if raw <= off < raw + rsize:
                return off - raw + va
        return None

    def read_rva(self, rva, length):
        off = None if rva is None else self.rva_to_off(rva)
        return b'' if off is None else self.data[off:off + length]

    def rip_target(self, next_insn_off, disp_off):
        """Куда указывает [rip+disp32]: RVA следующей инструкции + disp."""
        disp = struct.unpack_from('<i', self.data, disp_off)[0]
        rva = self.off_to_rva(next_insn_off)
        return None if rva is None else rva + disp

    def function_of(self, off):
        rva = self.off_to_rva(off)
        if rva is None:
            return None
        for begin, end in self.functions:
            if begin <= rva < end:
                return begin, end
        return None

    def function_bytes(self, func):
        begin, end = func
        start = self.rva_to_off(begin)
        return start, self.data[start:start + (end - begin)]


def references_string(pe, func, needle):
    """Есть ли в функции lea reg,[rip+X], где X указывает на строку needle."""
    start, code = pe.function_bytes(func)
    lea = re.compile(rb'[\x48\x4c]\x8d[\x05\x0d\x15\x1d\x25\x2d\x35\x3d]', re.S)
    for m in lea.finditer(code):
        insn = start + m.start()
        target = pe.rip_target(insn + 7, insn + 3)
        if pe.read_rva(target, len(needle)) == needle:
            return True
    return False


def calls_function(pe, func, callee_rva):
    """Есть ли в функции прямой call rel32 на callee_rva."""
    start, code = pe.function_bytes(func)
    for i in range(len(code) - 4):
        if code[i] != 0xE8:
            continue
        target = pe.off_to_rva(start + i + 5) + struct.unpack_from('<i', code, i + 1)[0]
        if target == callee_rva:
            return True
    return False


def find_nv12_site(pe):
    """jne перед сравнением с NV12 внутри хака "if Darwin: skip NV12"."""
    pattern = re.compile(rb'[\x75\xEB][\s\S]\x48\x8b\x05[\s\S]{4}\x48\x39\x02', re.S)
    hits = []
    for m in pattern.finditer(pe.data):
        mov = m.start() + 2
        if pe.read_rva(pe.rip_target(mov + 7, mov + 3), 8) != NV12_PREFIX:
            continue
        func = pe.function_of(m.start())
        if func and references_string(pe, func, DARWIN):
            hits.append(m.start())
    if len(hits) != 1:
        raise PatchError(f'nv12: ожидалось 1 место, найдено {len(hits)}')
    return Site('nv12', hits[0], 0x75, 0xEB)


def aware_setters(pe):
    """Все mov r8d,0/1 + lea rdx,[GUID] для D3D_AWARE/D3D11_AWARE."""
    pattern = re.compile(rb'\x41\xb8[\x00\x01]\x00\x00\x00\x48\x8d\x15[\s\S]{4}', re.S)
    found = []
    for m in pattern.finditer(pe.data):
        lea = m.start() + 6
        guid = pe.read_rva(pe.rip_target(lea + 7, lea + 3), 16)
        if guid == MF_SA_D3D_AWARE:
            found.append(('d3d', m.start() + 2))
        elif guid == MF_SA_D3D11_AWARE:
            found.append(('d3d11', m.start() + 2))
    return found


def find_aware_sites(pe):
    """Пара D3D_AWARE -> D3D11_AWARE подряд: это video_decoder_create_with_types.
    (В video processor порядок обратный, его не трогаем.)"""
    setters = aware_setters(pe)
    pairs = [(a[1], b[1]) for a, b in zip(setters, setters[1:])
             if a[0] == 'd3d' and b[0] == 'd3d11'
             and b[1] - a[1] <= MAX_AWARE_PAIR_GAP
             and pe.function_of(a[1]) == pe.function_of(b[1])]
    if len(pairs) != 1:
        raise PatchError(f'aware: ожидалась 1 пара D3D/D3D11, найдено {len(pairs)}')
    d3d, d3d11 = pairs[0]
    func = pe.function_of(d3d)
    return [Site('aware_d3d', d3d, 0x01, 0x00),
            Site('aware_d3d11', d3d11, 0x01, 0x00)], func


def find_align_site(pe, decoder_func):
    """mov dword [reg+X], 15 и рядом mov dword [reg+X+8], 1 в функции,
    которая вызывает video_decoder_create_with_types (h264_decoder_create)."""
    pattern = re.compile(rb'\xc7([\x80-\x87])([\s\S]{4})([\x0f\x00])\x00\x00\x00', re.S)
    hits = []
    for m in pattern.finditer(pe.data):
        disp = struct.unpack('<I', m.group(2))[0]
        flag = b'\xc7' + m.group(1) + struct.pack('<I', disp + 8) + b'\x01\x00\x00\x00'
        if flag not in pe.data[m.end():m.end() + MAX_ALIGN_TO_FLAG_GAP]:
            continue
        func = pe.function_of(m.start())
        if func and calls_function(pe, func, decoder_func[0]):
            hits.append(m.start() + 6)
    if len(hits) != 1:
        raise PatchError(f'align: ожидалось 1 место, найдено {len(hits)}')
    return Site('align', hits[0], PLANE_ALIGN_ORIG, 0x00)


def locate_sites(data):
    try:
        pe = PeImage(data)
    except struct.error:
        raise PatchError('файл обрезан или повреждён')
    aware, decoder_func = find_aware_sites(pe)
    return [find_nv12_site(pe)] + aware + [find_align_site(pe, decoder_func)]


def site_state(data, site):
    value = data[site.offset]
    if value == site.original:
        return 'исходный'
    if value == site.patched:
        return 'пропатчен'
    return f'неизвестно ({value:#04x})'


def crossover_version(app):
    try:
        with open(os.path.join(app, 'Contents/Info.plist'), 'rb') as f:
            return plistlib.load(f).get('CFBundleShortVersionString', '?')
    except (OSError, plistlib.InvalidFileException):
        return '?'


def wine_is_running():
    try:
        result = subprocess.run(['pgrep', '-f', 'bin/wineserver'], capture_output=True)
    except OSError:
        return False
    return result.returncode == 0


def write_atomically(path, data):
    """Пишем рядом и переименовываем: безопасно, даже если DLL сейчас загружена."""
    tmp = path + '.new'
    try:
        with open(tmp, 'wb') as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        shutil.copymode(path, tmp)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def backup_original(path, data):
    os.makedirs(BACKUP_DIR, exist_ok=True)
    digest = hashlib.sha256(data).hexdigest()[:12]
    dst = os.path.join(BACKUP_DIR, f'winegstreamer.dll.{digest}.orig')
    if not os.path.exists(dst):
        shutil.copy2(path, dst)
    return dst


def report(data, sites):
    for site in sites:
        print(f'  {site.name:12} смещение {site.offset:#08x}: {site_state(data, site)}')


def run(mode, app):
    path = os.path.join(app, DLL_REL)
    if not os.path.isfile(path):
        raise PatchError(f'не нашёл {path}')
    with open(path, 'rb') as f:
        data = f.read()
    print(f'CrossOver {crossover_version(app)}: {path}')
    print(f'sha256 {hashlib.sha256(data).hexdigest()}')
    sites = locate_sites(data)
    report(data, sites)
    if mode == 'check':
        return
    states = {site_state(data, s) for s in sites}
    if any(s.startswith('неизвестно') for s in states):
        raise PatchError('в каком-то месте неожиданный байт, ничего не меняю')
    target = 'patched' if mode == 'apply' else 'original'
    new = bytearray(data)
    for site in sites:
        new[site.offset] = getattr(site, target)
    if bytes(new) == data:
        print('Уже в нужном состоянии, ничего не меняю.')
        return
    if mode == 'apply':
        print(f'Бэкап: {backup_original(path, data)}')
    write_atomically(path, bytes(new))
    print(f'Готово ({mode}). sha256 {hashlib.sha256(new).hexdigest()}')
    report(new, sites)
    if wine_is_running():
        print('Wine сейчас запущен: изменения подхватятся при следующем запуске игры.')


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('mode', nargs='?', default='check', choices=['check', 'apply', 'restore'])
    parser.add_argument('--app', default=DEFAULT_APP, help='путь к CrossOver.app')
    args = parser.parse_args()
    try:
        run(args.mode, args.app)
    except PatchError as e:
        sys.exit(f'Ошибка: {e}')
    except PermissionError as e:
        # Чаще всего это не права на файл, а защита macOS «Управление приложениями»:
        # без неё Терминалу нельзя менять файлы внутри чужого .app, и sudo не поможет.
        sys.exit(f'Нет прав на запись ({e}).\n'
                 'Разрешите Терминалу менять программы: Системные настройки → '
                 'Конфиденциальность и безопасность → Управление приложениями → '
                 'включите Терминал, перезапустите его и повторите команду.\n'
                 f'Если не поможет: sudo python3 {shlex.join(sys.argv)}')
    except OSError as e:
        sys.exit(f'Ошибка файловой системы: {e}. Файл CrossOver не изменён.')


if __name__ == '__main__':
    main()
