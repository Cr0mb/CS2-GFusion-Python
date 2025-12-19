#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/numpy.h>
#include "controller.h"
#include "service.h"
#include <vector>
#include <memory>

namespace py = pybind11;

// Wrapper class to manage driver connection
class NeacDriverManager {
private:
    HANDLE hPort;
    
public:
    NeacDriverManager() : hPort(INVALID_HANDLE_VALUE) {}
    
    ~NeacDriverManager() {
        disconnect();
    }
    
    bool start_driver() {
        return ::start_driver() == 0;
    }
    
    bool stop_driver() {
        return ::stop_driver() == 0;
    }
    
    bool connect() {
        hPort = connect_driver();
        return hPort != INVALID_HANDLE_VALUE;
    }
    
    void disconnect() {
        if (hPort != INVALID_HANDLE_VALUE) {
            CloseHandle(hPort);
            hPort = INVALID_HANDLE_VALUE;
        }
    }
    
    bool is_connected() const {
        return hPort != INVALID_HANDLE_VALUE;
    }
    
    uintptr_t get_process_base(uint32_t pid) {
        if (hPort == INVALID_HANDLE_VALUE) return 0;
        return reinterpret_cast<uintptr_t>(get_proc_base(hPort, pid));
    }
    
    py::bytes read_process_memory(uint32_t pid, uintptr_t address, uint32_t size) {
        if (hPort == INVALID_HANDLE_VALUE) return py::bytes();
        
        std::vector<uint8_t> buffer(size);
        DWORD bytes_read = read_proc_memory(hPort, pid, reinterpret_cast<PVOID>(address), static_cast<DWORD>(size), buffer.data());
        
        if (bytes_read > 0) {
            return py::bytes(reinterpret_cast<char*>(buffer.data()), bytes_read);
        }
        return py::bytes();
    }
    
    bool write_process_memory(uint32_t pid, uintptr_t address, py::bytes data) {
        if (hPort == INVALID_HANDLE_VALUE) return false;
        
        std::string str_data = data;
        DWORD bytes_written = write_proc_memory(hPort, pid, reinterpret_cast<PVOID>(address), 
                                               static_cast<DWORD>(str_data.size()), const_cast<char*>(str_data.data()));
        return bytes_written == static_cast<DWORD>(str_data.size());
    }
    
    template<typename T>
    T read_value(uint32_t pid, uintptr_t address) {
        if (hPort == INVALID_HANDLE_VALUE) return T{};
        
        T value;
        DWORD bytes_read = read_proc_memory(hPort, pid, reinterpret_cast<PVOID>(address), sizeof(T), &value);
        return (bytes_read == sizeof(T)) ? value : T{};
    }
    
    template<typename T>
    bool write_value(uint32_t pid, uintptr_t address, const T& value) {
        if (hPort == INVALID_HANDLE_VALUE) return false;
        
        DWORD bytes_written = write_proc_memory(hPort, pid, reinterpret_cast<PVOID>(address), 
                                               sizeof(T), const_cast<T*>(&value));
        return bytes_written == sizeof(T);
    }
    
    // Templated methods for different data types
    uint8_t read_uint8(uint32_t pid, uintptr_t address) { return read_value<uint8_t>(pid, address); }
    uint16_t read_uint16(uint32_t pid, uintptr_t address) { return read_value<uint16_t>(pid, address); }
    uint32_t read_uint32(uint32_t pid, uintptr_t address) { return read_value<uint32_t>(pid, address); }
    uint64_t read_uint64(uint32_t pid, uintptr_t address) { return read_value<uint64_t>(pid, address); }
    int8_t read_int8(uint32_t pid, uintptr_t address) { return read_value<int8_t>(pid, address); }
    int16_t read_int16(uint32_t pid, uintptr_t address) { return read_value<int16_t>(pid, address); }
    int32_t read_int32(uint32_t pid, uintptr_t address) { return read_value<int32_t>(pid, address); }
    int64_t read_int64(uint32_t pid, uintptr_t address) { return read_value<int64_t>(pid, address); }
    float read_float(uint32_t pid, uintptr_t address) { return read_value<float>(pid, address); }
    double read_double(uint32_t pid, uintptr_t address) { return read_value<double>(pid, address); }
    
