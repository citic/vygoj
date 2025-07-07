// Copyright 2025 ECCI-UCR CC-BY 4.0
#include <atomic>
#include <cmath>
#include <iostream>
#include <thread>
#include <vector>

// Global variables, bad practice, but do not fix it for this problem
size_t thread_count = 0;
size_t number_count = 0;
std::vector<size_t> numbers;
size_t prime_count = 0;

void find_primes();
bool is_prime(const size_t number);

int main() {
  // Read numbers from stdin and fill the vector
  std::cin >> thread_count >> number_count;
  numbers.resize(number_count);
  for (size_t index = 0; index < number_count; ++index) {
    std::cin >> numbers[index];
  }
  // TODO: Create secondary threads. Use emplace_back() instead of push_back()
  find_primes();
  // TODO: Wait for all threads to finish. Call thread.join()
  // Print report
  std::cout << prime_count << " primes:" << std::endl;
  for (size_t index = 0; index < number_count; ++index) {
    if (numbers[index]) {
      std::cout << numbers[index] << std::endl;
    }
  }
  return 0;
}

void find_primes() {
  // While there is pending work
  // TODO: Parallelize this loop using dynamic mapping
  for (size_t index = 0; index < number_count; ++index) {
    // I got a pending number, check if it is prime
    if (is_prime(numbers[index])) {
      ++prime_count;
    } else {
      // Number is not prime, mark it to avoid printing it
      numbers[index] = 0;
    }
  }
}

bool is_prime(const size_t number) {
  if (number < 2) return false;
  if (number == 2) return true;
  if (number % 2 == 0) return false;
  size_t last = std::sqrt(number);
  for (size_t divisor = 3; divisor <= last; divisor += 2) {
    if (number % divisor == 0) {
      return false;
    }
  }
  return true;
}
