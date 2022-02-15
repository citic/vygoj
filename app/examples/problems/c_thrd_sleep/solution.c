#include <threads.h>
#include <stdio.h>
#include <stdlib.h>

int greet(void* data);

int main(void) {
  int error = thrd_success;
  size_t thread_count = 0;
  scanf("%zu", &thread_count);
  thrd_t* threads = calloc(thread_count, sizeof(thrd_t));
  for (size_t index = 0; index < thread_count; ++index) {
    error = thrd_create(&threads[index], greet, (void*)index);
    if (error != thrd_success) {
      fprintf(stderr, "Error: could not create secondary thread %zu\n", index);
    }
  }
  // printf("Hello from main thread\n");
  for (size_t index = 0; index < thread_count; ++index) {
    thrd_join(threads[index], NULL);
  }
  free(threads);
  return error;
}

int greet(void* data) {
  size_t rank = (size_t)data;
  struct timespec delay = {0, 10000000 * rank};
  thrd_sleep(&delay, NULL);
  printf("Hello from secondary thread %zu\n", rank);
  return 0;
}
