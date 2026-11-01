"""Detect the configured game process without reading game memory."""
import os
from pathlib import Path
import sys


def infer_executable(dll):
    dll=Path(dll)
    data=dll.parent.parent
    root=data.parent
    if data.name.endswith('_Data'):
        candidate=root/(data.name[:-5]+'.exe')
        if candidate.is_file():return str(candidate.resolve())
    choices=[p for p in root.glob('*.exe') if not p.name.lower().startswith(('unitycrashhandler','unins'))]
    return str(choices[0].resolve()) if len(choices)==1 else ''


def game_running(executable):
    if not executable:return False
    target=os.path.normcase(os.path.abspath(executable))
    if sys.platform=='win32':
        import ctypes
        from ctypes import wintypes as w
        class ProcessEntry(ctypes.Structure):
            _fields_=[('dwSize',w.DWORD),('cntUsage',w.DWORD),('th32ProcessID',w.DWORD),
                ('th32DefaultHeapID',ctypes.c_size_t),('th32ModuleID',w.DWORD),('cntThreads',w.DWORD),
                ('th32ParentProcessID',w.DWORD),('pcPriClassBase',w.LONG),('dwFlags',w.DWORD),('szExeFile',w.WCHAR*260)]
        k=ctypes.WinDLL('kernel32',use_last_error=True)
        k.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD];k.CreateToolhelp32Snapshot.restype=w.HANDLE
        k.Process32FirstW.argtypes=[w.HANDLE,ctypes.POINTER(ProcessEntry)]
        k.Process32NextW.argtypes=[w.HANDLE,ctypes.POINTER(ProcessEntry)]
        k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
        k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)]
        k.CloseHandle.argtypes=[w.HANDLE]
        snapshot=k.CreateToolhelp32Snapshot(2,0)
        if snapshot==ctypes.c_void_p(-1).value:return False
        try:
            entry=ProcessEntry();entry.dwSize=ctypes.sizeof(entry)
            ok=k.Process32FirstW(snapshot,ctypes.byref(entry))
            while ok:
                if entry.szExeFile.casefold()==Path(executable).name.casefold():
                    process=k.OpenProcess(0x1000,False,entry.th32ProcessID)
                    if process:
                        try:
                            size=w.DWORD(32768);path=ctypes.create_unicode_buffer(32768)
                            if k.QueryFullProcessImageNameW(process,0,path,ctypes.byref(size)) and os.path.normcase(path.value)==target:
                                return True
                        finally:k.CloseHandle(process)
                ok=k.Process32NextW(snapshot,ctypes.byref(entry))
        finally:k.CloseHandle(snapshot)
        return False
    if Path('/proc').is_dir():
        for item in Path('/proc').iterdir():
            if not item.name.isdigit():continue
            try:
                if os.path.normcase(os.readlink(item/'exe'))==target:return True
            except OSError:pass
    return False
