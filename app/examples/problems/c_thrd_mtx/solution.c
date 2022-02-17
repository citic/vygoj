#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <threads.h>

size_t thread_count = 0;
mtx_t can_access_count;
long count = 0;
long positives = 0;
long negatives = 0;

int contribute(void* data);

int main(void) {
  int error = thrd_success;
  mtx_init(&can_access_count, mtx_plain);
  // Create secondary threads
  scanf("%zu", &thread_count);
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
  printf("%ld %ld %ld\n", count, negatives, positives);
  // Release resources
  mtx_destroy(&can_access_count);
  free(threads);
  return error;
}

int contribute(void* data) {
  const size_t rank = (size_t)data;
//  mtx_lock(&can_access_count);
  count += rank % 2 == 0 ? (long)rank : -(long)rank;
  struct timespec delay = {0, 1000000};
  thrd_sleep(&delay, NULL);
  if (count >= 0) {
    ++positives;
  } else {
    ++negatives;
  }
//  mtx_unlock(&can_access_count);
  return EXIT_SUCCESS;
}
