#include "OptimizedGeometry.h"
#define NOMINMAX  // Fix std::min conflicts
#include "Parser.h"
#include <fstream>
#include <iostream>
#include <memory>
#include <algorithm>
#ifdef _WIN32
    #include <windows.h>
#else
    #include <sys/mman.h>
    #include <sys/stat.h>
    #include <fcntl.h>
    #include <unistd.h>
#endif

bool OptimizedGeometry::CreateOptimizedFile(const std::string& rawFile, const std::string& optimizedFile) {

    Parser parser(rawFile);
    meshes = parser.GetCombinedList();

    std::ofstream out(optimizedFile, std::ios::binary);
    if (!out) {
        std::cerr << "�� ������� ������� ���� ��� ������: " << optimizedFile << std::endl;
        return false;
    }

    size_t numMeshes = meshes.size();
    out.write(reinterpret_cast<const char*>(&numMeshes), sizeof(size_t));
    for (const auto& mesh : meshes) {

        size_t numTris = mesh.size();
        out.write(reinterpret_cast<const char*>(&numTris), sizeof(size_t));
        for (const auto& tri : mesh) {
            out.write(reinterpret_cast<const char*>(&tri.v0), sizeof(Vector3));
            out.write(reinterpret_cast<const char*>(&tri.v1), sizeof(Vector3));
            out.write(reinterpret_cast<const char*>(&tri.v2), sizeof(Vector3));
        }
    }
    out.close();
    return true;
}

bool OptimizedGeometry::CreateOptimizedFileBuffered(const std::string& rawFile, const std::string& optimizedFile, size_t bufferSize) {
    Parser parser(rawFile);
    meshes = parser.GetCombinedList();

    std::ofstream out(optimizedFile, std::ios::binary);
    if (!out) {
        std::cerr << "Failed to create file: " << optimizedFile << std::endl;
        return false;
    }
    
    // Set buffer size for better I/O performance
    auto buffer = std::make_unique<char[]>(bufferSize);
    out.rdbuf()->pubsetbuf(buffer.get(), bufferSize);

    size_t numMeshes = meshes.size();
    out.write(reinterpret_cast<const char*>(&numMeshes), sizeof(size_t));
    
    for (const auto& mesh : meshes) {
        size_t numTris = mesh.size();
        out.write(reinterpret_cast<const char*>(&numTris), sizeof(size_t));
        
        // Write triangles in batches for better cache performance
        constexpr size_t BATCH_SIZE = 1000;
        for (size_t i = 0; i < numTris; i += BATCH_SIZE) {
            size_t batchEnd = std::min(i + BATCH_SIZE, numTris);
            for (size_t j = i; j < batchEnd; ++j) {
                const auto& tri = mesh[j];
                out.write(reinterpret_cast<const char*>(&tri.v0), sizeof(Vector3));
                out.write(reinterpret_cast<const char*>(&tri.v1), sizeof(Vector3));
                out.write(reinterpret_cast<const char*>(&tri.v2), sizeof(Vector3));
            }
        }
    }
    
    out.close();
    return true;
}

bool OptimizedGeometry::LoadFromFile(const std::string& optimizedFile) {
    std::ifstream in(optimizedFile, std::ios::binary);
    if (!in) {
        std::cerr << "�� ������� ������� ���������������� ����: " << optimizedFile << std::endl;
        return false;
    }
    meshes.clear();
    size_t numMeshes;
    in.read(reinterpret_cast<char*>(&numMeshes), sizeof(size_t));
    for (size_t i = 0; i < numMeshes; ++i) {
        size_t numTris;
        in.read(reinterpret_cast<char*>(&numTris), sizeof(size_t));
        std::vector<TriangleCombined> mesh;
        mesh.resize(numTris);
        for (size_t j = 0; j < numTris; ++j) {
            in.read(reinterpret_cast<char*>(&mesh[j].v0), sizeof(Vector3));
            in.read(reinterpret_cast<char*>(&mesh[j].v1), sizeof(Vector3));
            in.read(reinterpret_cast<char*>(&mesh[j].v2), sizeof(Vector3));
        }
        meshes.push_back(mesh);
    }
    in.close();
    return true;
}

