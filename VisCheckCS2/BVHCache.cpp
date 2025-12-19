#include "BVHCache.h"
#include "VisCheck.h"
#include "PerformanceConfig.h"
#include <fstream>
#include <iostream>
#include <filesystem>
#include <algorithm>

// CacheEntry Implementation
bool CacheEntry::IsValid(const std::string& originalFile) const {
    if (!std::filesystem::exists(originalFile)) {
        return false;
    }
    
    try {
        auto currentTime = std::filesystem::last_write_time(originalFile);
        auto currentSize = std::filesystem::file_size(originalFile);
        
        // Simple comparison - just check file size for now
        return currentSize == fileSize;
    }
    catch (...) {
        return false;
    }
}

// PersistentBVHCache Implementation
PersistentBVHCache::PersistentBVHCache(const std::string& cacheDir) : cacheDirectory(cacheDir) {
    std::filesystem::create_directories(cacheDirectory);
    LoadCacheIndex();
}

PersistentBVHCache::~PersistentBVHCache() {
    SaveCacheIndex();
}

std::string PersistentBVHCache::GetCacheFilePath(const std::string& mapFile) const {
    std::string filename = std::filesystem::path(mapFile).filename().string();
    return (std::filesystem::path(cacheDirectory) / (filename + ".bvhcache")).string();
}

std::string PersistentBVHCache::GetIndexFilePath() const {
    return (std::filesystem::path(cacheDirectory) / "cache_index.bin").string();
}

size_t PersistentBVHCache::ComputeFileHash(const std::string& filePath) const {
    try {
        auto fileSize = std::filesystem::file_size(filePath);
        auto lastWrite = std::filesystem::last_write_time(filePath);
        
        // Simple hash based on size and path
        std::hash<std::string> pathHasher;
        return pathHasher(filePath) ^ fileSize;
    }
    catch (...) {
        return 0;
    }
}

void PersistentBVHCache::LoadCacheIndex() {
    std::string indexPath = GetIndexFilePath();
    if (!std::filesystem::exists(indexPath)) {
        return;
    }
    
    std::ifstream indexFile(indexPath, std::ios::binary);
    if (!indexFile) {
        return;
    }
    
    size_t entryCount;
    indexFile.read(reinterpret_cast<char*>(&entryCount), sizeof(size_t));
    
    for (size_t i = 0; i < entryCount; ++i) {
        std::string key;
        size_t keyLength;
        indexFile.read(reinterpret_cast<char*>(&keyLength), sizeof(size_t));
        key.resize(keyLength);
        indexFile.read(&key[0], keyLength);
        
        CacheEntry entry;
        
        // Read file path
        size_t filePathLength;
        indexFile.read(reinterpret_cast<char*>(&filePathLength), sizeof(size_t));
        entry.filePath.resize(filePathLength);
        indexFile.read(&entry.filePath[0], filePathLength);
        
        // Skip timestamp for compatibility (just set to min)
        time_t timeT;
        indexFile.read(reinterpret_cast<char*>(&timeT), sizeof(time_t));
        entry.lastModified = std::filesystem::file_time_type::min();
        
        indexFile.read(reinterpret_cast<char*>(&entry.fileSize), sizeof(size_t));
        indexFile.read(reinterpret_cast<char*>(&entry.dataHash), sizeof(size_t));
        
        cacheIndex[key] = entry;
    }
    
    std::cout << "[BVHCache] Loaded " << entryCount << " cache entries" << std::endl;
}

void PersistentBVHCache::SaveCacheIndex() {
    std::ofstream indexFile(GetIndexFilePath(), std::ios::binary);
    if (!indexFile) {
        return;
    }
    
    size_t entryCount = cacheIndex.size();
    indexFile.write(reinterpret_cast<const char*>(&entryCount), sizeof(size_t));
    
    for (const auto& [key, entry] : cacheIndex) {
        // Write key
        size_t keyLength = key.size();
        indexFile.write(reinterpret_cast<const char*>(&keyLength), sizeof(size_t));
        indexFile.write(key.c_str(), keyLength);
        
        // Write entry
        size_t filePathLength = entry.filePath.size();
        indexFile.write(reinterpret_cast<const char*>(&filePathLength), sizeof(size_t));
        indexFile.write(entry.filePath.c_str(), filePathLength);
        
        // Write timestamp as time_t for compatibility
        auto timeT = std::chrono::system_clock::to_time_t(std::chrono::system_clock::now());
        indexFile.write(reinterpret_cast<const char*>(&timeT), sizeof(time_t));
        
        indexFile.write(reinterpret_cast<const char*>(&entry.fileSize), sizeof(size_t));
        indexFile.write(reinterpret_cast<const char*>(&entry.dataHash), sizeof(size_t));
    }
}

