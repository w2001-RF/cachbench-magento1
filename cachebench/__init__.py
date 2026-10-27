"""cachebench : benchmark d'algorithmes de cache pilotés par l'IA, appliqué à Magento."""
from .engine import EngineConfig, resolve_capacity, simulate, trace_stats
from .policies import CachePolicy, KeyedPolicy, available, get_policy, register
from .traces import Request

__version__ = "0.1.0"
__all__ = ["Request", "CachePolicy", "KeyedPolicy", "register", "get_policy", "available",
           "EngineConfig", "simulate", "trace_stats", "resolve_capacity"]
