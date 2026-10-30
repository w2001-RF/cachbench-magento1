from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class CacheRequest:
    """Represents a single cache access request"""
    timestamp: float
    key: str
    size: int  # Size in bytes
    category: str  # product, page, block, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class BenchmarkMetrics:
    """Stores benchmark results"""
    hit_rate: float = 0.0
    miss_rate: float = 0.0
    byte_hit_rate: float = 0.0
    avg_latency_ms: float = 0.0
    evictions: int = 0
    total_requests: int = 0
    cache_utilization: float = 0.0
    category_hit_rates: Dict[str, float] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'hit_rate': self.hit_rate,
            'miss_rate': self.miss_rate,
            'byte_hit_rate': self.byte_hit_rate,
            'avg_latency_ms': self.avg_latency_ms,
            'evictions': self.evictions,
            'total_requests': self.total_requests,
            'cache_utilization': self.cache_utilization,
            'category_hit_rates': self.category_hit_rates
        }
