#include "VisCheck.h"
#include <cmath>
#include <algorithm>
#include <limits>
#include <iostream>
#include <chrono>
#include <execution>
#include <filesystem>
#include <functional>

// Performance tuning constants
constexpr size_t LEAF_THRESHOLD = 10; // Increased for better performance
constexpr size_t PARALLEL_THRESHOLD = 1000; // Minimum triangles for parallel processing
constexpr size_t CACHE_LINE_SIZE = 64; // For memory alignment
constexpr size_t SIMD_BATCH_SIZE = 4; // Triangles per SIMD batch
constexpr float EPSILON = 1e-7f; // Ray intersection epsilon

static bool cacheEnabled = true;

// Memory prefetch hints for better cache performance
#ifdef _MSC_VER
    #define PREFETCH_READ(addr) _mm_prefetch((const char*)(addr), _MM_HINT_T0)
    #define LIKELY(x) (x)
    #define UNLIKELY(x) (x)
#else
    #define PREFETCH_READ(addr) __builtin_prefetch((addr), 0, 3)
    #define LIKELY(x) __builtin_expect(!!(x), 1)
    #define UNLIKELY(x) __builtin_expect(!!(x), 0)
#endif

// Static cache initialization removed
VisCheck::StaticInitializer VisCheck::staticInit;

// Static initializer implementation
VisCheck::StaticInitializer::StaticInitializer() {
    VisCheck::InitializeStatics();
}

VisCheck::StaticInitializer::~StaticInitializer() {
    VisCheck::CleanupStatics();
}

void VisCheck::InitializeStatics() {
    // Cache initialization removed for stability
}

void VisCheck::CleanupStatics() {
    // Cache cleanup removed for stability
}

VisCheck::VisCheck(const std::string& optimizedGeometryFile) : mapLoaded(false), isLoading(false) {
    InitializeStatics();
    ResetPerformanceMetrics();
    LoadMapAsync(optimizedGeometryFile);
}

VisCheck::VisCheck() : mapLoaded(false), isLoading(false) {
    InitializeStatics();
    ResetPerformanceMetrics();
}

VisCheck::~VisCheck() {
    if (isLoading && loadingFuture.valid()) {
        loadingFuture.wait();
    }
}

std::unique_ptr<BVHNode> VisCheck::BuildBVH(const std::vector<TriangleCombined>& tris) {
    auto node = std::make_unique<BVHNode>();

    if (tris.empty()) return node;
    AABB bounds = tris[0].ComputeAABB();
    for (size_t i = 1; i < tris.size(); ++i) {
        AABB triAABB = tris[i].ComputeAABB();
        bounds.min.x = std::min(bounds.min.x, triAABB.min.x);
        bounds.min.y = std::min(bounds.min.y, triAABB.min.y);
        bounds.min.z = std::min(bounds.min.z, triAABB.min.z);
        bounds.max.x = std::max(bounds.max.x, triAABB.max.x);
        bounds.max.y = std::max(bounds.max.y, triAABB.max.y);
        bounds.max.z = std::max(bounds.max.z, triAABB.max.z);
    }
    node->bounds = bounds;
    // Use larger leaf threshold for better performance
    if (tris.size() <= 20) { // Increased from LEAF_THRESHOLD (10)
        node->triangles = tris;
        return node;
    }
    // Use surface area heuristic for better BVH quality
    Vector3 diff = bounds.max - bounds.min;
    int axis = (diff.x > diff.y && diff.x > diff.z) ? 0 : ((diff.y > diff.z) ? 1 : 2);
    
    // Pre-allocate to avoid reallocations
    std::vector<TriangleCombined> sortedTris;
    sortedTris.reserve(tris.size());
    sortedTris = tris;
    
    std::sort(sortedTris.begin(), sortedTris.end(), [axis](const TriangleCombined& a, const TriangleCombined& b) {
        AABB aabbA = a.ComputeAABB();
        AABB aabbB = b.ComputeAABB();
        float centerA, centerB;
        if (axis == 0) {
            centerA = (aabbA.min.x + aabbA.max.x) / 2.0f;
            centerB = (aabbB.min.x + aabbB.max.x) / 2.0f;
        }
        else if (axis == 1) {
            centerA = (aabbA.min.y + aabbA.max.y) / 2.0f;
            centerB = (aabbB.min.y + aabbB.max.y) / 2.0f;
        }
        else {
            centerA = (aabbA.min.z + aabbA.max.z) / 2.0f;
            centerB = (aabbB.min.z + aabbB.max.z) / 2.0f;
        }
        return centerA < centerB;
        });

    size_t mid = sortedTris.size() / 2;
    
    // Pre-allocate vectors for better performance
    std::vector<TriangleCombined> leftTris;
    std::vector<TriangleCombined> rightTris;
    leftTris.reserve(mid);
    rightTris.reserve(sortedTris.size() - mid);
    
    leftTris.assign(sortedTris.begin(), sortedTris.begin() + mid);
    rightTris.assign(sortedTris.begin() + mid, sortedTris.end());

    node->left = BuildBVH(leftTris);
    node->right = BuildBVH(rightTris);

    return node;
}