    bool write_uint8(uint32_t pid, uintptr_t address, uint8_t value) { return write_value(pid, address, value); }
    bool write_uint16(uint32_t pid, uintptr_t address, uint16_t value) { return write_value(pid, address, value); }
    bool write_uint32(uint32_t pid, uintptr_t address, uint32_t value) { return write_value(pid, address, value); }
    bool write_uint64(uint32_t pid, uintptr_t address, uint64_t value) { return write_value(pid, address, value); }
    bool write_int8(uint32_t pid, uintptr_t address, int8_t value) { return write_value(pid, address, value); }
    bool write_int16(uint32_t pid, uintptr_t address, int16_t value) { return write_value(pid, address, value); }
    bool write_int32(uint32_t pid, uintptr_t address, int32_t value) { return write_value(pid, address, value); }
    bool write_int64(uint32_t pid, uintptr_t address, int64_t value) { return write_value(pid, address, value); }
    bool write_float(uint32_t pid, uintptr_t address, float value) { return write_value(pid, address, value); }
    bool write_double(uint32_t pid, uintptr_t address, double value) { return write_value(pid, address, value); }
    
    bool protect_process_memory(uint32_t pid, uintptr_t address, uint32_t size, uint32_t new_protect) {
        if (hPort == INVALID_HANDLE_VALUE) return false;
        return protect_memory(hPort, pid, reinterpret_cast<PVOID>(address), size, new_protect);
    }
    
    bool update_driver_state(uint8_t function_id, uint8_t state) {
        if (hPort == INVALID_HANDLE_VALUE) return false;
        return update_state(hPort, function_id, state);
    }
    
    bool kill_process_by_pid(uint32_t pid) {
        if (hPort == INVALID_HANDLE_VALUE) return false;
        return kill_process(hPort, pid);
    }
    
    py::bytes read_kernel_memory(uintptr_t address, uint32_t size) {
        if (hPort == INVALID_HANDLE_VALUE) return py::bytes();
        
        std::vector<uint8_t> buffer(size);
        bool success = kernel_read_data(hPort, buffer.data(), reinterpret_cast<PVOID>(address), size);
        
        if (success) {
            return py::bytes(reinterpret_cast<char*>(buffer.data()), size);
        }
        return py::bytes();
    }
    
    bool write_kernel_memory(uintptr_t dst_address, py::bytes data) {
        if (hPort == INVALID_HANDLE_VALUE) return false;
        
        std::string str_data = data;
        return kernel_write_data(hPort, reinterpret_cast<PVOID>(dst_address), 
                               const_cast<char*>(str_data.data()), static_cast<DWORD>(str_data.size()));
    }
    
    py::list get_ssdt_table() {
        if (hPort == INVALID_HANDLE_VALUE) return py::list();
        
        PVOID ssdt_items[0x1000];
        bool success = get_ssdt_items(hPort, ssdt_items, sizeof(ssdt_items));
        
        py::list result;
        if (success) {
            for (int i = 0; i < 0x1000; i++) {
                result.append(reinterpret_cast<uintptr_t>(ssdt_items[i]));
            }
        }
        return result;
    }
};

