# app/performance.py

import time
import asyncio
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, deque


@dataclass
class OperationMetrics:
    """Metrics for a single operation"""
    operation_type: str
    start_time: float
    end_time: float
    success: bool
    error_message: Optional[str] = None
    
    @property
    def duration(self) -> float:
        return self.end_time - self.start_time


class PerformanceMonitor:
    """Performance monitoring and metrics collection"""
    
    def __init__(self, max_history: int = 10000):
        self.max_history = max_history
        self.metrics: deque = deque(maxlen=max_history)
        self.operation_counts: Dict[str, int] = defaultdict(int)
        self.error_counts: Dict[str, int] = defaultdict(int)
        self.start_time = time.time()
        self.lock = asyncio.Lock()
    
    async def record_operation(self, operation_type: str, duration: float, success: bool, error_message: Optional[str] = None):
        """Record an operation metric"""
        async with self.lock:
            metric = OperationMetrics(
                operation_type=operation_type,
                start_time=time.time() - duration,
                end_time=time.time(),
                success=success,
                error_message=error_message
            )
            
            self.metrics.append(metric)
            self.operation_counts[operation_type] += 1
            
            if not success:
                self.error_counts[operation_type] += 1
    
    async def get_summary(self, time_window: Optional[float] = None) -> Dict:
        """Get performance summary"""
        async with self.lock:
            current_time = time.time()
            
            # Filter metrics by time window if specified
            if time_window:
                cutoff_time = current_time - time_window
                filtered_metrics = [m for m in self.metrics if m.end_time >= cutoff_time]
            else:
                filtered_metrics = list(self.metrics)
            
            if not filtered_metrics:
                return {
                    "total_operations": 0,
                    "operations_per_second": 0,
                    "error_rate": 0,
                    "avg_latency_ms": 0,
                    "p95_latency_ms": 0,
                    "p99_latency_ms": 0
                }
            
            # Calculate metrics
            total_ops = len(filtered_metrics)
            successful_ops = sum(1 for m in filtered_metrics if m.success)
            error_rate = (total_ops - successful_ops) / total_ops if total_ops > 0 else 0
            
            # Calculate latencies
            durations = [m.duration * 1000 for m in filtered_metrics]  # Convert to ms
            durations.sort()
            
            avg_latency = sum(durations) / len(durations) if durations else 0
            p95_latency = durations[int(0.95 * len(durations))] if durations else 0
            p99_latency = durations[int(0.99 * len(durations))] if durations else 0
            
            # Calculate operations per second
            if time_window:
                ops_per_second = total_ops / time_window
            else:
                uptime = current_time - self.start_time
                ops_per_second = total_ops / uptime if uptime > 0 else 0
            
            # Operation breakdown
            operation_breakdown = defaultdict(int)
            for metric in filtered_metrics:
                operation_breakdown[metric.operation_type] += 1
            
            return {
                "total_operations": total_ops,
                "successful_operations": successful_ops,
                "operations_per_second": round(ops_per_second, 2),
                "error_rate": round(error_rate * 100, 2),
                "avg_latency_ms": round(avg_latency, 2),
                "p95_latency_ms": round(p95_latency, 2),
                "p99_latency_ms": round(p99_latency, 2),
                "operation_breakdown": dict(operation_breakdown),
                "uptime_seconds": round(current_time - self.start_time, 2)
            }
    
    async def get_recent_errors(self, limit: int = 10) -> List[Dict]:
        """Get recent error details"""
        async with self.lock:
            errors = [
                {
                    "operation": m.operation_type,
                    "timestamp": m.end_time,
                    "error": m.error_message,
                    "duration_ms": round(m.duration * 1000, 2)
                }
                for m in reversed(self.metrics)
                if not m.success and m.error_message
            ]
            return errors[:limit]


class OperationTimer:
    """Context manager for timing operations"""
    
    def __init__(self, monitor: PerformanceMonitor, operation_type: str):
        self.monitor = monitor
        self.operation_type = operation_type
        self.start_time = None
        self.success = True
        self.error_message = None
    
    async def __aenter__(self):
        self.start_time = time.time()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        end_time = time.time()
        duration = end_time - self.start_time
        
        if exc_type is not None:
            self.success = False
            self.error_message = str(exc_val)
        
        await self.monitor.record_operation(
            self.operation_type,
            duration,
            self.success,
            self.error_message
        )
        
        return False  # Don't suppress exceptions


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


def timed_operation(operation_type: str):
    """Decorator for timing operations"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            async with OperationTimer(performance_monitor, operation_type):
                return await func(*args, **kwargs)
        return wrapper
    return decorator