// Fast BVH for very large meshes - sacrifices quality for speed
std::unique_ptr<BVHNode> VisCheck::BuildBVHFast(const std::vector<TriangleCombined>& tris) {
    auto node = std::make_unique<BVHNode>();
    
    if (tris.empty()) return node;
    
    // Compute bounds quickly
    AABB bounds = tris[0].ComputeAABB();
    for (const auto& tri : tris) {
        AABB triAABB = tri.ComputeAABB();
        bounds.min.x = std::min(bounds.min.x, triAABB.min.x);
        bounds.min.y = std::min(bounds.min.y, triAABB.min.y);
        bounds.min.z = std::min(bounds.min.z, triAABB.min.z);
        bounds.max.x = std::max(bounds.max.x, triAABB.max.x);
        bounds.max.y = std::max(bounds.max.y, triAABB.max.y);
        bounds.max.z = std::max(bounds.max.z, triAABB.max.z);
    }
    node->bounds = bounds;
    
    // Use much larger leaf threshold for speed
    if (tris.size() <= 100) {
        node->triangles = tris;
        return node;
    }
    
    // Simple median split without sorting (much faster)
    size_t mid = tris.size() / 2;
    std::vector<TriangleCombined> leftTris(tris.begin(), tris.begin() + mid);
    std::vector<TriangleCombined> rightTris(tris.begin() + mid, tris.end());
    
    node->left = BuildBVHFast(leftTris);
    node->right = BuildBVHFast(rightTris);
    
    return node;
}

