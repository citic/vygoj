#include <threads.h>
#include <stdio.h>
#include <stdlib.h>

mtx_t can_access_count;
size_t count = 0;

int increase(void* data) {
  (void)data;
  mtx_lock(&can_access_count);
  ++count;
  mtx_unlock(&can_access_count);
  return EXIT_SUCCESS;
}

int main(void) {
  mtx_init(&can_access_count, mtx_plain);
  thrd_t thread[2];
  thrd_create(&thread[0], increase, (void*)NULL);
  thrd_create(&thread[1], increase, (void*)NULL);
  thrd_join(thread[0], NULL);
  thrd_join(thread[1], NULL);
  printf("count = %zu\n", count);
  mtx_destroy(&can_access_count);
  return EXIT_SUCCESS;
}