void PersistentBVHCache::SerializeBVHNode(std::ofstream& out, const BVHNode* node) const {
    if (!node) {
        bool isNull = true;
        out.write(reinterpret_cast<const char*>(&isNull), sizeof(bool));
        return;
    }
    
    bool isNull = false;
    out.write(reinterpret_cast<const char*>(&isNull), sizeof(bool));
    
    // Serialize AABB bounds
    out.write(reinterpret_cast<const char*>(&node->bounds), sizeof(AABB));
    
    // Serialize triangle count
    size_t triangleCount = node->triangles.size();
    out.write(reinterpret_cast<const char*>(&triangleCount), sizeof(size_t));
    
    // Serialize triangles
    for (const auto& triangle : node->triangles) {
        out.write(reinterpret_cast<const char*>(&triangle), sizeof(TriangleCombined));
    }
    
    // Serialize children (recursive)
    SerializeBVHNode(out, node->left.get());
    SerializeBVHNode(out, node->right.get());
}

std::unique_ptr<BVHNode> PersistentBVHCache::DeserializeBVHNode(std::ifstream& in) const {
    bool isNull;
    in.read(reinterpret_cast<char*>(&isNull), sizeof(bool));
    
    if (isNull) {
        return nullptr;
    }
    
    auto node = std::make_unique<BVHNode>();
    
    // Deserialize AABB bounds
    in.read(reinterpret_cast<char*>(&node->bounds), sizeof(AABB));
    
    // Deserialize triangle count and triangles
    size_t triangleCount;
    in.read(reinterpret_cast<char*>(&triangleCount), sizeof(size_t));
    
    node->triangles.resize(triangleCount);
    for (size_t i = 0; i < triangleCount; ++i) {
        in.read(reinterpret_cast<char*>(&node->triangles[i]), sizeof(TriangleCombined));
    }
    
    // Deserialize children (recursive)
    node->left = DeserializeBVHNode(in);
    node->right = DeserializeBVHNode(in);
    
    return node;
}

bool PersistentBVHCache::Store(const std::string& mapFile, const std::vector<std::unique_ptr<BVHNode>>& nodes) {
    std::lock_guard<std::mutex> lock(cacheMutex);
    
    std::string cacheFilePath = GetCacheFilePath(mapFile);
    std::ofstream file(cacheFilePath, std::ios::binary);
    if (!file) {
        return false;
    }
    
    // Write header
    uint32_t version = 1;
    uint32_t nodeCount = static_cast<uint32_t>(nodes.size());
    
    file.write(reinterpret_cast<const char*>(&version), sizeof(version));
    file.write(reinterpret_cast<const char*>(&nodeCount), sizeof(nodeCount));
    
    // Write nodes
    for (const auto& node : nodes) {
        SerializeBVHNode(file, node.get());
    }
    
    // Update cache index
    CacheEntry entry;
    entry.filePath = mapFile;
    entry.lastModified = std::filesystem::last_write_time(mapFile);
    entry.fileSize = std::filesystem::file_size(mapFile);
    entry.dataHash = ComputeFileHash(mapFile);
    
    cacheIndex[mapFile] = entry;
    
    std::cout << "[BVHCache] Stored " << nodes.size() << " nodes for " << mapFile << std::endl;
    return true;
}