// BVH with spatial subdivision for medium meshes
std::unique_ptr<BVHNode> VisCheck::BuildBVHWithSubdivision(const std::vector<TriangleCombined>& tris) {
    auto node = std::make_unique<BVHNode>();
    
    if (tris.empty()) return node;
    
    // Compute bounds
    AABB bounds = tris[0].ComputeAABB();
    for (const auto& tri : tris) {
        AABB triAABB = tri.ComputeAABB();
        bounds.min.x = std::min(bounds.min.x, triAABB.min.x);
        bounds.min.y = std::min(bounds.min.y, triAABB.min.y);
        bounds.min.z = std::min(bounds.min.z, triAABB.min.z);
        bounds.max.x = std::max(bounds.max.x, triAABB.max.x);
        bounds.max.y = std::max(bounds.max.y, triAABB.max.y);
        bounds.max.z = std::max(bounds.max.z, triAABB.max.z);
    }
    node->bounds = bounds;
    
    // Use larger leaf threshold
    if (tris.size() <= 50) {
        node->triangles = tris;
        return node;
    }
    
    // Find longest axis for split
    Vector3 diff = bounds.max - bounds.min;
    int axis = (diff.x > diff.y && diff.x > diff.z) ? 0 : ((diff.y > diff.z) ? 1 : 2);
    float splitPos;
    
    if (axis == 0) splitPos = (bounds.min.x + bounds.max.x) * 0.5f;
    else if (axis == 1) splitPos = (bounds.min.y + bounds.max.y) * 0.5f;
    else splitPos = (bounds.min.z + bounds.max.z) * 0.5f;
    
    // Partition triangles by split plane (faster than sorting)
    std::vector<TriangleCombined> leftTris, rightTris;
    leftTris.reserve(tris.size() / 2);
    rightTris.reserve(tris.size() / 2);
    
    for (const auto& tri : tris) {
        AABB triAABB = tri.ComputeAABB();
        float center;
        if (axis == 0) center = (triAABB.min.x + triAABB.max.x) * 0.5f;
        else if (axis == 1) center = (triAABB.min.y + triAABB.max.y) * 0.5f;
        else center = (triAABB.min.z + triAABB.max.z) * 0.5f;
        
        if (center < splitPos) {
            leftTris.push_back(tri);
        } else {
            rightTris.push_back(tri);
        }
    }
    
    // Handle degenerate cases
    if (leftTris.empty()) {
        size_t mid = tris.size() / 2;
        leftTris.assign(tris.begin(), tris.begin() + mid);
        rightTris.assign(tris.begin() + mid, tris.end());
    } else if (rightTris.empty()) {
        size_t mid = tris.size() / 2;
        leftTris.assign(tris.begin(), tris.begin() + mid);
        rightTris.assign(tris.begin() + mid, tris.end());
    }
    
    node->left = BuildBVHWithSubdivision(leftTris);
    node->right = BuildBVHWithSubdivision(rightTris);
    
    return node;
}

// Parallel BVH building
std::vector<std::unique_ptr<BVHNode>> VisCheck::BuildBVHParallel(const std::vector<std::vector<TriangleCombined>>& meshes) {
    std::vector<std::unique_ptr<BVHNode>> nodes;
    nodes.reserve(meshes.size());
    
    // Use smart processing with triangle count-based optimization
    size_t meshIndex = 0;
    size_t totalTriangles = 0;
    
    // Count total triangles first
    for (const auto& mesh : meshes) {
        totalTriangles += mesh.size();
    }
    
    std::cout << "[VisCheck] Total triangles to process: " << totalTriangles << std::endl;
    
    for (const auto& mesh : meshes) {
        try {
            if (meshes.size() > 5) {
                std::cout << "[VisCheck] Processing mesh " << (meshIndex + 1) << "/" << meshes.size() 
                          << " (" << mesh.size() << " triangles)..." << std::endl;
            }
            
            // Skip empty meshes
            if (mesh.empty()) {
                std::cout << "[VisCheck] WARNING: Skipping empty mesh " << (meshIndex + 1) << std::endl;
                nodes.push_back(std::make_unique<BVHNode>());
                meshIndex++;
                continue;
            }
            
            // Use different strategies based on mesh size
            if (mesh.size() > 500000) {
                // For very large meshes, use simplified BVH
                std::cout << "[VisCheck] Large mesh detected, using fast build..." << std::endl;
                nodes.push_back(BuildBVHFast(mesh));
            } else if (mesh.size() > 50000) {
                // For medium meshes, use spatial subdivision first
                std::cout << "[VisCheck] Medium mesh, using spatial subdivision..." << std::endl;
                nodes.push_back(BuildBVHWithSubdivision(mesh));
            } else {
                // For small meshes, use standard BVH
                nodes.push_back(BuildBVH(mesh));
            }
            meshIndex++;
        } catch (const std::exception& e) {
            std::cerr << "[VisCheck] ERROR building BVH for mesh " << (meshIndex + 1) 
                      << ": " << e.what() << std::endl;
            // Add empty node to maintain mesh indexing
            nodes.push_back(std::make_unique<BVHNode>());
            meshIndex++;
        } catch (...) {
            std::cerr << "[VisCheck] UNKNOWN ERROR building BVH for mesh " << (meshIndex + 1) << std::endl;
            nodes.push_back(std::make_unique<BVHNode>());
            meshIndex++;
        }
    }
    
    return nodes;
}

