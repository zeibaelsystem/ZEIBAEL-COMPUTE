"""Reviewed public standard GitHub runner capacity and FREE-ONLY routing.

Capacity evidence: https://docs.github.com/en/actions/reference/runners/github-hosted-runners
Only known smoke-tested runtime/platform combinations are auto-selected.
Spec numbers are minimum advertised resources, not guaranteed free resources forever.
"""
from scripts.runtime_router import select_runner

RUNNER_SPECS = {
    "ubuntu-24.04": {"os": "linux", "arch": "x64", "cpu": 4, "memory_gb": 16},
    "ubuntu-24.04-arm": {"os": "linux", "arch": "arm64", "cpu": 4, "memory_gb": 16},
    "windows-2022": {"os": "windows", "arch": "x64", "cpu": 4, "memory_gb": 16},
    "windows-11-arm": {"os": "windows", "arch": "arm64", "cpu": 4, "memory_gb": 16},
    "macos-15-intel": {"os": "macos", "arch": "x64", "cpu": 4, "memory_gb": 14},
    "macos-15": {"os": "macos", "arch": "arm64", "cpu": 3, "memory_gb": 7},
    "ubuntu-slim": {"os": "linux", "arch": "x64", "cpu": 1, "memory_gb": 5},
}
# Only already verified core language toolchains; new language combinations
# are provided by scripts.job_plan.NEW_RUNTIME_RUNNERS.
CORE_VERIFIED = {
    "python": set(RUNNER_SPECS),
    "node": {"ubuntu-24.04"},
    "go": {"ubuntu-24.04"},
    "rust": {"ubuntu-24.04"},
    "java": {"ubuntu-24.04"},
    "docker": {"ubuntu-24.04"},
}
TOOLCHAINS = {
    "python": {"python", "gcc", "g++"}, "node": {"node", "npm"},
    "go": {"go"}, "rust": {"rustc", "cargo"}, "java": {"java", "javac"},
    "docker": {"docker", "docker-compose"}, "php": {"php"},
    "ruby": {"ruby"}, "dotnet": {"dotnet"}, "kotlin": {"kotlinc", "java"},
    "swift": {"swift"}, "powershell": {"pwsh"}, "perl": {"perl"},
    "julia": {"julia"}, "haskell": {"ghc", "runghc"},
    "fortran": {"gfortran"}, "r": {"rscript"}, "scala": {"sbt", "java"},
}
FIELDS = {"os", "arch", "min_cpu", "min_memory_gb", "toolchains", "output_mb"}


def validate_requirements(requirements, output_files=False):
    if not isinstance(requirements, dict) or set(requirements) - FIELDS:
        raise ValueError("Invalid ZEIBAEL resource requirements")
    for key in ("os", "arch"):
        if key in requirements:
            allowed = {"linux", "windows", "macos"} if key == "os" else {"x64", "arm64"}
            if requirements[key] not in allowed:
                raise ValueError("Unsupported ZEIBAEL OS/architecture requirement")
    for key in ("min_cpu", "min_memory_gb", "output_mb"):
        if key in requirements:
            value = requirements[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0 or value != value or value == float("inf"):
                raise ValueError("Invalid ZEIBAEL resource quantity: " + key)
            if key != "output_mb" and value <= 0:
                raise ValueError("Invalid ZEIBAEL resource quantity: " + key)
    if requirements.get("output_mb", 0) > 50:
        raise ValueError("ZEIBAEL internal output budget is 50 MB/job; not a GitHub provider limit")
    if requirements.get("output_mb", 0) > 0 and not output_files:
        raise ValueError("ZEIBAEL output_mb requires reviewed output_files=true")
    tools = requirements.get("toolchains", [])
    if not isinstance(tools, list) or len(tools) > 12 or any(not isinstance(x, str) or not x or x != x.lower() for x in tools):
        raise ValueError("Invalid ZEIBAEL reviewed toolchains requirement")
    if len(set(tools)) != len(tools):
        raise ValueError("Duplicate ZEIBAEL toolchain requirement")


def choose_reviewed_runner(runtime, requirements, approved, timeout_profile, runner=None, output_files=False):
    """Fail closed: never select larger runners, self-hosted, paid image or unsupported tooling."""
    validate_requirements(requirements, output_files=output_files)
    if not set(requirements.get("toolchains", [])).issubset(TOOLCHAINS.get(runtime, set())):
        raise ValueError("Unsupported ZEIBAEL reviewed toolchain; no automatic installation")
    candidates = set(approved) & set(RUNNER_SPECS)
    if runner not in (None, "auto"):
        candidates &= {runner}
    candidates = {r for r in candidates
                  if r != "ubuntu-slim" or (runtime == "python" and timeout_profile == "short")}
    def eligible(name):
        spec = RUNNER_SPECS[name]
        return (("os" not in requirements or spec["os"] == requirements["os"])
                and ("arch" not in requirements or spec["arch"] == requirements["arch"])
                and spec["cpu"] >= requirements.get("min_cpu", 0)
                and spec["memory_gb"] >= requirements.get("min_memory_gb", 0))
    candidates = {name for name in candidates if eligible(name)}
    if not candidates:
        raise ValueError("ZEIBAEL FREE-ONLY standard runner insufficient or internally unverified; no paid fallback")
    default = select_runner(runtime)
    # Preserve legacy defaults unless requirements force another reviewed runner.
    return sorted(candidates, key=lambda r: (r != default,
                                            -RUNNER_SPECS[r]["cpu"],
                                            -RUNNER_SPECS[r]["memory_gb"], r))[0]
