from distutils.core import setup
import py2exe
import glob

setup(
    windows= [
        {
            "script": "microdrop/microdrop.py", # Main Python script    
            "icon_resources": [(0, "microdrop.ico")] # Icon to embed into the PE file.
        }
    ],
    # compressed and optimize reduce the size
    options = {"py2exe": {
        "compressed": 1,
        "optimize": 2,
        "includes": ['atk','gtk','gobject','cairo','gio','pango',
                    'pangocairo'],
        "excludes": ['_gtkagg', '_tkagg', 'bsddb', 'curses', 'email',
            'pywin.debugger','pywin.debugger.dbgcon', 'pywin.dialogs',
            'tcl', 'Tkconstants', 'Tkinter'],
        "packages": ["microdrop/hardware.dmf_control_board", "glib._glib"],
        "dll_excludes": ["API-MS-Win-Core-Debug-L1-1-0.dll",
            "API-MS-Win-Core-DelayLoad-L1-1-0.dll",
            "API-MS-Win-Core-ErrorHandling-L1-1-0.dll",
            "API-MS-Win-Core-File-L1-1-0.dll",
            "API-MS-Win-Core-Handle-L1-1-0.dll",
            "API-MS-Win-Core-Heap-L1-1-0.dll",
            "API-MS-Win-Core-IO-L1-1-0.dll",
            "API-MS-Win-Core-Interlocked-L1-1-0.dll",
            "API-MS-Win-Core-LibraryLoader-L1-1-0.dll",
            "API-MS-Win-Core-LocalRegistry-L1-1-0.dll",
            "API-MS-Win-Core-Localization-L1-1-0.dll",
            "API-MS-Win-Core-Misc-L1-1-0.dll",
            "API-MS-Win-Core-ProcessEnvironment-L1-1-0.dll",
            "API-MS-Win-Core-ProcessThreads-L1-1-0.dll",
            "API-MS-Win-Core-Profile-L1-1-0.dll",
            "API-MS-Win-Core-String-L1-1-0.dll",
            "API-MS-Win-Core-Synch-L1-1-0.dll",
            "API-MS-Win-Core-SysInfo-L1-1-0.dll",
            "DNSAPI.DLL",
            "MSIMG32.DLL",
            "NSI.dll",
            "USP10.DLL"],
        "bundle_files": 3,
        "dist_dir": "microdrop",
        "xref": False,
        "skip_archive": False,
        "ascii": False,
        "custom_boot_script": "",
        }
    },
    data_files=[("microdrop/gui/glade", glob.glob("microdrop/gui/glade/*.*"))]
)