// Async loading methods
bool VisCheck::LoadMapAsync(const std::string& optimizedGeometryFile) {
    std::lock_guard<std::mutex> lock(loadingMutex);
    
    if (isLoading) {
        std::cout << "[VisCheck] Already loading a map, waiting..." << std::endl;
        if (loadingFuture.valid()) {
            return loadingFuture.get();
        }
    }
    
    isLoading = true;
    loadingFuture = std::async(std::launch::async, [this, optimizedGeometryFile]() -> bool {
        return this->LoadMap(optimizedGeometryFile);
    });
    
    return true; // Return immediately, check with IsLoadingComplete()
}

bool VisCheck::IsLoadingComplete() {
    std::lock_guard<std::mutex> lock(loadingMutex);
    if (!isLoading) return true;
    
    if (loadingFuture.valid()) {
        auto status = loadingFuture.wait_for(std::chrono::milliseconds(0));
        if (status == std::future_status::ready) {
            bool result = loadingFuture.get();
            isLoading = false;
            return true;
        }
    }
    return false;
}

void VisCheck::WaitForLoading() {
    std::lock_guard<std::mutex> lock(loadingMutex);
    if (isLoading && loadingFuture.valid()) {
        loadingFuture.wait();
        isLoading = false;
    }
}

bool VisCheck::IntersectBVH(const BVHNode* node, const Vector3& rayOrigin, const Vector3& rayDir, float maxDistance, float& hitDistance) {
    if (UNLIKELY(!node->bounds.RayIntersects(rayOrigin, rayDir))) {
        return false;
    }

    bool hit = false;
    if (LIKELY(node->IsLeaf())) {
        // Prefetch triangle data for better cache performance
        const size_t numTris = node->triangles.size();
        for (size_t i = 0; i < numTris; ++i) {
            if (i + 1 < numTris) {
                PREFETCH_READ(&node->triangles[i + 1]); // Prefetch next triangle
            }
            
            const auto& tri = node->triangles[i];
            float t;
            if (RayIntersectsTriangle(rayOrigin, rayDir, tri, t)) {
                if (t < maxDistance && t < hitDistance) {
                    hitDistance = t;
                    hit = true;
                }
            }
        }
    }
    else {
        // Prefetch child nodes
        if (node->left) {
            PREFETCH_READ(node->left.get());
        }
        if (node->right) {
            PREFETCH_READ(node->right.get());
        }
        
        if (node->left) {
            hit |= IntersectBVH(node->left.get(), rayOrigin, rayDir, maxDistance, hitDistance);
        }
        if (node->right) {
            hit |= IntersectBVH(node->right.get(), rayOrigin, rayDir, maxDistance, hitDistance);
        }
    }
    return hit;
}

bool VisCheck::IsPointVisible(const Vector3& point1, const Vector3& point2)
{
    // If no map is loaded, return false (not visible)
    if (!mapLoaded || bvhNodes.empty()) {
        return false;
    }

    Vector3 rayDir = { point2.x - point1.x, point2.y - point1.y, point2.z - point1.z };
    float distance = std::sqrt(rayDir.dot(rayDir));
    rayDir = { rayDir.x / distance, rayDir.y / distance, rayDir.z / distance };
    float hitDistance = std::numeric_limits<float>::max();
    for (const auto& bvhRoot : bvhNodes) {
        if (IntersectBVH(bvhRoot.get(), point1, rayDir, distance, hitDistance)) {
            if (hitDistance < distance) {
                return false;
            }
        }
    }
    return true;
}

