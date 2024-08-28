#include <assert.h>
#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <threads.h>

size_t thread_count = 0;
size_t number_count = 0;
size_t* numbers = NULL;
mtx_t can_access_globals;
size_t next_number = 0;
size_t prime_count = 0;

int find_primes(void* data);
bool is_prime(size_t number);

int main(void) {
  int error = thrd_success;
  mtx_init(&can_access_globals, mtx_plain);
  // Read numbers
  scanf("%zu %zu", &thread_count, &number_count);
  numbers = (size_t*) calloc(number_count, sizeof(size_t));
  assert(numbers);
  for (size_t index = 0; index < number_count; ++index) {
    scanf("%zu", &numbers[index]);
  }
  // Create secondary threads
  thrd_t* threads = (thrd_t*) calloc(thread_count, sizeof(thrd_t));
  assert(threads);
  for (size_t index = 0; index < thread_count; ++index) {
    error = thrd_create(&threads[index], find_primes, (void*)index);
    assert(error == thrd_success);
  }
  // Wait for secondary threads
  for (size_t index = 0; index < thread_count; ++index) {
    thrd_join(threads[index], NULL);
  }
  // Print report
  printf("%zu primes:\n", prime_count);
  for (size_t index = 0; index < number_count; ++index) {
    if (numbers[index]) {
      printf("%zu\n", numbers[index]);
    }
  }
  // Release resources
  free(threads);
  free(numbers);
  mtx_destroy(&can_access_globals);
  return error;
}

int find_primes(void* data) {
  (void)data;
  // While there is pending work
  mtx_lock(&can_access_globals);
  size_t index = next_number++;
  mtx_unlock(&can_access_globals);
  while (index < number_count) {
    // I got a pending number, check if it is prime
    if (is_prime(numbers[index])) {
      mtx_lock(&can_access_globals);
      ++prime_count;
      mtx_unlock(&can_access_globals);
    } else {
      // Number is not prime, mark it to avoid printing it
      numbers[index] = 0;
    }
    // Try to get the next available work unit
    mtx_lock(&can_access_globals);
    index = next_number++;
    mtx_unlock(&can_access_globals);
  }
  return 0;
}

bool is_prime(size_t number) {
  if (number < 2) return false;
  if (number == 2) return true;
  if (number % 2 == 0) return false;

  size_t last = sqrt(number);
  for (size_t i = 3; i <= last; i += 2) {
    if (number % i == 0) {
      return false;
    }
  }

  return true;
}
