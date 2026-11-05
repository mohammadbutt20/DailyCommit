# Compiles and runs untrusted Java submissions. The worker starts it with no network, no
# capabilities, a read-only root, and a tmpfs at /work (see backend/src/dailycommit/sandbox/backend.py).
FROM eclipse-temurin:21-jdk-jammy

# Gson for the generated harness's JSON (de)serialization. Pinned by checksum.
ADD --checksum=sha256:57928d6e5a6edeb2abd3770a8f95ba44dce45f3b23b7a9dc2b309c581552a78b \
    https://repo1.maven.org/maven2/com/google/code/gson/gson/2.11.0/gson-2.11.0.jar \
    /opt/gson/gson.jar
RUN chmod 755 /opt/gson && chmod 444 /opt/gson/gson.jar

# Class-data-sharing archive for javac's startup classes: the root is read-only at run time, so
# build it here. Cuts roughly a third off every compile.
RUN mkdir /tmp/warm && cd /tmp/warm \
    && printf 'class W { public static void main(String[] a) { System.out.println(java.util.List.of(1)); } }' > W.java \
    && javac -J-XX:ArchiveClassesAtExit=/opt/javac.jsa -cp /opt/gson/gson.jar W.java \
    && chmod 444 /opt/javac.jsa \
    && cd / && rm -rf /tmp/warm

WORKDIR /work
USER 65534:65534