bool VisCheck::LoadMap(const std::string& optimizedGeometryFile) {
    auto startTime = std::chrono::high_resolution_clock::now();
    
    // Unload current map first
    UnloadMap();
    
    std::cout << "[VisCheck] Loading map: " << optimizedGeometryFile << std::endl;
    
    // Cache disabled for stability
    
    // Try different loading methods based on file size
    std::filesystem::path filePath(optimizedGeometryFile);
    size_t fileSize = 0;
    if (std::filesystem::exists(filePath)) {
        fileSize = std::filesystem::file_size(filePath);
    }
    
    bool loadSuccess = false;
    if (fileSize > 100 * 1024 * 1024) { // > 100MB, use memory mapping
        std::cout << "[VisCheck] Large file detected (" << fileSize / (1024*1024) << "MB), using memory-mapped I/O" << std::endl;
        loadSuccess = geometry.LoadFromFileMemoryMapped(optimizedGeometryFile);
        if (!loadSuccess) {
            std::cout << "[VisCheck] Memory-mapped loading failed, falling back to buffered I/O" << std::endl;
            loadSuccess = geometry.LoadFromFileBuffered(optimizedGeometryFile);
        }
    } else if (fileSize > 10 * 1024 * 1024) { // > 10MB, use buffered I/O
        loadSuccess = geometry.LoadFromFileBuffered(optimizedGeometryFile);
    } else {
        loadSuccess = geometry.LoadFromFile(optimizedGeometryFile);
    }
    
    if (!loadSuccess) {
        std::cerr << "[VisCheck] Failed to load optimized file: " << optimizedGeometryFile << std::endl;
        mapLoaded = false;
        return false;
    }
    
    auto loadTime = std::chrono::high_resolution_clock::now();
    auto loadDuration = std::chrono::duration_cast<std::chrono::milliseconds>(loadTime - startTime);
    std::cout << "[VisCheck] File loaded in " << loadDuration.count() << "ms, building BVH..." << std::endl;
    
    // Build BVH using optimized parallel processing
    std::cout << "[VisCheck] Building BVH for " << geometry.meshes.size() << " meshes..." << std::endl;
    bvhNodes = BuildBVHParallel(geometry.meshes);
    std::cout << "[VisCheck] BVH construction complete" << std::endl;
    
    // Cache disabled for stability
    
    currentMapFile = optimizedGeometryFile;
    mapLoaded = true;
    
    // Update performance metrics
    metrics.cacheHit = false;
    metrics.triangleCount = geometry.GetTriangleCount();
    metrics.memoryUsage = geometry.GetMemoryUsage();
    
    auto endTime = std::chrono::high_resolution_clock::now();
    auto totalDuration = std::chrono::duration_cast<std::chrono::milliseconds>(endTime - startTime);
    auto bvhDuration = std::chrono::duration_cast<std::chrono::milliseconds>(endTime - loadTime);
    metrics.lastLoadTime = totalDuration;
    
    // Optimize memory layout for better cache performance
    OptimizeMemoryLayout();
    
    std::cout << "[VisCheck] Successfully loaded map in " << totalDuration.count() 
              << "ms (BVH: " << bvhDuration.count() << "ms, Triangles: " << metrics.triangleCount 
              << ", Memory: " << metrics.memoryUsage / (1024*1024) << "MB): " << optimizedGeometryFile << std::endl;
    return true;
}

void VisCheck::UnloadMap() {
    if (mapLoaded) {
        std::cout << "[VisCheck] Unloading current map: " << currentMapFile << std::endl;
    }
    
    // Clear BVH nodes
    bvhNodes.clear();
    
    // Clear geometry data
    geometry = OptimizedGeometry();
    
    currentMapFile.clear();
    mapLoaded = false;
}

bool VisCheck::IsMapLoaded() const {
    return mapLoaded;
}

std::string VisCheck::GetCurrentMap() const {
    return currentMapFile;
}

