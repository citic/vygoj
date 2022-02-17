#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <threads.h>

#define MIN(x, y) (((x) < (y)) ? (x) : (y))

size_t thread_count = 0;
double required = 0.0;
mtx_t can_access_contribution;
double contribution = 0.0;

int contribute(void* data);

int main(void) {
  int error = thrd_success;
  mtx_init(&can_access_contribution, mtx_plain);
  // Create secondary threads
  scanf("%zu %lg", &thread_count, &required);
  thrd_t* threads = (thrd_t*) calloc(thread_count, sizeof(thrd_t));
  assert(threads);
  for (size_t index = 0; index < thread_count; ++index) {
    error = thrd_create(&threads[index], contribute, (void*)index);
    assert(error == thrd_success);
  }
  // Wait for secondary threads
  for (size_t index = 0; index < thread_count; ++index) {
    thrd_join(threads[index], NULL);
  }
  printf("%lg\n", contribution);
  // Release resources
  mtx_destroy(&can_access_contribution);
  free(threads);
  return error;
}

int contribute(void* data) {
  const size_t rank = (size_t)data;
  mtx_lock(&can_access_contribution);
  // Decide how much I am going to contribute
  const double left = required - contribution;
  const double my_max = rank + 1;
  const double my_contribution = MIN(left, my_max);
  // Get that money
  struct timespec milisecond = {0, 1000000};
  thrd_sleep(&milisecond, NULL);
  // Contribute it to the global amount
  contribution += my_contribution;
  mtx_unlock(&can_access_contribution);
  return EXIT_SUCCESS;
}
