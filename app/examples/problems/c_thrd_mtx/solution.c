#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <threads.h>

size_t thread_count = 0;
size_t duration = 0;
mtx_t can_access_force;
long force = 0;

int pull_rope(void* data);

int main(void) {
  int error = mtx_init(&can_access_force, mtx_plain);
  scanf("%zu %zu", &thread_count, &duration);
  // Create secondary threads
  thrd_t* threads = (thrd_t*) calloc(thread_count, sizeof(thrd_t));
  assert(threads);
  for (size_t index = 1; index < thread_count; ++index) {
    error = thrd_create(&threads[index], pull_rope, (void*)index);
    assert(error == thrd_success);
  }
  // Wait for secondary threads
  for (size_t index = 1; index < thread_count; ++index) {
    thrd_join(threads[index], NULL);
  }
  // Report game result
  const char* winner = force > 0 ? "even won" : force < 0 ? "odd won" : "tie"; 
  printf("Result %ld: %s\n", force, winner);
  // Release resources
  mtx_destroy(&can_access_force);
  free(threads);
  return error;
}

int pull_rope(void* data) {
  const size_t rank = (size_t)data;
  const long my_force = rank % 2 == 0 ? rank : -(long)rank;
  // While game is active
  size_t my_time = 0;
  while (my_time < duration) {
    // Rest to get force
    const size_t milliseconds = 10 * rank;
    const struct timespec delay = { 0, 1000000 * milliseconds };
    thrd_sleep(&delay, NULL);
    my_time += rank;
    // Pull the rope
    mtx_lock(&can_access_force);
    force += my_force;
    mtx_unlock(&can_access_force);
  }
  return 0;
}
