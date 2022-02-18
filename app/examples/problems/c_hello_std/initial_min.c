#include <stdio.h>
#include <stdlib.h>
#include <threads.h>

int greet(void* data) {
  (void)data;
  printf("Hello from secondary thread\n");
  return EXIT_SUCCESS;
}

int main(void) {
  thrd_t thread;
  thrd_create(&thread, greet, (void*)NULL);
  printf("Hello from main thread\n");
  thrd_join(thread, NULL);
  return EXIT_SUCCESS;
}
