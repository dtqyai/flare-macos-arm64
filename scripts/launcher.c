#include <mach-o/dyld.h>
#include <libgen.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
int main(int argc, char **argv) {
    char raw[PATH_MAX], resolved[PATH_MAX], engine[PATH_MAX], data[PATH_MAX + 32];
    uint32_t size = sizeof(raw);
    if (_NSGetExecutablePath(raw, &size) || !realpath(raw, resolved)) { perror("Flare path"); return 1; }
    char *dir = dirname(resolved);
    snprintf(engine, sizeof(engine), "%s/flare", dir);
    snprintf(data, sizeof(data), "--data-path=%s/../Resources", dir);
    char **args = calloc((size_t)argc + 2, sizeof(char *));
    if (!args) return 1;
    args[0] = engine;
    args[1] = data;
    for (int i = 1; i < argc; ++i) args[i + 1] = argv[i];
    execv(engine, args);
    perror("Flare launch");
    free(args);
    return 1;
}
