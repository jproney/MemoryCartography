// Easy test to make sure we can find all of the pointers in the data section
#include <stdlib.h>
#include <stdio.h>


static long foo = 0xdeadbeef;
static char* ptr = NULL;
static char* bar = (char*)0xfeedface;
static char baz = 'a';
static char* word = "hello";

int main(int argc, char* argv[]){
    ptr = malloc(263);
    printf("Break here and find the pointers!\n");
    free(ptr);
    return 0;
}
