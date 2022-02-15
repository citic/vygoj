#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <threads.h>

size_t thread_count = 0;
size_t work_count = 0;
size_t* work_units = NULL;
size_t next_unit = 0;

int simulate_work(void* data);

int main(void) {
  int error = thrd_success;
  // Read work units
  scanf("%zu %zu", &thread_count, &work_count);
  work_units = (size_t*) calloc(work_count, sizeof(size_t));
  assert(work_units);
  for (size_t index = 0; index < work_count; ++index) {
    scanf("%zu", &work_units[index]);
  }
  // Create secondary threads
  thrd_t* threads = (thrd_t*) calloc(thread_count, sizeof(thrd_t));
  assert(threads);
  for (size_t index = 0; index < thread_count; ++index) {
    error = thrd_create(&threads[index], simulate_work, (void*)index);
    assert(error == thrd_success);
  }
  // Wait for secondary threads
  for (size_t index = 0; index < thread_count; ++index) {
    thrd_join(threads[index], NULL);
  }
  // Release resources
  free(threads);
  free(work_units);
  return error;
}

int simulate_work(void* data) {
  const size_t rank = (size_t)data;
  // While there is pending work
  size_t my_unit = next_unit++;
  while (my_unit < work_count) {
    // I got a work unit, simulate it by sleeping
    const size_t milliseconds = work_units[my_unit];
    const struct timespec delay = { 0, 1000000 * milliseconds };
    thrd_sleep(&delay, NULL);
    // I finished my work unit, report it
    printf("Thread %zu completed work %zu: %zu\n", rank, my_unit, milliseconds);
    // Try to get the next available work unit
    my_unit = next_unit++;
  }
  return 0;
}
