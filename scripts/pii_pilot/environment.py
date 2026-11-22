"""Report kernel-enforced limits instead of treating a host CPU count as a quota."""

import os
from pathlib import Path
import platform


def environment():
    result = {"os": platform.system(), "machine": platform.machine(),
              "python": platform.python_version(), "host_cpus": os.cpu_count(),
              "cpu_quota_cores": None, "memory_limit_bytes": None,
              "target_2cpu_4gb_measured": False}
    if platform.system() != "Linux":
        return result
    cpu = Path("/sys/fs/cgroup/cpu.max")
    memory = Path("/sys/fs/cgroup/memory.max")
    if cpu.exists() and memory.exists():
        quota, period = cpu.read_text().split()
        limit = memory.read_text().strip()
        result["cpu_quota_cores"] = int(quota) / int(period) if quota != "max" else None
        result["memory_limit_bytes"] = int(limit) if limit != "max" else None
        result["target_2cpu_4gb_measured"] = (result["cpu_quota_cores"] == 2
                                             and result["memory_limit_bytes"] == 4 * 1024 ** 3)
    return result