PYBIND11_MODULE(neac_controller, m) {
    m.doc() = "NeacController Python Bindings - Windows Kernel Driver Controller";
    
    py::class_<NeacDriverManager>(m, "NeacDriverManager")
        .def(py::init<>())
        .def("start_driver", &NeacDriverManager::start_driver, 
             "Start the NeacSafe64 driver service")
        .def("stop_driver", &NeacDriverManager::stop_driver, 
             "Stop the NeacSafe64 driver service")
        .def("connect", &NeacDriverManager::connect, 
             "Connect to the driver communication port")
        .def("disconnect", &NeacDriverManager::disconnect, 
             "Disconnect from the driver")
        .def("is_connected", &NeacDriverManager::is_connected, 
             "Check if connected to the driver")
        .def("get_process_base", &NeacDriverManager::get_process_base, 
             "Get the base address of a process by PID",
             py::arg("pid"))
        .def("read_process_memory", &NeacDriverManager::read_process_memory,
             "Read memory from a process",
             py::arg("pid"), py::arg("address"), py::arg("size"))
        .def("write_process_memory", &NeacDriverManager::write_process_memory,
             "Write memory to a process",
             py::arg("pid"), py::arg("address"), py::arg("data"))
        
        // Typed read methods
        .def("read_uint8", &NeacDriverManager::read_uint8, py::arg("pid"), py::arg("address"))
        .def("read_uint16", &NeacDriverManager::read_uint16, py::arg("pid"), py::arg("address"))
        .def("read_uint32", &NeacDriverManager::read_uint32, py::arg("pid"), py::arg("address"))
        .def("read_uint64", &NeacDriverManager::read_uint64, py::arg("pid"), py::arg("address"))
        .def("read_int8", &NeacDriverManager::read_int8, py::arg("pid"), py::arg("address"))
        .def("read_int16", &NeacDriverManager::read_int16, py::arg("pid"), py::arg("address"))
        .def("read_int32", &NeacDriverManager::read_int32, py::arg("pid"), py::arg("address"))
        .def("read_int64", &NeacDriverManager::read_int64, py::arg("pid"), py::arg("address"))
        .def("read_float", &NeacDriverManager::read_float, py::arg("pid"), py::arg("address"))
        .def("read_double", &NeacDriverManager::read_double, py::arg("pid"), py::arg("address"))
        
        // Typed write methods
        .def("write_uint8", &NeacDriverManager::write_uint8, py::arg("pid"), py::arg("address"), py::arg("value"))
        .def("write_uint16", &NeacDriverManager::write_uint16, py::arg("pid"), py::arg("address"), py::arg("value"))
        .def("write_uint32", &NeacDriverManager::write_uint32, py::arg("pid"), py::arg("address"), py::arg("value"))
        .def("write_uint64", &NeacDriverManager::write_uint64, py::arg("pid"), py::arg("address"), py::arg("value"))
        .def("write_int8", &NeacDriverManager::write_int8, py::arg("pid"), py::arg("address"), py::arg("value"))
        .def("write_int16", &NeacDriverManager::write_int16, py::arg("pid"), py::arg("address"), py::arg("value"))
        .def("write_int32", &NeacDriverManager::write_int32, py::arg("pid"), py::arg("address"), py::arg("value"))
        .def("write_int64", &NeacDriverManager::write_int64, py::arg("pid"), py::arg("address"), py::arg("value"))
        .def("write_float", &NeacDriverManager::write_float, py::arg("pid"), py::arg("address"), py::arg("value"))
        .def("write_double", &NeacDriverManager::write_double, py::arg("pid"), py::arg("address"), py::arg("value"))
        
        .def("protect_process_memory", &NeacDriverManager::protect_process_memory,
             "Change memory protection of a process memory region",
             py::arg("pid"), py::arg("address"), py::arg("size"), py::arg("new_protect"))
        .def("update_driver_state", &NeacDriverManager::update_driver_state,
             "Update driver state",
             py::arg("function_id"), py::arg("state"))
        .def("kill_process_by_pid", &NeacDriverManager::kill_process_by_pid,
             "Kill a process by PID",
             py::arg("pid"))
        .def("read_kernel_memory", &NeacDriverManager::read_kernel_memory,
             "Read kernel memory",
             py::arg("address"), py::arg("size"))
        .def("write_kernel_memory", &NeacDriverManager::write_kernel_memory,
             "Write kernel memory",
             py::arg("dst_address"), py::arg("data"))
        .def("get_ssdt_table", &NeacDriverManager::get_ssdt_table,
             "Get System Service Descriptor Table items");
    
    // Memory protection constants
    m.attr("PAGE_NOACCESS") = 0x01;
    m.attr("PAGE_READONLY") = 0x02;
    m.attr("PAGE_READWRITE") = 0x04;
    m.attr("PAGE_WRITECOPY") = 0x08;
    m.attr("PAGE_EXECUTE") = 0x10;
    m.attr("PAGE_EXECUTE_READ") = 0x20;
    m.attr("PAGE_EXECUTE_READWRITE") = 0x40;
    m.attr("PAGE_EXECUTE_WRITECOPY") = 0x80;
    m.attr("PAGE_GUARD") = 0x100;
    m.attr("PAGE_NOCACHE") = 0x200;
    m.attr("PAGE_WRITECOMBINE") = 0x400;
}
