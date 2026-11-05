# Compiles and runs untrusted C++ submissions. The worker starts it with no network, no
# capabilities, a read-only root, and a tmpfs at /work (see backend/src/dailycommit/sandbox/backend.py).
FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends g++ nlohmann-json3-dev \
    && rm -rf /var/lib/apt/lists/*

# Built once here so a submission's compile only sees user code and a tiny header:
#  - dcio.o: the harness's JSON I/O (nlohmann/json instantiated for the problem value types)
#  - pch.hpp.gch: <bits/stdc++.h> precompiled with the exact flags the worker compiles with
#    (sandbox/languages.py CPP_FLAGS; keep them in sync or GCC silently ignores the PCH).
COPY dcio.hpp dcio.cpp /opt/dc/
RUN cd /opt/dc \
    && g++ -std=c++17 -O2 -c dcio.cpp -o dcio.o \
    && printf '#include <bits/stdc++.h>\n' > pch.hpp \
    && g++ -std=c++17 -O2 -pipe -x c++-header pch.hpp -o pch.hpp.gch \
    && rm dcio.cpp \
    && chmod -R a+rX,a-w /opt/dc

WORKDIR /work
USER 65534:65534
