// JSON input/output for the generated C++ harness. Compiled once into the image (dcio.o) so
// submissions never pay for nlohmann/json's templates at compile time. Only the value types of
// the problem format exist: int, long long, double, bool, string, and 1-D/2-D vectors of them.
#pragma once

#include <cstddef>
#include <string>

namespace dcio {

// Reads the JSON array of test inputs. Throws on malformed input.
void load(const char* path);
std::size_t cases();

// Argument `name` of test `i`, converted to T.
template <class T>
T get(std::size_t i, const char* name);

// Compact JSON for a value. Invalid UTF-8 in strings is replaced, never thrown.
template <class T>
std::string dump(const T& value);

}  // namespace dcio
