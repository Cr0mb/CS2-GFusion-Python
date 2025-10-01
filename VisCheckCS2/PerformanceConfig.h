#pragma once

// Performance Configuration for VisCheckCS2
// Adjust these values based on your system and requirements

namespace PerformanceConfig {
    
    // BVH Construction Settings
    constexpr size_t BVH_LEAF_THRESHOLD = 10;          // Triangles per leaf node
    constexpr size_t BVH_PARALLEL_THRESHOLD = 1000;    // Min triangles for parallel build
    
    // Memory Management
    constexpr size_t MEMORY_POOL_SIZE = 10000;         // Max BVH nodes in pool
    constexpr size_t DEFAULT_BUFFER_SIZE = 1024 * 1024; // 1MB I/O buffer
    constexpr size_t LARGE_FILE_THRESHOLD = 100 * 1024 * 1024; // 100MB for memory mapping
    constexpr size_t MEDIUM_FILE_THRESHOLD = 10 * 1024 * 1024;  // 10MB for buffered I/O
    
    // Cache Settings
    constexpr bool ENABLE_PERSISTENT_CACHE = true;
    constexpr int CACHE_MAX_AGE_DAYS = 7;              // Auto-cleanup after 7 days
    inline const char* DEFAULT_CACHE_DIR = "cache";
    
    // Optimization Settings
    constexpr bool ENABLE_SIMD = true;
    constexpr bool ENABLE_PREFETCHING = true;
    constexpr size_t SIMD_BATCH_SIZE = 4;
    constexpr size_t PREFETCH_DISTANCE = 2;           // Prefetch 2 cache lines ahead
    
    // Ray Intersection
    constexpr float RAY_EPSILON = 1e-7f;
    
    // Lazy Loading Settings
    constexpr size_t PROGRESSIVE_CHUNK_SIZE = 100;     // Meshes per chunk
    constexpr size_t MAX_PARTIAL_MESHES = 1000;       // Max meshes for partial loading
    
    // System Optimization
    constexpr bool OPTIMIZE_MEMORY_LAYOUT = true;
    constexpr bool ENABLE_CACHE_PREWARMING = true;
    
    // Performance Monitoring
    constexpr bool ENABLE_PERFORMANCE_METRICS = true;
    constexpr bool VERBOSE_LOADING = true;
}

// Platform-specific optimizations
#ifdef _WIN32
    #define PLATFORM_WINDOWS 1
    #define USE_MEMORY_MAPPING 1
#else
    #define PLATFORM_WINDOWS 0
    #define USE_MEMORY_MAPPING 1
#endif

// Compiler-specific optimizations
#ifdef _MSC_VER
    #define FORCE_INLINE __forceinline
    #define LIKELY(x) (x)
    #define UNLIKELY(x) (x)
#elif defined(__GNUC__) || defined(__clang__)
    #define FORCE_INLINE inline __attribute__((always_inline))
    #define LIKELY(x) __builtin_expect(!!(x), 1)
    #define UNLIKELY(x) __builtin_expect(!!(x), 0)
#else
    #define FORCE_INLINE inline
    #define LIKELY(x) (x)
    #define UNLIKELY(x) (x)
#endif

// Memory alignment for SIMD
#ifdef _MSC_VER
    #define ALIGN(n) __declspec(align(n))
#else
    #define ALIGN(n) __attribute__((aligned(n)))
#endif