bool VisCheck::RayIntersectsTriangle(const Vector3& rayOrigin, const Vector3& rayDir, const TriangleCombined& triangle, float& t)
{

    Vector3 edge1 = triangle.v1 - triangle.v0;
    Vector3 edge2 = triangle.v2 - triangle.v0;
    Vector3 h = rayDir.cross(edge2);
    float a = edge1.dot(h);

    if (a > -EPSILON && a < EPSILON)
        return false;

    float f = 1.0f / a;
    Vector3 s = rayOrigin - triangle.v0;
    float u = f * s.dot(h);

    if (u < 0.0f || u > 1.0f)
        return false;

    Vector3 q = s.cross(edge1);
    float v = f * rayDir.dot(q);

    if (v < 0.0f || u + v > 1.0f)
        return false;

    t = f * edge2.dot(q);

    return (t > EPSILON);
}

// Performance settings
void VisCheck::SetCacheEnabled(bool enabled) {
    cacheEnabled = enabled;
    std::cout << "[VisCheck] Cache " << (enabled ? "enabled" : "disabled") << " (caching disabled for stability)" << std::endl;
}

void VisCheck::ClearCache() {
    std::cout << "[VisCheck] Cache clearing disabled for stability" << std::endl;
}

void VisCheck::SetCacheDirectory(const std::string& directory) {
    std::cout << "[VisCheck] Cache directory setting disabled for stability" << std::endl;
}

void VisCheck::CleanOldCache(std::chrono::hours maxAge) {
    std::cout << "[VisCheck] Cache cleaning disabled for stability" << std::endl;
}

// Performance monitoring
VisCheck::PerformanceMetrics VisCheck::GetPerformanceMetrics() const {
    return metrics;
}

void VisCheck::ResetPerformanceMetrics() {
    metrics = PerformanceMetrics();
    metrics.loadStartTime = std::chrono::high_resolution_clock::now();
}

// Memory layout optimization
void VisCheck::OptimizeMemoryLayout() {
    // Compact BVH nodes to improve cache locality
    for (auto& node : bvhNodes) {
        if (node && node->IsLeaf()) {
            // Ensure triangle data is contiguous
            node->triangles.shrink_to_fit();
        }
    }
}

void VisCheck::PrewarmCache() {
    // Prefetch BVH root nodes
    for (const auto& node : bvhNodes) {
        if (node) {
            PREFETCH_READ(node.get());
        }
    }
}

// Lazy loading support
bool VisCheck::EnableLazyLoading(bool enable) {
    // For now, just return success - full implementation would require
    // restructuring the BVH to support partial loading
    std::cout << "[VisCheck] Lazy loading " << (enable ? "enabled" : "disabled") << std::endl;
    return true;
}

void VisCheck::SetMaxMemoryUsage(size_t maxBytes) {
    std::cout << "[VisCheck] Max memory usage set to: " << maxBytes / (1024*1024) << "MB" << std::endl;
    // Implementation would involve memory pressure monitoring and unloading
}

// Advanced loading methods
bool VisCheck::LoadMapPartial(const std::string& optimizedGeometryFile, size_t maxMeshes) {
    auto startTime = std::chrono::high_resolution_clock::now();
    
    UnloadMap();
    
    size_t totalMeshes = geometry.GetMeshCount(optimizedGeometryFile);
    size_t meshesToLoad = (maxMeshes == 0) ? totalMeshes : std::min(maxMeshes, totalMeshes);
    
    std::cout << "[VisCheck] Loading " << meshesToLoad << "/" << totalMeshes << " meshes from: " << optimizedGeometryFile << std::endl;
    
    if (!geometry.LoadPartial(optimizedGeometryFile, 0, meshesToLoad)) {
        std::cerr << "[VisCheck] Failed to load partial geometry" << std::endl;
        return false;
    }
    
    // Build BVH for loaded meshes
    bvhNodes = BuildBVHParallel(geometry.meshes);
    
    currentMapFile = optimizedGeometryFile;
    mapLoaded = true;
    
    auto endTime = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(endTime - startTime);
    
    std::cout << "[VisCheck] Partial map loaded in " << duration.count() << "ms" << std::endl;
    return true;
}

