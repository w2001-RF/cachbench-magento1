
from abc import ABC, abstractmethod
from .models import CacheRequest

class CacheAlgorithm(ABC):
    """Base class for cache replacement algorithms"""
    
    def __init__(self, cache_size: int, name: str):
        self.cache_size = cache_size
        self.name = name
        self.cache = {}
        self.current_size = 0
        
    @abstractmethod
    def get(self, request: CacheRequest) -> bool:
        """
        Attempt to retrieve item from cache
        Returns True if hit, False if miss
        """
        pass
    
    @abstractmethod
    def put(self, request: CacheRequest) -> int:
        """
        Add item to cache, evicting if necessary
        Returns number of evictions performed
        """
        pass
    
    @abstractmethod
    def should_cache(self, request: CacheRequest) -> bool:
        """Determine if item should be cached"""
        pass
    
    def reset(self):
        """Reset cache state"""
        self.cache = {}
        self.current_size = 0