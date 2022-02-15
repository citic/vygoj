#include <stdio.h>
#include <stdlib.h>
#include <threads.h>

int greet(void* data);

int main(void) {
  thrd_t thread;
  int error = thrd_create(&thread, greet, (void*)NULL);
  if (error == thrd_success) {
    printf("Hello from main thread\n");
    thrd_join(thread, NULL);
  } else {
    fprintf(stderr, "Error: could not create secondary thread\n");
  }
  return error;
}

int greet(void* data) {
  (void)data;
  printf("Hello from secondary thread\n");
  return 0;
}