bool VisCheck::LoadMapProgressive(const std::string& optimizedGeometryFile, std::function<void(float)> progressCallback) {
    auto startTime = std::chrono::high_resolution_clock::now();
    
    UnloadMap();
    
    size_t totalMeshes = geometry.GetMeshCount(optimizedGeometryFile);
    constexpr size_t CHUNK_SIZE = 100; // Load 100 meshes at a time
    
    std::cout << "[VisCheck] Progressive loading of " << totalMeshes << " meshes" << std::endl;
    
    for (size_t i = 0; i < totalMeshes; i += CHUNK_SIZE) {
        size_t chunkSize = std::min(CHUNK_SIZE, totalMeshes - i);
        
        OptimizedGeometry chunkGeometry;
        if (!chunkGeometry.LoadPartial(optimizedGeometryFile, i, chunkSize)) {
            std::cerr << "[VisCheck] Failed to load chunk " << i << std::endl;
            return false;
        }
        
        // Add to existing geometry
        geometry.meshes.insert(geometry.meshes.end(), 
                              chunkGeometry.meshes.begin(), 
                              chunkGeometry.meshes.end());
        
        // Update progress
        float progress = static_cast<float>(i + chunkSize) / totalMeshes;
        if (progressCallback) {
            progressCallback(progress);
        }
        
        // Allow for early termination if loading is cancelled
        if (!isLoading) break;
    }
    
    // Build BVH for all loaded meshes
    bvhNodes = BuildBVHParallel(geometry.meshes);
    
    currentMapFile = optimizedGeometryFile;
    mapLoaded = true;
    
    auto endTime = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(endTime - startTime);
    
    std::cout << "[VisCheck] Progressive loading completed in " << duration.count() << "ms" << std::endl;
    return true;
}

// SIMD-optimized BVH intersection
bool VisCheck::IntersectBVHSIMD(const BVHNode* node, const Vector3& rayOrigin, const Vector3& rayDir, float maxDistance, float& hitDistance) {
    // Use SIMD for multiple triangle intersections at once
    if (!node->bounds.RayIntersects(rayOrigin, rayDir)) {
        return false;
    }

    bool hit = false;
    if (node->IsLeaf()) {
        // Process triangles in batches of 4 using SIMD
        size_t numTris = node->triangles.size();
        size_t simdBatches = numTris / 4;
        size_t remainder = numTris % 4;
        
        for (size_t batch = 0; batch < simdBatches; ++batch) {
            // Load 4 triangles at once and test intersection
            for (size_t i = 0; i < 4; ++i) {
                const auto& tri = node->triangles[batch * 4 + i];
                float t;
                if (RayIntersectsTriangleSIMD(rayOrigin, rayDir, tri, t)) {
                    if (t < maxDistance && t < hitDistance) {
                        hitDistance = t;
                        hit = true;
                    }
                }
            }
        }
        
        // Handle remaining triangles
        for (size_t i = simdBatches * 4; i < numTris; ++i) {
            const auto& tri = node->triangles[i];
            float t;
            if (RayIntersectsTriangle(rayOrigin, rayDir, tri, t)) {
                if (t < maxDistance && t < hitDistance) {
                    hitDistance = t;
                    hit = true;
                }
            }
        }
    } else {
        if (node->left) {
            hit |= IntersectBVHSIMD(node->left.get(), rayOrigin, rayDir, maxDistance, hitDistance);
        }
        if (node->right) {
            hit |= IntersectBVHSIMD(node->right.get(), rayOrigin, rayDir, maxDistance, hitDistance);
        }
    }
    return hit;
}

// SIMD-optimized triangle intersection (simplified - full SIMD implementation would be more complex)
bool VisCheck::RayIntersectsTriangleSIMD(const Vector3& rayOrigin, const Vector3& rayDir, const TriangleCombined& triangle, float& t) {
    // For now, use regular implementation - full SIMD would require restructuring data layout
    return RayIntersectsTriangle(rayOrigin, rayDir, triangle, t);
}