bool PersistentBVHCache::Load(const std::string& mapFile, std::vector<std::unique_ptr<BVHNode>>& nodes) {
    std::lock_guard<std::mutex> lock(cacheMutex);
    
    auto it = cacheIndex.find(mapFile);
    if (it == cacheIndex.end() || !it->second.IsValid(mapFile)) {
        return false;
    }
    
    std::string cacheFilePath = GetCacheFilePath(mapFile);
    std::ifstream file(cacheFilePath, std::ios::binary);
    if (!file) {
        return false;
    }
    
    // Read header
    uint32_t version, nodeCount;
    file.read(reinterpret_cast<char*>(&version), sizeof(version));
    file.read(reinterpret_cast<char*>(&nodeCount), sizeof(nodeCount));
    
    if (version != 1) {
        std::cout << "[BVHCache] Version mismatch, cache invalid" << std::endl;
        return false;
    }
    
    // Read nodes
    nodes.clear();
    nodes.reserve(nodeCount);
    
    for (uint32_t i = 0; i < nodeCount; ++i) {
        auto node = DeserializeBVHNode(file);
        if (node) {
            nodes.push_back(std::move(node));
        }
    }
    
    std::cout << "[BVHCache] Loaded " << nodeCount << " cached nodes for " << mapFile << std::endl;
    return true;
}

bool PersistentBVHCache::IsValid(const std::string& mapFile) const {
    std::lock_guard<std::mutex> lock(cacheMutex);
    auto it = cacheIndex.find(mapFile);
    return it != cacheIndex.end() && it->second.IsValid(mapFile);
}

void PersistentBVHCache::Clear() {
    std::lock_guard<std::mutex> lock(cacheMutex);
    
    // Remove all cache files
    for (const auto& [mapFile, entry] : cacheIndex) {
        std::string cacheFilePath = GetCacheFilePath(mapFile);
        std::filesystem::remove(cacheFilePath);
    }
    
    // Clear index
    cacheIndex.clear();
    std::filesystem::remove(GetIndexFilePath());
    
    std::cout << "[BVHCache] Cleared all cache files" << std::endl;
}

void PersistentBVHCache::CleanOldEntries(std::chrono::hours maxAge) {
    std::lock_guard<std::mutex> lock(cacheMutex);
    
    std::vector<std::string> toRemove;
    
    for (const auto& [mapFile, entry] : cacheIndex) {
        // Simple cleanup - if file doesn't exist or is invalid, mark for removal
        if (!std::filesystem::exists(entry.filePath) || !entry.IsValid(entry.filePath)) {
            toRemove.push_back(mapFile);
        }
    }
    
    for (const auto& mapFile : toRemove) {
        std::string cacheFilePath = GetCacheFilePath(mapFile);
        std::filesystem::remove(cacheFilePath);
        cacheIndex.erase(mapFile);
    }
    
    if (!toRemove.empty()) {
        std::cout << "[BVHCache] Cleaned " << toRemove.size() << " old cache entries" << std::endl;
    }
}

size_t PersistentBVHCache::GetCacheSize() const {
    std::lock_guard<std::mutex> lock(cacheMutex);
    return cacheIndex.size();
}

std::vector<std::string> PersistentBVHCache::GetCachedFiles() const {
    std::lock_guard<std::mutex> lock(cacheMutex);
    
    std::vector<std::string> files;
    files.reserve(cacheIndex.size());
    
    for (const auto& [mapFile, entry] : cacheIndex) {
        files.push_back(mapFile);
    }
    
    return files;
}

// BVHNodePool Implementation
BVHNodePool::BVHNodePool() : poolSize(0) {}

BVHNodePool::~BVHNodePool() {
    Clear();
}

std::unique_ptr<BVHNode> BVHNodePool::Acquire() {
    std::lock_guard<std::mutex> lock(poolMutex);
    
    if (!pool.empty()) {
        auto node = std::move(pool.back());
        pool.pop_back();
        poolSize--;
        return node;
    }
    
    return std::make_unique<BVHNode>();
}

void BVHNodePool::Release(std::unique_ptr<BVHNode> node) {
    if (!node) return;
    
    std::lock_guard<std::mutex> lock(poolMutex);
    
    if (poolSize < MAX_POOL_SIZE) {
        pool.push_back(std::move(node));
        poolSize++;
    }
    // If pool is full, just let the unique_ptr destruct naturally
}

void BVHNodePool::Clear() {
    std::lock_guard<std::mutex> lock(poolMutex);
    pool.clear();
    poolSize = 0;
}

size_t BVHNodePool::Size() const {
    std::lock_guard<std::mutex> lock(poolMutex);
    return poolSize;
}
