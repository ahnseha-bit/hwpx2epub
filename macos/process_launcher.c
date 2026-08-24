#include <errno.h>
#include <stdio.h>
#include <unistd.h>

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "usage: epub_launcher <engine> [arguments...]\n");
        return 64;
    }
    if (setpgid(0, 0) != 0) {
        perror("setpgid");
        return 70;
    }
    execv(argv[1], &argv[1]);
    perror("execv");
    return errno == ENOENT ? 127 : 126;
}
