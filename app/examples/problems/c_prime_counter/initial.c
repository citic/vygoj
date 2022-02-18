#include <assert.h>
#include <math.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>

size_t thread_count = 0;
size_t number_count = 0;
size_t* numbers = NULL;
size_t prime_count = 0;

void find_primes(void);
bool is_prime(size_t number);

int main(void) {
  // Read numbers
  scanf("%zu %zu", &thread_count, &number_count);
  numbers = (size_t*) calloc(number_count, sizeof(size_t));
  assert(numbers);
  for (size_t index = 0; index < number_count; ++index) {
    scanf("%zu", &numbers[index]);
  }
  // Find primes
  find_primes();
  // Print report
  printf("%zu primes:\n", prime_count);
  for (size_t index = 0; index < number_count; ++index) {
    if (numbers[index]) {
      printf("%zu\n", numbers[index]);
    }
  }
  // Release resources
  free(numbers);
  return EXIT_SUCCESS;
}

void find_primes(void) {
  // Traverse all numbers
  for (size_t index = 0; index < number_count; ++index) {
    // If number is prime, increase the counter
    if (is_prime(numbers[index])) {
      ++prime_count;
    } else {
      // Number is not prime, mark it to avoid printing it later
      numbers[index] = 0;
    }
  }
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