bool OptimizedGeometry::LoadFromFileBuffered(const std::string& optimizedFile, size_t bufferSize) {
    std::ifstream in(optimizedFile, std::ios::binary);
    if (!in) {
        std::cerr << "Failed to open optimized file: " << optimizedFile << std::endl;
        return false;
    }
    
    // Set buffer size for better I/O performance
    auto buffer = std::make_unique<char[]>(bufferSize);
    in.rdbuf()->pubsetbuf(buffer.get(), bufferSize);
    
    meshes.clear();
    size_t numMeshes;
    in.read(reinterpret_cast<char*>(&numMeshes), sizeof(size_t));
    
    meshes.reserve(numMeshes);
    
    for (size_t i = 0; i < numMeshes; ++i) {
        size_t numTris;
        in.read(reinterpret_cast<char*>(&numTris), sizeof(size_t));
        
        std::vector<TriangleCombined> mesh;
        mesh.reserve(numTris);
        
        // Read triangles in batches for better cache performance
        constexpr size_t BATCH_SIZE = 1000;
        for (size_t j = 0; j < numTris; j += BATCH_SIZE) {
            size_t batchEnd = std::min(j + BATCH_SIZE, numTris);
            size_t batchSize = batchEnd - j;
            
            // Resize and read batch
            size_t oldSize = mesh.size();
            mesh.resize(oldSize + batchSize);
            
            for (size_t k = 0; k < batchSize; ++k) {
                auto& tri = mesh[oldSize + k];
                in.read(reinterpret_cast<char*>(&tri.v0), sizeof(Vector3));
                in.read(reinterpret_cast<char*>(&tri.v1), sizeof(Vector3));
                in.read(reinterpret_cast<char*>(&tri.v2), sizeof(Vector3));
            }
        }
        
        meshes.push_back(std::move(mesh));
    }
    
    in.close();
    return true;
}

