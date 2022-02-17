#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <threads.h>

size_t thread_count = 0;
double required = 0.0;
double contribution = 0.0;

int contribute(void* data);

int main(void) {
  int error = thrd_success;
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
  free(threads);
  return error;
}

int contribute(void* data) {
  const size_t rank = (size_t)data;
  const double my_contribution = rank;
  struct timespec milisecond = {0, 1000000};
  thrd_sleep(&milisecond, NULL);
  contribution += my_contribution;
  return EXIT_SUCCESS;
}
