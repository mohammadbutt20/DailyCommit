"""Starter code and test harness for Java submissions.

The user's file is Solution.java (`class Solution` with the problem's method); the harness is
Main.java. Both are compiled together inside the sandbox, so a wrong signature is a compile
error. JSON goes through Gson, which is baked into the image.
"""

from dailycommit.problems.schema import Signature, parse_type

_JAVA_TYPES = {
    "int": "int",
    "long": "long",
    "double": "double",
    "bool": "boolean",
    "string": "String",
}
_DEFAULTS = {"int": "0", "long": "0", "double": "0.0", "bool": "false", "string": '""'}


def java_type(type_name: str) -> str:
    base, depth = parse_type(type_name)
    return _JAVA_TYPES[base] + "[]" * depth


def _default(type_name: str) -> str:
    base, depth = parse_type(type_name)
    if depth == 0:
        return _DEFAULTS[base]
    return f"new {_JAVA_TYPES[base]}[0]" + "[]" * (depth - 1)


def starter_code(sig: Signature) -> str:
    params = ", ".join(f"{java_type(p.type)} {p.name}" for p in sig.params)
    return (
        "import java.util.*;\n"
        "\n"
        "class Solution {\n"
        f"    public {java_type(sig.returns)} {sig.function}({params}) {{\n"
        f"        return {_default(sig.returns)};\n"
        "    }\n"
        "}\n"
    )


# Runs inside the sandbox. Same protocol as the Python harness: one marked JSON line per test
# on the real stdout, user output captured separately, expected outputs never present.
_HARNESS = r"""
import com.google.gson.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;

public final class Main {
    private static final Gson GSON =
        new GsonBuilder().serializeNulls().serializeSpecialFloatingPointValues().create();
    private static PrintStream out;
    private static String mark;

    public static void main(String[] args) throws Exception {
        mark = args[0];
        out = new PrintStream(new FileOutputStream(FileDescriptor.out), false, StandardCharsets.UTF_8);
        // Deep recursion in solutions needs more than the default main-thread stack.
        Thread t = new Thread(null, Main::runAll, "solution", 256L << 20);
        t.start();
        t.join();
        out.flush();
    }

    private static void emit(JsonObject o) {
        out.print(mark + GSON.toJson(o) + "\n");
        out.flush();
    }

    private static String trace(Throwable e) {
        StringBuilder sb = new StringBuilder(e.toString());
        int shown = 0;
        for (StackTraceElement f : e.getStackTrace()) {
            String c = f.getClassName();
            if (c.equals("Main") || c.startsWith("java.") || c.startsWith("jdk.")
                    || c.startsWith("com.google.")) continue;
            sb.append("\n    at ").append(f);
            if (++shown == 5) break;
        }
        String s = sb.toString();
        return s.length() > 2000 ? s.substring(s.length() - 2000) : s;
    }

    private static String tail(String s, int n) {
        return s.length() > n ? s.substring(s.length() - n) : s;
    }

    private static void runAll() {
        JsonArray cases;
        try {
            cases = JsonParser.parseString(Files.readString(Path.of("inputs.json"))).getAsJsonArray();
        } catch (Exception e) {
            JsonObject o = new JsonObject();
            o.addProperty("fatal", "harness could not read inputs: " + e);
            emit(o);
            return;
        }
        ByteArrayOutputStream captured = new ByteArrayOutputStream();
        PrintStream capture = new PrintStream(captured, true, StandardCharsets.UTF_8);
        System.setOut(capture);
        System.setErr(capture);
        JsonObject ready = new JsonObject();
        ready.addProperty("ready", true);
        emit(ready);
        for (int i = 0; i < cases.size(); i++) {
            JsonObject c = cases.get(i).getAsJsonObject();
__ARGS__
            captured.reset();
            Object result = null;
            String err = null;
            long start = System.nanoTime();
            try {
                result = new Solution().__FUNCTION__(__CALL__);
            } catch (OutOfMemoryError e) {
                // The runner reads exit code 137 as a memory-limit kill, same as the kernel OOM killer.
                out.flush();
                Runtime.getRuntime().halt(137);
            } catch (Throwable e) {
                err = trace(e);
            }
            long ms = (System.nanoTime() - start) / 1_000_000;
            capture.flush();
            JsonObject o = new JsonObject();
            o.addProperty("i", i);
            o.add("out", err == null ? GSON.toJsonTree(result) : JsonNull.INSTANCE);
            o.addProperty("ms", ms);
            if (err == null) o.add("err", JsonNull.INSTANCE); else o.addProperty("err", err);
            o.addProperty("stdout", tail(captured.toString(StandardCharsets.UTF_8), 1000));
            emit(o);
        }
        JsonObject done = new JsonObject();
        done.addProperty("done", true);
        emit(done);
    }
}
"""


def harness(sig: Signature) -> str:
    args = "\n".join(
        f"            {java_type(p.type)} a{n} = "
        f'GSON.fromJson(c.get("{p.name}"), {java_type(p.type)}.class);'
        for n, p in enumerate(sig.params)
    )
    call = ", ".join(f"a{n}" for n in range(len(sig.params)))
    return (
        _HARNESS.replace("__ARGS__", args)
        .replace("__FUNCTION__", sig.function)
        .replace("__CALL__", call)
    )
