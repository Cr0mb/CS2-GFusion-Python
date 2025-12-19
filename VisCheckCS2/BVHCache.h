#pragma once
#include <string>
#include <vector>
#include <memory>
#include <unordered_map>
#include <mutex>
#include <fstream>
#include <filesystem>
#include <chrono>
#include "Math.hpp"

// Forward declarations
struct BVHNode;

struct CacheEntry {
    std::string filePath;
    std::filesystem::file_time_type lastModified;
    size_t fileSize;
    size_t dataHash;
    
    bool IsValid(const std::string& originalFile) const;
};

class PersistentBVHCache {
private:
    std::string cacheDirectory;
    std::unordered_map<std::string, CacheEntry> cacheIndex;
    mutable std::mutex cacheMutex;
    
    // Cache management
    void LoadCacheIndex();
    void SaveCacheIndex();
    std::string GetCacheFilePath(const std::string& mapFile) const;
    std::string GetIndexFilePath() const;
    size_t ComputeFileHash(const std::string& filePath) const;
    
    // BVH serialization
    void SerializeBVHNode(std::ofstream& out, const BVHNode* node) const;
    std::unique_ptr<BVHNode> DeserializeBVHNode(std::ifstream& in) const;
    
public:
    PersistentBVHCache(const std::string& cacheDir = "cache");
    ~PersistentBVHCache();
    
    // Cache operations
    bool Store(const std::string& mapFile, const std::vector<std::unique_ptr<BVHNode>>& nodes);
    bool Load(const std::string& mapFile, std::vector<std::unique_ptr<BVHNode>>& nodes);
    bool IsValid(const std::string& mapFile) const;
    void Clear();
    void CleanOldEntries(std::chrono::hours maxAge = std::chrono::hours(24 * 7)); // Default: 1 week
    
    // Statistics
    size_t GetCacheSize() const;
    std::vector<std::string> GetCachedFiles() const;
};

// Memory pool for BVH nodes to reduce allocation overhead
class BVHNodePool {
private:
    std::vector<std::unique_ptr<BVHNode>> pool;
    mutable std::mutex poolMutex;
    size_t poolSize;
    static constexpr size_t MAX_POOL_SIZE = 10000;
    
public:
    BVHNodePool();
    ~BVHNodePool();
    
    std::unique_ptr<BVHNode> Acquire();
    void Release(std::unique_ptr<BVHNode> node);
    void Clear();
    size_t Size() const;
};
