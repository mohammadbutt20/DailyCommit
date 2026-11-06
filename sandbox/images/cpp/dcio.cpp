#include "dcio.hpp"

#include <fstream>
#include <iterator>
#include <nlohmann/json.hpp>
#include <stdexcept>
#include <vector>

using nlohmann::json;

namespace dcio {

static json g_cases;

void load(const char* path) {
    std::ifstream in(path);
    if (!in) throw std::runtime_error("cannot open inputs");
    g_cases = json::parse(std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>());
}

std::size_t cases() { return g_cases.size(); }

template <class T>
T get(std::size_t i, const char* name) {
    return g_cases.at(i).at(name).get<T>();
}

template <class T>
std::string dump(const T& value) {
    return json(value).dump(-1, ' ', false, json::error_handler_t::replace);
}

#define DCIO_TYPE(T)                                                         \
    template T get<T>(std::size_t, const char*);                             \
    template std::vector<T> get<std::vector<T>>(std::size_t, const char*);   \
    template std::vector<std::vector<T>> get<std::vector<std::vector<T>>>(   \
        std::size_t, const char*);                                           \
    template std::string dump<T>(const T&);                                  \
    template std::string dump<std::vector<T>>(const std::vector<T>&);        \
    template std::string dump<std::vector<std::vector<T>>>(                  \
        const std::vector<std::vector<T>>&);

DCIO_TYPE(int)
DCIO_TYPE(long long)
DCIO_TYPE(double)
DCIO_TYPE(bool)
DCIO_TYPE(std::string)

}  // namespace dcio
