"""Windows Job Object utility for complete process isolation and child lifecycle management.

Ensures that all spawned subprocesses (ffmpeg, AI stage workers, TTS workers) are
automatically terminated at the Windows kernel level if DubStudio exits or is killed.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import os
import subprocess
import sys
from typing import Optional, Union

logger = logging.getLogger(__name__)

# Win32 Constants
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JobObjectExtendedLimitInformation = 9
PROCESS_SET_QUOTA = 0x0100
PROCESS_TERMINATE = 0x0001


class IO_COUNTERS(ctypes.Structure):
    _fields_ = [
        ("ReadOperationCount", ctypes.c_uint64),
        ("WriteOperationCount", ctypes.c_uint64),
        ("OtherOperationCount", ctypes.c_uint64),
        ("ReadTransferCount", ctypes.c_uint64),
        ("WriteTransferCount", ctypes.c_uint64),
        ("OtherTransferCount", ctypes.c_uint64),
    ]


class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("PerProcessUserTimeLimit", ctypes.c_int64),
        ("PerJobUserTimeLimit", ctypes.c_int64),
        ("LimitFlags", wintypes.DWORD),
        ("MinimumWorkingSetSize", ctypes.c_size_t),
        ("MaximumWorkingSetSize", ctypes.c_size_t),
        ("ActiveProcessLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t),
        ("PriorityClass", wintypes.DWORD),
        ("SchedulingClass", wintypes.DWORD),
    ]


class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
        ("IoInfo", IO_COUNTERS),
        ("ProcessMemoryLimit", ctypes.c_size_t),
        ("JobMemoryLimit", ctypes.c_size_t),
        ("PeakProcessMemoryLimit", ctypes.c_size_t),
        ("PeakJobMemoryLimit", ctypes.c_size_t),
    ]


# Module-level handle to prevent garbage collection
_GLOBAL_JOB_HANDLE: Optional[int] = None


def init_job_object() -> Optional[int]:
    """Create a Windows Job Object with KILL_ON_JOB_CLOSE and attach current process.
    
    Returns the job handle, or None if not on Windows or if initialization failed.
    """
    global _GLOBAL_JOB_HANDLE
    if sys.platform != "win32":
        return None

    if _GLOBAL_JOB_HANDLE is not None:
        return _GLOBAL_JOB_HANDLE

    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        kernel32.CreateJobObjectW.restype = wintypes.HANDLE

        kernel32.SetInformationJobObject.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.SetInformationJobObject.restype = wintypes.BOOL

        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL

        kernel32.GetCurrentProcess.restype = wintypes.HANDLE

        h_job = kernel32.CreateJobObjectW(None, None)
        if not h_job:
            err = kernel32.GetLastError()
            logger.warning(f"CreateJobObjectW failed with error code: {err}")
            return None

        info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
        info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE

        ok = kernel32.SetInformationJobObject(
            h_job,
            JobObjectExtendedLimitInformation,
            ctypes.byref(info),
            ctypes.sizeof(info),
        )
        if not ok:
            err = kernel32.GetLastError()
            logger.warning(f"SetInformationJobObject failed with error: {err}")
            kernel32.CloseHandle(h_job)
            return None

        # Assign the current process so child processes automatically inherit the job
        cur_proc = kernel32.GetCurrentProcess()
        res = kernel32.AssignProcessToJobObject(h_job, cur_proc)
        if not res:
            err = kernel32.GetLastError()
            # Error 5 (ACCESS_DENIED) can occur if already in a restricted job, which is fine
            logger.info(f"AssignProcessToJobObject on main process status: {res} (err: {err})")

        _GLOBAL_JOB_HANDLE = h_job
        logger.info(f"Windows Job Object initialized with KILL_ON_JOB_CLOSE (handle: {h_job})")
        return _GLOBAL_JOB_HANDLE
    except Exception as e:
        logger.warning(f"Failed to initialize Windows Job Object: {e}")
        return None


def assign_process_to_job(target: Union[subprocess.Popen, int]) -> bool:
    """Explicitly assign a subprocess or PID to the global Job Object.
    
    Useful for ensuring child processes are tied to the job even if inheritance was skipped.
    """
    if sys.platform != "win32":
        return False

    h_job = init_job_object()
    if not h_job:
        return False

    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE

        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        pid = target.pid if isinstance(target, subprocess.Popen) else int(target)
        proc_handle = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
        if not proc_handle:
            # Fall back to using target._handle if available
            if isinstance(target, subprocess.Popen) and hasattr(target, "_handle") and target._handle:
                proc_handle = target._handle
            else:
                return False

        kernel32.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        kernel32.AssignProcessToJobObject.restype = wintypes.BOOL

        res = kernel32.AssignProcessToJobObject(h_job, proc_handle)
        if proc_handle != getattr(target, "_handle", None):
            kernel32.CloseHandle(proc_handle)

        return bool(res)
    except Exception as e:
        logger.debug(f"assign_process_to_job notice: {e}")
        return False
