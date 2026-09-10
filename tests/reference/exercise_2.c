#include <stdio.h>
#include <stdlib.h>

int main(int argc, char **argv) {
    int a, b, c, maximum;
    if (argc != 4) return 1;
    a = atoi(argv[1]);
    b = atoi(argv[2]);
    c = atoi(argv[3]);
    maximum = a > b ? a : b;
    maximum = maximum > c ? maximum : c;
    printf("%d\n", maximum);
    return 0;
}
