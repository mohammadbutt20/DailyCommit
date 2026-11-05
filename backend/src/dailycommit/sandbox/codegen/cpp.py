"""Starter code and test harness for C++ submissions.

The user's file is solution.cpp (`class Solution` with the problem's method); the harness
main.cpp #includes it, so compiler messages point at solution.cpp lines. <bits/stdc++.h> and
`using namespace std` are in scope, as on most judges. JSON goes through the image's prebuilt
dcio library (sandbox/images/cpp/dcio.hpp), never compiled per submission.
"""

from dailycommit.problems.schema import Signature, parse_type

_CPP_TYPES = {
    "int": "int",
    "long": "long long",
    "double": "double",
    "bool": "bool",
    "string": "string",
}


def cpp_type(type_name: str) -> str:
    base, depth = parse_type(type_name)
    t = _CPP_TYPES[base]
    for _ in range(depth):
        t = f"vector<{t}>"
    return t


def _param(type_name: str, name: str) -> str:
    _, depth = parse_type(type_name)
    return f"{cpp_type(type_name)}{'&' if depth else ''} {name}"


def starter_code(sig: Signature) -> str:
    params = ", ".join(_param(p.type, p.name) for p in sig.params)
    return (
        "class Solution {\n"
        "public:\n"
        f"    {cpp_type(sig.returns)} {sig.function}({params}) {{\n"
        "        return {};\n"
        "    }\n"
        "};\n"
    )


# Runs inside the sandbox. Same protocol as the Python harness: one marked JSON line per test
# on the real stdout (a dup of fd 1), user output captured in a file, expected outputs never
# present. Names live in __dc to stay out of the user's way.
_HARNESS = r"""
#include <bits/stdc++.h>
#include <fcntl.h>
#include <pthread.h>
#include <unistd.h>
#include "dcio.hpp"
using namespace std;

#include "solution.cpp"

namespace __dc {

static FILE* out;
static string mark;
static int cap_fd;

static void emit(const string& json) {
    fputs(mark.c_str(), out);
    fputs(json.c_str(), out);
    fputc('\n', out);
    fflush(out);
}

static string captured() {
    fflush(stdout);
    cout.flush();
    cerr.flush();
    off_t size = lseek(cap_fd, 0, SEEK_END);
    off_t from = size > 1000 ? size - 1000 : 0;
    string s(static_cast<size_t>(size - from), '\0');
    if (!s.empty() && pread(cap_fd, s.data(), s.size(), from) < 0) s.clear();
    return s;
}

static void reset_capture() {
    fflush(stdout);
    cout.flush();
    cerr.flush();
    if (ftruncate(cap_fd, 0) != 0) {}
    lseek(cap_fd, 0, SEEK_SET);
}

static void* run_all(void*) {
    try {
        dcio::load("inputs.json");
    } catch (const exception& e) {
        emit(string("{\"fatal\":") + dcio::dump(string("harness could not read inputs: ") + e.what()) + "}");
        return nullptr;
    }
    emit("{\"ready\":true}");
    for (size_t i = 0; i < dcio::cases(); i++) {
__ARGS__
        reset_capture();
        string result = "null", err;
        auto start = chrono::steady_clock::now();
        auto elapsed = [&] {
            return (long long)chrono::duration_cast<chrono::milliseconds>(
                chrono::steady_clock::now() - start).count();
        };
        long long ms = 0;
        try {
            Solution sol;
            __RET__ r = sol.__FUNCTION__(__CALL__);
            ms = elapsed();  // before serialization, which isn't the user's time
            result = dcio::dump(r);
        } catch (const bad_alloc&) {
            fflush(out);
            _exit(137);  // the runner reads 137 as a memory-limit kill
        } catch (const exception& e) {
            ms = elapsed();
            err = string("uncaught exception: ") + e.what();
        } catch (...) {
            ms = elapsed();
            err = "uncaught exception";
        }
        emit("{\"i\":" + to_string(i) + ",\"out\":" + (err.empty() ? result : string("null")) +
             ",\"ms\":" + to_string(ms) +
             ",\"err\":" + (err.empty() ? string("null") : dcio::dump(err)) +
             ",\"stdout\":" + dcio::dump(captured()) + "}");
    }
    emit("{\"done\":true}");
    return nullptr;
}

}  // namespace __dc

int main(int argc, char** argv) {
    if (argc < 2) return 2;
    __dc::mark = argv[1];
    __dc::out = fdopen(dup(1), "w");
    __dc::cap_fd = open("/work/.stdout", O_RDWR | O_CREAT | O_TRUNC, 0600);
    if (!__dc::out || __dc::cap_fd < 0) return 2;
    dup2(__dc::cap_fd, 1);
    dup2(__dc::cap_fd, 2);
    // Deep recursion in solutions needs more than the default 8 MB stack.
    pthread_attr_t attr;
    pthread_attr_init(&attr);
    pthread_attr_setstacksize(&attr, 256u << 20);
    pthread_t t;
    if (pthread_create(&t, &attr, __dc::run_all, nullptr) != 0) __dc::run_all(nullptr);
    else pthread_join(t, nullptr);
    fflush(__dc::out);
    _exit(0);
}
"""


def harness(sig: Signature) -> str:
    args = "\n".join(
        f'        auto a{n} = dcio::get<{cpp_type(p.type)}>(i, "{p.name}");'
        for n, p in enumerate(sig.params)
    )
    call = ", ".join(f"a{n}" for n in range(len(sig.params)))
    return (
        _HARNESS.replace("__ARGS__", args)
        .replace("__RET__", cpp_type(sig.returns))
        .replace("__FUNCTION__", sig.function)
        .replace("__CALL__", call)
    )