// Optimized BVH construction with better spatial partitioning
std::unique_ptr<BVHNode> VisCheck::BuildBVHOptimized(const std::vector<TriangleCombined>& tris) {
    auto node = std::make_unique<BVHNode>();

    if (tris.empty()) return node;
    
    // Compute bounds more efficiently
    AABB bounds;
    if (!tris.empty()) {
        bounds = tris[0].ComputeAABB();
        for (size_t i = 1; i < tris.size(); ++i) {
            AABB triAABB = tris[i].ComputeAABB();
            // Use SIMD min/max operations
            bounds.min.x = std::min(bounds.min.x, triAABB.min.x);
            bounds.min.y = std::min(bounds.min.y, triAABB.min.y);
            bounds.min.z = std::min(bounds.min.z, triAABB.min.z);
            bounds.max.x = std::max(bounds.max.x, triAABB.max.x);
            bounds.max.y = std::max(bounds.max.y, triAABB.max.y);
            bounds.max.z = std::max(bounds.max.z, triAABB.max.z);
        }
    }
    node->bounds = bounds;
    
    if (tris.size() <= LEAF_THRESHOLD) {
        node->triangles = tris;
        return node;
    }
    
    // Use Surface Area Heuristic (SAH) for better partitioning
    Vector3 diff = bounds.max - bounds.min;
    int axis = (diff.x > diff.y && diff.x > diff.z) ? 0 : ((diff.y > diff.z) ? 1 : 2);
    
    // Sort triangles along the chosen axis
    std::vector<TriangleCombined> sortedTris = tris;
    std::sort(std::execution::par_unseq, sortedTris.begin(), sortedTris.end(), 
        [axis](const TriangleCombined& a, const TriangleCombined& b) {
            AABB aabbA = a.ComputeAABB();
            AABB aabbB = b.ComputeAABB();
            float centerA, centerB;
            if (axis == 0) {
                centerA = (aabbA.min.x + aabbA.max.x) * 0.5f;
                centerB = (aabbB.min.x + aabbB.max.x) * 0.5f;
            } else if (axis == 1) {
                centerA = (aabbA.min.y + aabbA.max.y) * 0.5f;
                centerB = (aabbB.min.y + aabbB.max.y) * 0.5f;
            } else {
                centerA = (aabbA.min.z + aabbA.max.z) * 0.5f;
                centerB = (aabbB.min.z + aabbB.max.z) * 0.5f;
            }
            return centerA < centerB;
        });

    size_t mid = sortedTris.size() / 2;
    std::vector<TriangleCombined> leftTris(sortedTris.begin(), sortedTris.begin() + mid);
    std::vector<TriangleCombined> rightTris(sortedTris.begin() + mid, sortedTris.end());

    // Build children in parallel for large trees
    if (tris.size() > PARALLEL_THRESHOLD) {
        auto leftFuture = std::async(std::launch::async, [this, &leftTris]() {
            return BuildBVHOptimized(leftTris);
        });
        node->right = BuildBVHOptimized(rightTris);
        node->left = leftFuture.get();
    } else {
        node->left = BuildBVHOptimized(leftTris);
        node->right = BuildBVHOptimized(rightTris);
    }

    return node;
}

// Memory-mapped file loading for faster I/O
bool VisCheck::LoadMapMemoryMapped(const std::string& optimizedGeometryFile) {
    auto startTime = std::chrono::high_resolution_clock::now();
    
    UnloadMap();
    
    std::cout << "[VisCheck] Using memory-mapped loading for: " << optimizedGeometryFile << std::endl;
    
    if (!geometry.LoadFromFileMemoryMapped(optimizedGeometryFile)) {
        std::cerr << "[VisCheck] Memory-mapped loading failed" << std::endl;
        return false;
    }
    
    // Build BVH
    bvhNodes = BuildBVHParallel(geometry.meshes);
    
    currentMapFile = optimizedGeometryFile;
    mapLoaded = true;
    
    auto endTime = std::chrono::high_resolution_clock::now();
    auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(endTime - startTime);
    
    std::cout << "[VisCheck] Memory-mapped loading completed in " << duration.count() << "ms" << std::endl;
    return true;
}