#ifdef _WIN32
bool OptimizedGeometry::LoadFromFileMemoryMapped(const std::string& optimizedFile) {
    HANDLE hFile = CreateFileA(optimizedFile.c_str(), GENERIC_READ, FILE_SHARE_READ, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (hFile == INVALID_HANDLE_VALUE) {
        std::cerr << "Failed to open file for memory mapping: " << optimizedFile << std::endl;
        return false;
    }
    
    LARGE_INTEGER fileSize;
    if (!GetFileSizeEx(hFile, &fileSize)) {
        CloseHandle(hFile);
        return false;
    }
    
    HANDLE hMapFile = CreateFileMappingA(hFile, nullptr, PAGE_READONLY, fileSize.HighPart, fileSize.LowPart, nullptr);
    if (!hMapFile) {
        CloseHandle(hFile);
        return false;
    }
    
    const char* data = static_cast<const char*>(MapViewOfFile(hMapFile, FILE_MAP_READ, 0, 0, 0));
    if (!data) {
        CloseHandle(hMapFile);
        CloseHandle(hFile);
        return false;
    }
    
    try {
        meshes.clear();
        const char* ptr = data;
        
        size_t numMeshes = *reinterpret_cast<const size_t*>(ptr);
        ptr += sizeof(size_t);
        
        meshes.reserve(numMeshes);
        
        for (size_t i = 0; i < numMeshes; ++i) {
            size_t numTris = *reinterpret_cast<const size_t*>(ptr);
            ptr += sizeof(size_t);
            
            std::vector<TriangleCombined> mesh;
            mesh.reserve(numTris);
            
            for (size_t j = 0; j < numTris; ++j) {
                TriangleCombined tri;
                tri.v0 = *reinterpret_cast<const Vector3*>(ptr);
                ptr += sizeof(Vector3);
                tri.v1 = *reinterpret_cast<const Vector3*>(ptr);
                ptr += sizeof(Vector3);
                tri.v2 = *reinterpret_cast<const Vector3*>(ptr);
                ptr += sizeof(Vector3);
                
                mesh.push_back(tri);
            }
            
            meshes.push_back(std::move(mesh));
        }
    }
    catch (...) {
        UnmapViewOfFile(data);
        CloseHandle(hMapFile);
        CloseHandle(hFile);
        return false;
    }
    
    UnmapViewOfFile(data);
    CloseHandle(hMapFile);
    CloseHandle(hFile);
    return true;
}
#else
bool OptimizedGeometry::LoadFromFileMemoryMapped(const std::string& optimizedFile) {
    int fd = open(optimizedFile.c_str(), O_RDONLY);
    if (fd == -1) {
        std::cerr << "Failed to open file for memory mapping: " << optimizedFile << std::endl;
        return false;
    }
    
    struct stat sb;
    if (fstat(fd, &sb) == -1) {
        close(fd);
        return false;
    }
    
    const char* data = static_cast<const char*>(mmap(nullptr, sb.st_size, PROT_READ, MAP_PRIVATE, fd, 0));
    if (data == MAP_FAILED) {
        close(fd);
        return false;
    }
    
    try {
        meshes.clear();
        const char* ptr = data;
        
        size_t numMeshes = *reinterpret_cast<const size_t*>(ptr);
        ptr += sizeof(size_t);
        
        meshes.reserve(numMeshes);
        
        for (size_t i = 0; i < numMeshes; ++i) {
            size_t numTris = *reinterpret_cast<const size_t*>(ptr);
            ptr += sizeof(size_t);
            
            std::vector<TriangleCombined> mesh;
            mesh.reserve(numTris);
            
            for (size_t j = 0; j < numTris; ++j) {
                TriangleCombined tri;
                tri.v0 = *reinterpret_cast<const Vector3*>(ptr);
                ptr += sizeof(Vector3);
                tri.v1 = *reinterpret_cast<const Vector3*>(ptr);
                ptr += sizeof(Vector3);
                tri.v2 = *reinterpret_cast<const Vector3*>(ptr);
                ptr += sizeof(Vector3);
                
                mesh.push_back(tri);
            }
            
            meshes.push_back(std::move(mesh));
        }
    }
    catch (...) {
        munmap(const_cast<char*>(data), sb.st_size);
        close(fd);
        return false;
    }
    
    munmap(const_cast<char*>(data), sb.st_size);
    close(fd);
    return true;
}
#endif

bool OptimizedGeometry::LoadPartial(const std::string& optimizedFile, size_t startMesh, size_t meshCount) {
    std::ifstream in(optimizedFile, std::ios::binary);
    if (!in) {
        std::cerr << "Failed to open optimized file: " << optimizedFile << std::endl;
        return false;
    }
    
    meshes.clear();
    size_t numMeshes;
    in.read(reinterpret_cast<char*>(&numMeshes), sizeof(size_t));
    
    if (startMesh >= numMeshes) return false;
    
    size_t endMesh = std::min(startMesh + meshCount, numMeshes);
    meshes.reserve(endMesh - startMesh);
    
    // Skip to starting mesh
    for (size_t i = 0; i < startMesh; ++i) {
        size_t numTris;
        in.read(reinterpret_cast<char*>(&numTris), sizeof(size_t));
        in.seekg(numTris * 3 * sizeof(Vector3), std::ios::cur);
    }
    
    // Load requested meshes
    for (size_t i = startMesh; i < endMesh; ++i) {
        size_t numTris;
        in.read(reinterpret_cast<char*>(&numTris), sizeof(size_t));
        
        std::vector<TriangleCombined> mesh;
        mesh.resize(numTris);
        
        for (size_t j = 0; j < numTris; ++j) {
            in.read(reinterpret_cast<char*>(&mesh[j].v0), sizeof(Vector3));
            in.read(reinterpret_cast<char*>(&mesh[j].v1), sizeof(Vector3));
            in.read(reinterpret_cast<char*>(&mesh[j].v2), sizeof(Vector3));
        }
        
        meshes.push_back(std::move(mesh));
    }
    
    in.close();
    return true;
}

size_t OptimizedGeometry::GetMeshCount(const std::string& optimizedFile) const {
    std::ifstream in(optimizedFile, std::ios::binary);
    if (!in) return 0;
    
    size_t numMeshes;
    in.read(reinterpret_cast<char*>(&numMeshes), sizeof(size_t));
    return numMeshes;
}

size_t OptimizedGeometry::GetTriangleCount() const {
    size_t count = 0;
    for (const auto& mesh : meshes) {
        count += mesh.size();
    }
    return count;
}

size_t OptimizedGeometry::GetMemoryUsage() const {
    size_t usage = sizeof(*this);
    usage += meshes.capacity() * sizeof(std::vector<TriangleCombined>);
    for (const auto& mesh : meshes) {
        usage += mesh.capacity() * sizeof(TriangleCombined);
    }
    return usage;
}

void OptimizedGeometry::Clear() {
    meshes.clear();
    meshes.shrink_to_fit();
}
