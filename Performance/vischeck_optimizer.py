"""
VisCheck Performance Optimizer
Integrates advanced caching and optimization features for the Python vischeck module
"""

import os
import sys
import time
import json
import hashlib
import threading
import queue
from pathlib import Path
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, Future

# Add current directory to path for vischeck.pyd
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    import vischeck
    VISCHECK_AVAILABLE = True
except ImportError:
    VISCHECK_AVAILABLE = False
    print("[Performance] VisCheck module not available - using stub")


@dataclass
class PerformanceMetrics:
    load_time_ms: int = 0
    cache_hit: bool = False
    triangle_count: int = 0
    memory_usage_mb: float = 0.0
    map_file: str = ""
    load_method: str = "standard"
    
    
@dataclass
class CacheEntry:
    map_file: str
    file_hash: str
    file_size: int
    last_modified: float
    triangles: int
    created_time: float
    
    def is_valid(self) -> bool:
        if not os.path.exists(self.map_file):
            return False
        try:
            stat = os.stat(self.map_file)
            return (stat.st_size == self.file_size and 
                   stat.st_mtime == self.last_modified)
        except:
            return False


class VisCheckCache:
    """High-performance cache manager for VisCheck maps"""
    
    def __init__(self, cache_dir: str = "cache/vischeck"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.index_file = self.cache_dir / "cache_index.json"
        self.cache_index: Dict[str, CacheEntry] = {}
        self.lock = threading.RLock()
        self.load_index()
        
    def load_index(self):
        """Load cache index from disk"""
        if not self.index_file.exists():
            return
            
        try:
            with open(self.index_file, 'r') as f:
                data = json.load(f)
                
            for key, entry_data in data.items():
                self.cache_index[key] = CacheEntry(**entry_data)
                
            print(f"[VisCache] Loaded {len(self.cache_index)} cache entries")
        except Exception as e:
            print(f"[VisCache] Failed to load index: {e}")
            
    def save_index(self):
        """Save cache index to disk"""
        try:
            with self.lock:
                data = {k: v.__dict__ for k, v in self.cache_index.items()}
                
            with open(self.index_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[VisCache] Failed to save index: {e}")
            
    def get_file_hash(self, file_path: str) -> str:
        """Quick hash of file for validation"""
        try:
            stat = os.stat(file_path)
            # Use file size + modification time for quick hash
            content = f"{stat.st_size}_{stat.st_mtime}_{file_path}"
            return hashlib.md5(content.encode()).hexdigest()
        except:
            return ""
            
    def is_cached(self, map_file: str) -> bool:
        """Check if map is cached and valid"""
        with self.lock:
            entry = self.cache_index.get(map_file)
            return entry is not None and entry.is_valid()
            
    def add_entry(self, map_file: str, triangles: int = 0):
        """Add new cache entry"""
        try:
            stat = os.stat(map_file)
            entry = CacheEntry(
                map_file=map_file,
                file_hash=self.get_file_hash(map_file),
                file_size=stat.st_size,
                last_modified=stat.st_mtime,
                triangles=triangles,
                created_time=time.time()
            )
            
            with self.lock:
                self.cache_index[map_file] = entry
                
            self.save_index()
            print(f"[VisCache] Added cache entry for {os.path.basename(map_file)}")
        except Exception as e:
            print(f"[VisCache] Failed to add entry: {e}")
            
    def clean_old_entries(self, max_age_hours: int = 24 * 7):
        """Remove old cache entries"""
        cutoff_time = time.time() - (max_age_hours * 3600)
        removed = 0
        
        with self.lock:
            to_remove = []
            for key, entry in self.cache_index.items():
                if entry.created_time < cutoff_time or not entry.is_valid():
                    to_remove.append(key)
                    
            for key in to_remove:
                del self.cache_index[key]
                removed += 1
                
        if removed > 0:
            self.save_index()
            print(f"[VisCache] Cleaned {removed} old entries")
            
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            total = len(self.cache_index)
            valid = sum(1 for e in self.cache_index.values() if e.is_valid())
            total_triangles = sum(e.triangles for e in self.cache_index.values())
            
        return {
            "total_entries": total,
            "valid_entries": valid,
            "total_triangles": total_triangles,
            "cache_dir_size_mb": self._get_dir_size_mb()
        }
        
    def _get_dir_size_mb(self) -> float:
        """Get cache directory size in MB"""
        try:
            total = sum(f.stat().st_size for f in self.cache_dir.rglob('*') if f.is_file())
            return total / (1024 * 1024)
        except:
            return 0.0


class AsyncVisCheck:
    """Async wrapper for VisCheck with performance optimizations"""
    
    def __init__(self, cache_dir: str = "cache/vischeck"):
        self.cache = VisCheckCache(cache_dir)
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="VisCheck")
        self.current_instance: Optional[Any] = None
        self.current_map: str = ""
        self.loading_future: Optional[Future] = None
        self.metrics = PerformanceMetrics()
        self.progress_callback: Optional[Callable[[float, str], None]] = None
        
        # TEMPORARY: Disable caching to prevent crashes
        self.use_caching = False
        print("[AsyncVisCheck] Caching temporarily disabled for stability")
        
    def set_progress_callback(self, callback: Callable[[float, str], None]):
        """Set callback for loading progress updates"""
        self.progress_callback = callback
        
    def is_available(self) -> bool:
        """Check if VisCheck is available"""
        return VISCHECK_AVAILABLE
        
    def is_loading(self) -> bool:
        """Check if map is currently loading"""
        return self.loading_future is not None and not self.loading_future.done()
        
    def is_loaded(self) -> bool:
        """Check if a map is currently loaded"""
        return self.current_instance is not None and hasattr(self.current_instance, 'is_map_loaded') and self.current_instance.is_map_loaded()
        
    def get_current_map(self) -> str:
        """Get currently loaded map file"""
        return self.current_map
        
    def get_metrics(self) -> PerformanceMetrics:
        """Get performance metrics"""
        return self.metrics
        
    def _progress_update(self, progress: float, message: str):
        """Internal progress update"""
        if self.progress_callback:
            self.progress_callback(progress, message)
            
    def _load_map_sync(self, map_file: str) -> tuple[bool, PerformanceMetrics]:
        """Synchronous map loading with metrics"""
        start_time = time.time()
        metrics = PerformanceMetrics(map_file=map_file)
        
        try:
            if not VISCHECK_AVAILABLE:
                return False, metrics
                
            if not os.path.exists(map_file):
                return False, metrics
                
            # Skip cache check if caching is disabled
            if self.use_caching:
                # Check cache first
                self._progress_update(0.1, "Checking cache...")
                if self.cache.is_cached(map_file):
                    metrics.cache_hit = True
                    metrics.load_method = "cached"
                    self._progress_update(0.3, "Cache hit! Loading...")
                else:
                    self._progress_update(0.1, "Cache miss, loading from disk...")
                    metrics.load_method = "disk"
            else:
                self._progress_update(0.1, "Loading from disk (caching disabled)...")
                metrics.load_method = "direct"
                
            # Create VisCheck instance
            self._progress_update(0.4, "Initializing VisCheck...")
            instance = vischeck.VisCheck()
            
            # Load map
            self._progress_update(0.6, "Loading map data...")
            success = instance.load_map(map_file)
            
            if success:
                self._progress_update(0.8, "Finalizing...")
                self.current_instance = instance
                self.current_map = map_file
                
                # Add to cache if not cached (only if caching enabled)
                if self.use_caching and not metrics.cache_hit:
                    try:
                        # Try to get triangle count if available
                        triangle_count = 0
                        if hasattr(instance, 'get_triangle_count'):
                            triangle_count = instance.get_triangle_count()
                        self.cache.add_entry(map_file, triangle_count)
                        metrics.triangle_count = triangle_count
                    except:
                        pass
                        
                self._progress_update(1.0, "Complete!")
                
            end_time = time.time()
            metrics.load_time_ms = int((end_time - start_time) * 1000)
            
            return success, metrics
            
        except Exception as e:
            print(f"[AsyncVisCheck] Load error: {e}")
            return False, metrics
            
    def load_map_async(self, map_file: str) -> Future:
        """Load map asynchronously"""
        # Cancel any existing load
        if self.loading_future and not self.loading_future.done():
            self.loading_future.cancel()
            
        # Submit new load task
        self.loading_future = self.executor.submit(self._load_map_sync, map_file)
        return self.loading_future
        
    def wait_for_load(self, timeout: float = 30.0) -> bool:
        """Wait for current load to complete"""
        if not self.loading_future:
            return self.is_loaded()
            
        try:
            success, metrics = self.loading_future.result(timeout=timeout)
            self.metrics = metrics
            return success
        except Exception as e:
            print(f"[AsyncVisCheck] Wait error: {e}")
            return False
            
    def is_visible(self, pos1: tuple, pos2: tuple) -> bool:
        """Check visibility between two points"""
        if not self.is_loaded():
            print("[AsyncVisCheck] WARNING: No map loaded, defaulting to NOT visible")
            return False  # Default to NOT visible if no map loaded
            
        try:
            return self.current_instance.is_visible(pos1, pos2)
        except Exception as e:
            print(f"[AsyncVisCheck] Visibility check error: {e}")
            return False  # Default to NOT visible on error
            
    def unload_map(self):
        """Unload current map"""
        if self.current_instance:
            try:
                if hasattr(self.current_instance, 'unload_map'):
                    self.current_instance.unload_map()
            except:
                pass
            self.current_instance = None
            self.current_map = ""
            
    def cleanup(self):
        """Cleanup resources"""
        if self.loading_future and not self.loading_future.done():
            self.loading_future.cancel()
            
        self.unload_map()
        self.executor.shutdown(wait=False)
        
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return self.cache.get_stats()
        
    def clean_cache(self, max_age_hours: int = 24 * 7):
        """Clean old cache entries"""
        self.cache.clean_old_entries(max_age_hours)


# Global instance
_global_vischeck: Optional[AsyncVisCheck] = None

def get_global_vischeck() -> AsyncVisCheck:
    """Get global VisCheck instance"""
    global _global_vischeck
    if _global_vischeck is None:
        _global_vischeck = AsyncVisCheck()
    return _global_vischeck

def cleanup_global_vischeck():
    """Cleanup global instance"""
    global _global_vischeck
    if _global_vischeck:
        _global_vischeck.cleanup()
        _global_vischeck = None
