"""Deterministic FREE-ONLY runner choices for previously reviewed public jobs.

This is not a natural-language execution endpoint. Grace must commit and review
a manifest; no arbitrary text can dispatch commands or install toolchains.
"""
# Priority-ordered runners for each ZEIBAEL runtime. Only first is auto-selected;
# explicit runner choices remain validated by job_plan.py.
BUILTIN_RUNNERS = {
    "python": ("ubuntu-24.04",),
    "node": ("ubuntu-24.04",),
    "go": ("ubuntu-24.04",),
    "rust": ("ubuntu-24.04",),
    "java": ("ubuntu-24.04",),
    "docker": ("ubuntu-24.04",),
    "php": ("ubuntu-24.04",),
    "ruby": ("ubuntu-24.04",),
    "dotnet": ("ubuntu-24.04",),
    "kotlin": ("ubuntu-24.04",),
    "swift": ("ubuntu-24.04",),
    "powershell": ("ubuntu-24.04",),
    "perl": ("ubuntu-24.04",),
    "julia": ("ubuntu-24.04",),
    "haskell": ("ubuntu-24.04",),
    "fortran": ("ubuntu-24.04",),
    "r": ("windows-2022",),
    "scala": ("windows-2022",),
}

ALIASES = {
    "pwsh": "powershell", "powershell": "powershell",
    "perl": "perl", "julia": "julia",
    "haskell": "haskell", "ghc": "haskell",
    "fortran": "fortran", "gfortran": "fortran",
    "r": "r", "r language": "r", "rscript": "r",
    "scala": "scala",
    "javascript": "node", "js": "node", "typescript": "node", "ts": "node",
    "c#": "dotnet", "csharp": "dotnet", ".net": "dotnet",
    "c": "python", "c++": "python", "cpp": "python",
    "bash": "python", "shell": "python",
}

def resolve_language(language):
    if not isinstance(language, str) or not language.strip():
        raise ValueError("Language must be a nonempty supported name")
    name = " ".join(language.strip().lower().split())
    runtime = ALIASES.get(name, name)
    if runtime not in BUILTIN_RUNNERS:
        raise ValueError("Unsupported language; ZEIBAEL has no reviewed runtime (not a GitHub provider limit)")
    return runtime

def select_runner(runtime):
    if runtime not in BUILTIN_RUNNERS:
        raise ValueError("Unsupported runtime in ZEIBAEL internal router")
    return BUILTIN_RUNNERS[runtime][0]
