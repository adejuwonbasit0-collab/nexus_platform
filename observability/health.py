"""System health checker — returns live system metrics."""
import time
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class HealthCheck:
    status: str          # 'healthy' | 'degraded' | 'unhealthy'
    latency_ms: float = 0
    detail: str = ''
    error: str = ''


@dataclass
class HealthReport:
    database:  HealthCheck = field(default_factory=lambda: HealthCheck('unknown'))
    cache:     HealthCheck = field(default_factory=lambda: HealthCheck('unknown'))
    storage:   HealthCheck = field(default_factory=lambda: HealthCheck('unknown'))
    memory:    HealthCheck = field(default_factory=lambda: HealthCheck('unknown'))
    disk:      HealthCheck = field(default_factory=lambda: HealthCheck('unknown'))

    @property
    def overall(self):
        statuses = [self.database.status, self.cache.status, self.memory.status, self.disk.status]
        if 'unhealthy' in statuses:
            return 'unhealthy'
        if 'degraded' in statuses:
            return 'degraded'
        return 'healthy'


class SystemHealthChecker:
    def get_full_health(self) -> HealthReport:
        return HealthReport(
            database=self._check_database(),
            cache=self._check_cache(),
            storage=self._check_storage(),
            memory=self._check_memory(),
            disk=self._check_disk(),
        )

    def _check_database(self) -> HealthCheck:
        try:
            from django.db import connection
            start = time.time()
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
            ms = (time.time() - start) * 1000
            status = 'healthy' if ms < 100 else 'degraded'
            return HealthCheck(status=status, latency_ms=round(ms, 2),
                               detail=f'Query in {ms:.1f}ms')
        except Exception as e:
            return HealthCheck(status='unhealthy', error=str(e))

    def _check_cache(self) -> HealthCheck:
        try:
            from django.core.cache import cache
            start = time.time()
            cache.set('_health_check', '1', 5)
            val = cache.get('_health_check')
            ms = (time.time() - start) * 1000
            if val == '1':
                return HealthCheck(status='healthy', latency_ms=round(ms, 2))
            return HealthCheck(status='degraded', detail='Cache read/write mismatch')
        except Exception as e:
            return HealthCheck(status='unhealthy', error=str(e))

    def _check_storage(self) -> HealthCheck:
        try:
            from django.conf import settings
            media_root = str(settings.MEDIA_ROOT)
            if not os.path.exists(media_root):
                os.makedirs(media_root, exist_ok=True)
            test_file = os.path.join(media_root, '.health_check')
            with open(test_file, 'w') as f:
                f.write('ok')
            os.remove(test_file)
            return HealthCheck(status='healthy', detail=f'Media root writable: {media_root}')
        except Exception as e:
            return HealthCheck(status='unhealthy', error=str(e))

    def _check_memory(self) -> HealthCheck:
        try:
            import resource
            usage = resource.getrusage(resource.RUSAGE_SELF)
            mem_mb = usage.ru_maxrss / 1024
            status = 'healthy'
            if mem_mb > 800:
                status = 'degraded'
            if mem_mb > 1500:
                status = 'unhealthy'
            return HealthCheck(status=status, detail=f'{mem_mb:.0f} MB RSS')
        except Exception:
            # Try reading /proc/meminfo as fallback
            try:
                with open('/proc/meminfo') as f:
                    lines = f.readlines()
                mem = {}
                for line in lines:
                    parts = line.split()
                    if len(parts) >= 2:
                        mem[parts[0].rstrip(':')] = int(parts[1])
                total  = mem.get('MemTotal', 0) / 1024
                avail  = mem.get('MemAvailable', 0) / 1024
                used   = total - avail
                pct    = (used / total * 100) if total > 0 else 0
                status = 'healthy' if pct < 80 else ('degraded' if pct < 90 else 'unhealthy')
                return HealthCheck(status=status,
                                   detail=f'{used:.0f}MB used / {total:.0f}MB total ({pct:.1f}%)')
            except Exception as e2:
                return HealthCheck(status='unknown', detail='Could not read memory info')

    def _check_disk(self) -> HealthCheck:
        try:
            stat = os.statvfs('/')
            total = stat.f_blocks * stat.f_frsize
            free  = stat.f_bfree  * stat.f_frsize
            used  = total - free
            pct   = (used / total * 100) if total > 0 else 0
            total_gb = total / (1024**3)
            used_gb  = used  / (1024**3)
            free_gb  = free  / (1024**3)
            status = 'healthy' if pct < 80 else ('degraded' if pct < 90 else 'unhealthy')
            return HealthCheck(status=status,
                               detail=f'{used_gb:.1f}GB / {total_gb:.1f}GB ({pct:.1f}% used)')
        except Exception as e:
            return HealthCheck(status='unknown', error=str(e))

    def get_metrics(self) -> dict:
        """Return dict suitable for JSON API or dashboard."""
        report = self.get_full_health()
        return {
            'overall':  report.overall,
            'database': {'status': report.database.status, 'latency_ms': report.database.latency_ms, 'detail': report.database.detail},
            'cache':    {'status': report.cache.status,    'latency_ms': report.cache.latency_ms,    'detail': report.cache.detail},
            'storage':  {'status': report.storage.status,  'detail': report.storage.detail},
            'memory':   {'status': report.memory.status,   'detail': report.memory.detail},
            'disk':     {'status': report.disk.status,     'detail': report.disk.detail},
        }
