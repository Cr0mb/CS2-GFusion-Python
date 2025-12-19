#pragma once
#include <string>
#include <vector>
#include <memory>
#include "Math.hpp"

class OptimizedGeometry {
public:
    std::vector<std::vector<TriangleCombined>> meshes;

    // Original methods
    bool LoadFromFile(const std::string& optimizedFile);
    bool CreateOptimizedFile(const std::string& rawFile, const std::string& optimizedFile);
    
    // Optimized methods
    bool LoadFromFileBuffered(const std::string& optimizedFile, size_t bufferSize = 1024 * 1024); // 1MB buffer
    bool LoadFromFileMemoryMapped(const std::string& optimizedFile);
    bool CreateOptimizedFileBuffered(const std::string& rawFile, const std::string& optimizedFile, size_t bufferSize = 1024 * 1024);
    
    // Lazy loading support
    bool LoadPartial(const std::string& optimizedFile, size_t startMesh, size_t meshCount);
    size_t GetMeshCount(const std::string& optimizedFile) const;
    
    // Statistics
    size_t GetTriangleCount() const;
    size_t GetMemoryUsage() const;
    
    // Clear data
    void Clear();
};
