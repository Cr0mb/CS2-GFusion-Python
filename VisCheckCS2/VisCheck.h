#ifndef VISCHECK_H
#define VISCHECK_H

#include <vector>
#include <memory>
#include <string>
#include <thread>
#include <future>
#include <unordered_map>
#include <mutex>
#include <fstream>
#include <chrono>
#include <immintrin.h>  // For SIMD optimizations
#include "OptimizedGeometry.h"
#include "Math.hpp"

struct BVHNode {
    AABB bounds;
    std::vector<TriangleCombined> triangles;
    std::unique_ptr<BVHNode> left;
    std::unique_ptr<BVHNode> right;

    bool IsLeaf() const { return !left && !right; }
};


class VisCheck {
private:
    OptimizedGeometry geometry;
    std::vector<std::unique_ptr<BVHNode>> bvhNodes;
    bool mapLoaded;
    std::string currentMapFile;
    
    // Threading support
    std::future<bool> loadingFuture;
    bool isLoading;
    std::mutex loadingMutex;
    
    // Performance monitoring
    struct PerformanceMetrics {
        std::chrono::high_resolution_clock::time_point loadStartTime{std::chrono::high_resolution_clock::now()};
        std::chrono::milliseconds lastLoadTime{0};
        size_t triangleCount = 0;
        size_t memoryUsage = 0;
        bool cacheHit = false;
        
        // Default constructor
        PerformanceMetrics() = default;
        
        // Copy constructor  
        PerformanceMetrics(const PerformanceMetrics& other) = default;
        
        // Assignment operator
        PerformanceMetrics& operator=(const PerformanceMetrics& other) = default;
    } metrics;

    std::unique_ptr<BVHNode> BuildBVH(const std::vector<TriangleCombined>& triangles);
    std::unique_ptr<BVHNode> BuildBVHOptimized(const std::vector<TriangleCombined>& triangles);
    std::unique_ptr<BVHNode> BuildBVHFast(const std::vector<TriangleCombined>& triangles);
    std::unique_ptr<BVHNode> BuildBVHWithSubdivision(const std::vector<TriangleCombined>& triangles);
    std::vector<std::unique_ptr<BVHNode>> BuildBVHParallel(const std::vector<std::vector<TriangleCombined>>& meshes);
    bool IntersectBVH(const BVHNode* node, const Vector3& rayOrigin, const Vector3& rayDir, float maxDistance, float& hitDistance);
    bool IntersectBVHSIMD(const BVHNode* node, const Vector3& rayOrigin, const Vector3& rayDir, float maxDistance, float& hitDistance);
    bool RayIntersectsTriangle(const Vector3& rayOrigin, const Vector3& rayDir, const TriangleCombined& triangle, float& t);
    bool RayIntersectsTriangleSIMD(const Vector3& rayOrigin, const Vector3& rayDir, const TriangleCombined& triangle, float& t);
    
    // Advanced loading methods
    bool LoadMapMemoryMapped(const std::string& optimizedGeometryFile);
    bool LoadMapPartial(const std::string& optimizedGeometryFile, size_t maxMeshes = 0);
    bool LoadMapProgressive(const std::string& optimizedGeometryFile, std::function<void(float)> progressCallback = nullptr);
    
    // Internal optimization methods
    void OptimizeMemoryLayout();
    void PrewarmCache();
    static void InitializeStatics();
    static void CleanupStatics();

public:
    VisCheck(const std::string& optimizedGeometryFile);
    VisCheck();
    ~VisCheck();
    
    // Async loading methods
    bool LoadMapAsync(const std::string& optimizedGeometryFile);
    bool LoadMap(const std::string& optimizedGeometryFile);
    bool IsLoadingComplete();
    void WaitForLoading();
    
    void UnloadMap();
    bool IsPointVisible(const Vector3& point1, const Vector3& point2);
    bool IsMapLoaded() const;
    std::string GetCurrentMap() const;
    
    // Performance settings
    static void SetCacheEnabled(bool enabled);
    static void ClearCache();
    static void SetCacheDirectory(const std::string& directory);
    static void CleanOldCache(std::chrono::hours maxAge = std::chrono::hours(24 * 7));
    
    // Performance monitoring
    PerformanceMetrics GetPerformanceMetrics() const;
    void ResetPerformanceMetrics();
    
    // Lazy loading and streaming
    bool EnableLazyLoading(bool enable = true);
    void SetMaxMemoryUsage(size_t maxBytes);
    
    // Static initialization
    class StaticInitializer {
    public:
        StaticInitializer();
        ~StaticInitializer();
    };
    static StaticInitializer staticInit;
};

#endif
